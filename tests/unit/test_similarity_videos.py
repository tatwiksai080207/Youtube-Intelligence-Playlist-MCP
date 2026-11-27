"""Unit tests for objective video similarity ranking (UT_SIM, FR-1.2, FR-1.3, INV-01)."""

# ruff: noqa: N802
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.similarity.videos import (
    compute_duration_similarity,
    is_eligible_candidate,
    rank_similar_videos,
    resolve_video_similarity_weights,
)

FORBIDDEN_POPULARITY_AND_HTTP = {
    "httpx",
    "requests",
    "aiohttp",
    "google",
    "view_count",
    "like_count",
    "subscriber_count",
    "statistics",
}


def _video(
    vid: str,
    *,
    title: str,
    tags: tuple[str, ...] = (),
    description: str = "",
    category_id: str | None = "28",
    duration_seconds: int | None = 600,
    live_broadcast_content: str = "none",
    privacy_status: str = "public",
    is_available: bool = True,
) -> VideoMeta:
    return VideoMeta(
        video_id=vid,
        title=title,
        description=description,
        channel_id=f"UC_{vid}",
        channel_title=f"Channel {vid}",
        tags=tags,
        category_id=category_id,
        category_name="Science & Technology" if category_id == "28" else "Education",
        duration_seconds=duration_seconds,
        live_broadcast_content=live_broadcast_content,
        privacy_status=privacy_status,
        is_available=is_available,
    )


def test_UT_SIM_video_module_contains_no_popularity_or_http_imports() -> None:
    src = Path("src/yt_intel_mcp/similarity/videos.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not (names & FORBIDDEN_POPULARITY_AND_HTTP)
    assert not (attrs & FORBIDDEN_POPULARITY_AND_HTTP)
    # VideoMeta has no popularity attributes by contract (INV-01).
    assert not hasattr(VideoMeta(video_id="dQw4w9WgXcQ", title="t"), "view_count")


def test_UT_SIM_missing_tags_and_live_duration_weight_redistribution() -> None:
    seed_no_tags = _video(
        "seed0000001",
        title="Python Asyncio Event Loops",
        tags=(),
        description="Deep dive into structured concurrency and coroutines.",
        category_id="28",
        duration_seconds=600,
    )
    cand_exact = _video(
        "cand0000001",
        title="Python Asyncio Event Loops",
        tags=("python", "asyncio"),
        description="Deep dive into structured concurrency and coroutines.",
        category_id="28",
        duration_seconds=600,
    )
    cand_unrelated = _video(
        "cand0000002",
        title="Sourdough Baking Fermentation",
        tags=("baking",),
        description="Artisan bread baking guide.",
        category_id="26",
        duration_seconds=1800,
    )

    result = rank_similar_videos(seed_no_tags, [cand_exact, cand_unrelated], max_results=5)
    assert result.active_weights["tags"] == 0.0
    assert sum(result.active_weights.values()) == pytest.approx(1.0)
    # Exact match across all active features reaches 1.0 despite missing seed tags.
    assert result.ranked_videos[0].video.video_id == "cand0000001"
    assert result.ranked_videos[0].score == pytest.approx(1.0)
    assert result.ranked_videos[1].video.video_id == "cand0000002"
    assert result.ranked_videos[1].score < 0.5


def test_UT_SIM_excludes_seed_private_deleted_and_live_candidates() -> None:
    seed = _video("seed0000001", title="Python Asyncio")
    candidates = [
        seed,
        _video("priv0000001", title="Python Asyncio Private", privacy_status="private", is_available=False),
        _video("dele0000001", title="Python Asyncio Deleted", privacy_status="deleted", is_available=False),
        _video("live0000001", title="Python Asyncio Live", live_broadcast_content="live", duration_seconds=0),
        _video("good0000001", title="Python Asyncio Coroutines"),
    ]
    assert not is_eligible_candidate(candidates[1], seed_video_id=seed.video_id)
    result = rank_similar_videos(seed, candidates, max_results=10)
    assert result.total_candidates_evaluated == 1
    assert result.excluded_count == 4
    assert [r.video.video_id for r in result.ranked_videos] == ["good0000001"]


def test_UT_SIM_deterministic_tie_breaking_and_duration_similarity() -> None:
    assert compute_duration_similarity(600, 600) == pytest.approx(1.0)
    assert compute_duration_similarity(600, 0) == 0.0
    assert compute_duration_similarity(None, 600) == 0.0

    seed = _video("seed0000001", title="Rust Ownership Model", tags=("rust",))
    cand_b = _video("candB000001", title="Rust Ownership Model", tags=("rust",))
    cand_a = _video("candA000001", title="Rust Ownership Model", tags=("rust",))

    result = rank_similar_videos(seed, [cand_b, cand_a], max_results=2)
    assert [item.video.video_id for item in result.ranked_videos] == [
        "candA000001",
        "candB000001",
    ]


def test_UT_SIM_scoring_weights_validation_rejects_invalid_and_zero_sum() -> None:
    weights = resolve_video_similarity_weights({"title": 0.8, "tags": 0.2})
    assert weights["title"] == pytest.approx(0.8)

    with pytest.raises(ToolError) as exc_info:
        resolve_video_similarity_weights(
            {"title": 0.0, "tags": 0.0, "description": 0.0, "category": 0.0, "duration": 0.0}
        )
    assert exc_info.value.code is ErrorCode.INVALID_ARGUMENT

    with pytest.raises(ToolError) as exc_unknown:
        resolve_video_similarity_weights({"view_count": 1.0})
    assert exc_unknown.value.code is ErrorCode.INVALID_ARGUMENT
