"""Unit tests for MF-10 constrained playlist selection solver (UT_SOLV, FR-5.2, INV-09..11)."""

# ruff: noqa: N802
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from yt_intel_mcp.config import SimilarityConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.playlist import (
    UNVERIFIED_AUDIO_LANGUAGE_LABEL,
    build_playlist_constraints,
    evaluate_selection_constraints,
    score_candidates_for_topic,
    solve_playlist_selection,
)

FORBIDDEN_POPULARITY_AND_HTTP = {
    "httpx",
    "httpcore",
    "requests",
    "aiohttp",
    "google",
    "urllib",
    "view_count",
    "like_count",
    "subscriber_count",
    "statistics",
}


def _video(
    video_id: str,
    title: str,
    duration_seconds: int | None,
    *,
    tags: tuple[str, ...] = (),
    description: str = "",
    default_audio_language: str | None = "en",
    default_language: str | None = "en",
    is_available: bool = True,
    privacy_status: str = "public",
    live_broadcast_content: str = "none",
) -> VideoMeta:
    return VideoMeta(
        video_id=video_id,
        title=title,
        tags=tags,
        description=description,
        duration_seconds=duration_seconds,
        default_audio_language=default_audio_language,
        default_language=default_language,
        is_available=is_available,
        privacy_status=privacy_status,
        live_broadcast_content=live_broadcast_content,
    )


def test_UT_SOLV_maximises_topic_relevance_inside_strict_window() -> None:
    constraints = build_playlist_constraints(
        topic="python asyncio",
        target_total_minutes=120,
        tolerance_percent=5,
        max_video_minutes=60,
        max_videos=10,
    )
    # Optimal pair (V_HIGH_A, V_HIGH_B) = 3500 + 3500 = 7000s in [6840, 7200], total score 1.80.
    # Greedy/single traps: V_TRAP (3600s, 0.70) or V_OVER_CAP (3601s > 60m inclusive cap).
    videos = [
        _video("V_TRAP", "Python Basics", 3600),
        _video("V_FILLER", "Unrelated Stuff", 3300),
        _video("V_HIGH_A", "Python Asyncio Deep Dive", 3500),
        _video("V_HIGH_B", "Python Asyncio Structured Concurrency", 3500),
        _video("V_OVER_CAP", "Marathon Talk", 3601),  # > 60m inclusive cap
        _video("V_PRIVATE", "Private Asyncio", 3500, privacy_status="private"),
        _video("V_LIVE", "Live Asyncio", 3500, live_broadcast_content="live"),
    ]
    scores = {
        "V_TRAP": 0.70,
        "V_FILLER": 0.10,
        "V_HIGH_A": 0.92,
        "V_HIGH_B": 0.88,
        "V_OVER_CAP": 0.99,
        "V_PRIVATE": 0.99,
        "V_LIVE": 0.99,
    }

    solution = solve_playlist_selection(videos, constraints, relevance_scores=scores)
    selected_ids = [item.video.video_id for item in solution.selected_videos]
    assert selected_ids == ["V_HIGH_A", "V_HIGH_B"]
    assert solution.total_duration_seconds == 7000
    assert solution.total_duration_human == "1h 56m 40s"
    assert solution.total_relevance_score == pytest.approx(1.80)
    assert solution.candidates_retrieved == 7
    assert solution.candidates_eligible == 4
    assert (
        evaluate_selection_constraints(
            [item.video for item in solution.selected_videos], constraints
        )
        == []
    )


def test_UT_SOLV_UT_DUR_window_boundaries_114_120_and_never_relaxes_silently() -> None:
    constraints = build_playlist_constraints(
        topic="distributed consensus",
        target_total_minutes=120,
        tolerance_percent=5,
        max_video_minutes=60,
    )
    # Exact floor 6840s (114:00) and exact ceiling 7200s (120:00) accepted
    exact_floor = solve_playlist_selection(
        [
            _video("V1", "Consensus A", 3420),
            _video("V2", "Consensus B", 3420),
        ],
        constraints,
    )
    assert exact_floor.total_duration_seconds == 6840
    assert exact_floor.total_duration_human == "1h 54m"

    exact_ceil = solve_playlist_selection(
        [
            _video("V1", "Consensus A", 3600),
            _video("V2", "Consensus B", 3600),
        ],
        constraints,
    )
    assert exact_ceil.total_duration_seconds == 7200
    assert exact_ceil.total_duration_human == "2h"

    # Adjacent out-of-window totals 6839s (113:59) and 7201s (120:01) NEVER accepted or relaxed
    with pytest.raises(ToolError) as below_err:
        solve_playlist_selection(
            [
                _video("V1", "Consensus A", 3420),
                _video("V2", "Consensus B", 3419),
            ],
            constraints,
        )
    assert below_err.value.code is ErrorCode.CONSTRAINTS_UNSATISFIABLE
    assert below_err.value.details["closest_achievable_seconds"] == 6839
    assert below_err.value.details["binding_constraint"] == "insufficient_candidate_pool"

    with pytest.raises(ToolError) as over_err:
        solve_playlist_selection(
            [
                _video("V1", "Consensus A", 3600),
                _video("V2", "Consensus B", 3601),  # also over 60m max_video_minutes
            ],
            build_playlist_constraints(
                topic="distributed consensus",
                target_total_minutes=120,
                tolerance_percent=5,
                max_video_minutes=65,
            ),
        )
    assert over_err.value.code is ErrorCode.CONSTRAINTS_UNSATISFIABLE
    assert over_err.value.details["closest_achievable_seconds"] == 3601


def test_UT_SOLV_deterministic_tie_breaking_and_playback_ordering() -> None:
    constraints = build_playlist_constraints(
        topic="sqlite storage",
        target_total_minutes=40,
        tolerance_percent=5,
        max_video_minutes=25,
    )
    # Pair (A, D) = 0.80 (1000+1400=2400s), Pair (B, C) = 0.80 (1200+1200=2400s).
    # D+B and D+C exceed 2400s; A+B and A+C fall below 2280s. Thus ONLY {A, D} and {B, C} fit,
    # tying at 0.80 so lexicographical tie break ("A", "D") < ("B", "C") must win regardless of
    # input permutation, then playback ordering sorts D (0.55) before A (0.25) => ["D", "A"].
    base_videos = [
        _video("D", "SQLite Storage D", 1400),
        _video("B", "SQLite Storage B", 1200),
        _video("C", "SQLite Storage C", 1200),
        _video("A", "SQLite Storage A", 1000),
        _video("D", "SQLite Storage Duplicate", 1400),  # duplicate ID deduplicated cleanly
    ]
    scores = {"A": 0.25, "D": 0.55, "B": 0.40, "C": 0.40}

    sol_forward = solve_playlist_selection(base_videos, constraints, relevance_scores=scores)
    sol_reversed = solve_playlist_selection(
        list(reversed(base_videos)), constraints, relevance_scores=scores
    )
    assert [v.video.video_id for v in sol_forward.selected_videos] == ["D", "A"]
    assert [v.video.video_id for v in sol_reversed.selected_videos] == ["D", "A"]
    assert sol_forward.candidates_retrieved == 4


def test_UT_SOLV_tfidf_end_to_end_scoring_and_audio_language_labels() -> None:
    constraints = build_playlist_constraints(
        topic="python asyncio event loop",
        target_total_minutes=30,
        tolerance_percent=10,
        language="en",
        allow_unknown_language=True,
    )
    videos = [
        _video(
            "V_MATCH_EN",
            "Python Asyncio Event Loop Internals",
            900,
            tags=("python", "asyncio"),
            description="Complete guide to event loop tasks and https://evil.example/inject",
            default_audio_language="en-US",
            default_language="fr",
        ),
        _video(
            "V_UNVERIFIED",
            "Python Asyncio Coroutines Workshop",
            900,
            tags=("asyncio",),
            default_audio_language=None,
            default_language="en",
        ),
        _video(
            "V_WRONG_AUDIO",
            "Python Asyncio Event Loop Masterclass",
            900,
            default_audio_language="es",
            default_language="en",
        ),
        _video(
            "V_OFFTOPIC",
            "Artisan Bread Fermentation",
            900,
            default_audio_language="en",
        ),
    ]

    computed_scores = score_candidates_for_topic("python asyncio event loop", videos)
    assert computed_scores["V_MATCH_EN"] > computed_scores["V_UNVERIFIED"] > 0.0
    assert computed_scores["V_OFFTOPIC"] == 0.0

    solution = solve_playlist_selection(videos, constraints)
    assert [item.video.video_id for item in solution.selected_videos] == [
        "V_MATCH_EN",
        "V_UNVERIFIED",
    ]
    assert solution.selected_videos[0].audio_language_status == "verified"
    assert solution.selected_videos[0].is_audio_language_unverified is False
    assert solution.selected_videos[1].audio_language_status == "unverified"
    assert solution.selected_videos[1].is_audio_language_unverified is True
    assert solution.selected_videos[1].audio_language_label == UNVERIFIED_AUDIO_LANGUAGE_LABEL
    assert solution.algorithm_used == "exact"

    # Small exact DP regime coverage (n_elig * max_k * (T+1) <= 250k and T <= 3600)
    assert score_candidates_for_topic("the and", [videos[0]]) == {"V_MATCH_EN": 0.0}
    assert score_candidates_for_topic("python", []) == {}


def test_UT_SOLV_constraints_unsatisfiable_diagnostics_and_options() -> None:
    # 1. Empty or all unavailable pool -> insufficient_candidate_pool
    constraints = build_playlist_constraints(topic="rust", target_total_minutes=60)
    with pytest.raises(ToolError) as empty_err:
        solve_playlist_selection([], constraints)
    assert empty_err.value.code is ErrorCode.CONSTRAINTS_UNSATISFIABLE
    assert empty_err.value.details["candidates_retrieved"] == 0
    assert empty_err.value.details["binding_constraint"] == "insufficient_candidate_pool"
    assert empty_err.value.details["requires_user_choice"] is True
    assert "among the 0 candidates retrieved" in empty_err.value.message
    assert "not mean none exists on YouTube" in empty_err.value.message
    assert empty_err.value.details["options"][0]["estimated_extra_quota"] == {
        "search_calls": 1,
        "units": 1,
    }

    # 2. Language filter eliminates all playable items -> language_filter + opt-in option
    lang_constraints = build_playlist_constraints(
        topic="rust", target_total_minutes=30, language="en", allow_unknown_language=False
    )
    with pytest.raises(ToolError) as lang_err:
        solve_playlist_selection(
            [
                _video("V1", "Rust Ownership", 900, default_audio_language=None),
                _video("V2", "Rust Lifetimes", 900, default_audio_language="de"),
            ],
            lang_constraints,
        )
    assert lang_err.value.code is ErrorCode.CONSTRAINTS_UNSATISFIABLE
    assert lang_err.value.details["binding_constraint"] == "language_filter"
    params = {opt.get("parameter") for opt in lang_err.value.details["options"]}
    assert "allow_unknown_language" in params
    assert "language" in params

    # 3. Per-video max_video_minutes rejects all candidates -> max_video_minutes
    per_vid_constraints = build_playlist_constraints(
        topic="rust", target_total_minutes=60, max_video_minutes=15
    )
    with pytest.raises(ToolError) as max_vid_err:
        solve_playlist_selection(
            [_video("V1", "Long Rust Lecture", 1200)],
            per_vid_constraints,
        )
    assert max_vid_err.value.details["binding_constraint"] == "max_video_minutes"
    max_vid_opts = [
        opt
        for opt in max_vid_err.value.details["options"]
        if opt.get("parameter") == "max_video_minutes"
    ]
    assert max_vid_opts and max_vid_opts[0]["suggested_value"] == 20

    # 4. max_videos capacity blocks reaching target_min_seconds -> max_videos_capacity
    cap_constraints = build_playlist_constraints(
        topic="rust", target_total_minutes=30, max_videos=2, tolerance_percent=0
    )
    with pytest.raises(ToolError) as cap_err:
        solve_playlist_selection(
            [
                _video("V1", "Rust Part 1", 600),
                _video("V2", "Rust Part 2", 600),
                _video("V3", "Rust Part 3", 600),
            ],
            cap_constraints,
        )
    assert cap_err.value.details["binding_constraint"] == "max_videos_capacity"
    cap_opts = [
        opt for opt in cap_err.value.details["options"] if opt.get("parameter") == "max_videos"
    ]
    assert cap_opts and cap_opts[0]["suggested_value"] == 3

    # 5. Window gap over [3420, 3600] despite longest_sum >= 3420 -> target_total_window_floor
    gap_constraints = build_playlist_constraints(
        topic="rust", target_total_minutes=60, tolerance_percent=5, max_videos=3
    )
    with pytest.raises(ToolError) as gap_err:
        solve_playlist_selection(
            [
                _video("V1", "Rust A", 2500),
                _video("V2", "Rust B", 2500),
                _video("V3", "Rust C", 800),
            ],
            gap_constraints,
        )
    assert gap_err.value.details["binding_constraint"] == "target_total_window_floor"
    assert gap_err.value.details["closest_achievable_seconds"] == 3300
    tol_opts = [
        opt
        for opt in gap_err.value.details["options"]
        if opt.get("parameter") == "tolerance_percent"
    ]
    assert tol_opts and tol_opts[0]["suggested_value"] >= 8.34


def test_UT_SOLV_exact_bitset_fallback_handles_sparse_zero_tolerance_in_scaled_regime() -> None:
    # Build > 35 candidates AND > 1.5M exact_work where bucket DP step (30s) causes
    # higher-scoring noise (2410s) to dominate bucket 80/160 and overshoot 7200s, proving
    # exact bitset fallback + local search recovers 2401 + 2401 + 2398 = 7200 in scaled mode.
    constraints = build_playlist_constraints(
        topic="systems engineering",
        target_total_minutes=120,
        tolerance_percent=0,
        max_video_minutes=65,
        max_videos=6,
    )
    videos = [_video(f"S_{i:03d}", "Systems Noise", 2410) for i in range(40)]
    videos.extend(
        [
            _video("EXACT_A", "Systems Core A", 2401),
            _video("EXACT_B", "Systems Core B", 2398),
            _video("ALT_C", "Systems Alt C", 2401),
        ]
    )
    scores = {f"S_{i:03d}": 0.90 for i in range(40)}
    scores["EXACT_A"] = 0.40
    scores["EXACT_B"] = 0.50
    scores["ALT_C"] = 0.65

    solution = solve_playlist_selection(videos, constraints, relevance_scores=scores)
    assert solution.total_duration_seconds == 7200
    assert solution.algorithm_used == "bitset_local_search"
    assert [item.video.video_id for item in solution.selected_videos] == [
        "ALT_C",
        "EXACT_B",
        "EXACT_A",
    ]
    assert (
        evaluate_selection_constraints(
            [item.video for item in solution.selected_videos], constraints
        )
        == []
    )

    # Verify unknown-audio shortfall triggers language_filter binding_constraint diagnosis
    short_lang_constraints = build_playlist_constraints(
        topic="systems", target_total_minutes=30, language="en", allow_unknown_language=False
    )
    with pytest.raises(ToolError) as err_lang_short:
        solve_playlist_selection(
            [
                _video("V_EN", "Systems Design", 900, default_audio_language="en"),
                _video("V_UNK", "Systems Unknown", 900, default_audio_language=None),
            ],
            short_lang_constraints,
        )
    assert err_lang_short.value.code is ErrorCode.CONSTRAINTS_UNSATISFIABLE
    assert err_lang_short.value.details["binding_constraint"] == "language_filter"


def test_UT_SOLV_guards_scaled_bnb_and_no_popularity_imports() -> None:
    constraints = build_playlist_constraints(topic="python", target_total_minutes=30)
    valid = [_video("V1", "Python", 1800)]

    with pytest.raises(ValueError, match="positive sum"):
        score_candidates_for_topic(
            "python",
            valid,
            similarity_config=SimilarityConfig(
                title_weight=0.0, tags_weight=0.0, description_weight=0.0
            ),
        )

    for bad_score in (-0.1, 1.1, float("nan")):
        with pytest.raises(ValueError, match=r"\[0.0, 1.0\]"):
            solve_playlist_selection(valid, constraints, relevance_scores={"V1": bad_score})

    with pytest.raises(ValueError, match="numeric"):
        solve_playlist_selection(valid, constraints, relevance_scores={"V1": True})  # type: ignore[dict-item]

    # Exercise Branch-and-Bound path directly on N <= 35 with target > 3600s
    long_constraints = build_playlist_constraints(
        topic="algorithms",
        target_total_minutes=180,
        tolerance_percent=5,
        max_video_minutes=60,
        max_videos=6,
    )
    items = [_video(f"ALG_{i:02d}", f"Algorithms Lecture {i}", 1800 + i * 60) for i in range(18)]
    long_sol = solve_playlist_selection(items, long_constraints)
    assert 10260 <= long_sol.total_duration_seconds <= 10800
    assert long_sol.algorithm_used == "exact"

    # Provider isolation & objective metadata audit (SE-6, INV-01)
    source_path = (
        Path(__file__).resolve().parents[2] / "src" / "yt_intel_mcp" / "playlist" / "solver.py"
    )
    raw = source_path.read_text(encoding="utf-8")
    tree = ast.parse(raw)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(FORBIDDEN_POPULARITY_AND_HTTP)
    for forbidden in (
        "view_count",
        "viewCount",
        "like_count",
        "likeCount",
        "subscriber_count",
        "subscriberCount",
    ):
        assert forbidden not in raw
