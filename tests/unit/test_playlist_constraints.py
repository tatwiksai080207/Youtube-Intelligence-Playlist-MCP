"""Unit tests for MF-08 playlist constraint model and duration window logic (UT_SOLV_WINDOW)."""

# ruff: noqa: N802
from __future__ import annotations

import pytest

from yt_intel_mcp.config import PlaylistConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.playlist import (
    PlaylistConstraints,
    build_playlist_constraints,
    evaluate_selection_constraints,
    is_total_in_window,
    is_video_duration_eligible,
)


def _video(
    video_id: str,
    duration_seconds: int | None,
    *,
    is_available: bool = True,
    privacy_status: str = "public",
    live_broadcast_content: str = "none",
) -> VideoMeta:
    return VideoMeta(
        video_id=video_id,
        title=f"Video {video_id}",
        duration_seconds=duration_seconds,
        is_available=is_available,
        privacy_status=privacy_status,
        live_broadcast_content=live_broadcast_content,
    )


def test_UT_SOLV_WINDOW_120m_5pct_window_endpoints_and_rejections() -> None:
    constraints = build_playlist_constraints(
        topic="python asyncio",
        target_total_minutes=120,
        tolerance_percent=5,
        max_video_minutes=20,
    )
    assert constraints.target_min_seconds == 6840  # 114:00
    assert constraints.target_max_seconds == 7200  # 120:00
    assert constraints.max_video_seconds == 1200  # 20:00
    assert constraints.max_videos == 25
    assert constraints.privacy_status == "private"
    assert constraints.allow_unknown_language is False

    # Exact endpoints accepted, adjacent out-of-window totals rejected (INV-09)
    assert is_total_in_window(6840, constraints) is True
    assert is_total_in_window(7020, constraints) is True
    assert is_total_in_window(7200, constraints) is True
    assert is_total_in_window(6839, constraints) is False  # 113:59
    assert is_total_in_window(7201, constraints) is False  # 120:01
    assert is_total_in_window(0, constraints) is False
    assert is_total_in_window(True, constraints) is False


def test_UT_SOLV_WINDOW_decimal_tolerance_avoids_float_drift() -> None:
    # 100m = 6000s, 29% tol => 6000 * 0.71 = 4260s exact (naive float gives 4260.000000000001)
    constraints = build_playlist_constraints(
        topic="algorithms",
        target_total_minutes=100,
        tolerance_percent=29,
    )
    assert constraints.target_max_seconds == 6000
    assert constraints.target_min_seconds == 4260
    assert is_total_in_window(4260, constraints) is True
    assert is_total_in_window(4259, constraints) is False

    # Zero tolerance requires exact match to T
    exact = build_playlist_constraints(topic="exact", target_total_minutes=30, tolerance_percent=0)
    assert exact.target_min_seconds == 1800
    assert exact.target_max_seconds == 1800
    assert is_total_in_window(1800, exact) is True
    assert is_total_in_window(1799, exact) is False
    assert is_total_in_window(1801, exact) is False


def test_UT_SOLV_WINDOW_inclusive_max_video_minutes_and_availability() -> None:
    constraints = build_playlist_constraints(
        topic="compilers",
        target_total_minutes=120,
        max_video_minutes=20,
    )
    assert is_video_duration_eligible(_video("V_EXACT", 1200), constraints) is True  # 20:00
    assert is_video_duration_eligible(_video("V_MIN", 1), constraints) is True
    assert is_video_duration_eligible(_video("V_OVER", 1201), constraints) is False  # 20:01
    assert is_video_duration_eligible(_video("V_ZERO", 0), constraints) is False
    assert is_video_duration_eligible(_video("V_NONE", None), constraints) is False
    assert (
        is_video_duration_eligible(
            _video("V_LIVE", 600, live_broadcast_content="live"), constraints
        )
        is False
    )
    assert (
        is_video_duration_eligible(_video("V_PRIV", 600, privacy_status="private"), constraints)
        is False
    )
    assert (
        is_video_duration_eligible(_video("V_UNAVAIL", 600, is_available=False), constraints)
        is False
    )
    assert (
        is_video_duration_eligible(
            _video("V_UNLISTED", 600, privacy_status="unlisted"), constraints
        )
        is True
    )

    # When max_video_minutes exceeds target_total_minutes, effective cap is target_max_seconds
    capped = build_playlist_constraints(
        topic="short list",
        target_total_minutes=15,
        max_video_minutes=30,
    )
    assert capped.max_video_seconds == 1800
    assert capped.effective_max_video_seconds == 900
    assert is_video_duration_eligible(_video("V_OK", 900), capped) is True
    assert is_video_duration_eligible(_video("V_TOO_LONG", 901), capped) is False


def test_UT_SOLV_WINDOW_max_videos_is_upper_bound_and_selection_evaluation() -> None:
    constraints = build_playlist_constraints(
        topic="distributed systems",
        target_total_minutes=120,
        tolerance_percent=5,
        max_video_minutes=45,
        max_videos=25,
    )
    # Only 3 videos (< 25 max_videos) totaling 6840s (114:00) satisfies all constraints
    valid_trio = [
        _video("V1", 2400),
        _video("V2", 2220),
        _video("V3", 2220),
    ]
    assert evaluate_selection_constraints(valid_trio, constraints) == []

    # Empty, below floor, above ceiling, over count, and ineligible video failures
    assert evaluate_selection_constraints([], constraints) == ["empty_selection"]
    assert evaluate_selection_constraints([_video("V1", 2400)], constraints) == [
        "below_target_duration_floor"
    ]
    assert evaluate_selection_constraints(
        [_video("V1", 2700), _video("V2", 2700), _video("V3", 2000)], constraints
    ) == ["exceeds_target_duration_ceiling"]
    assert "video_ineligible" in evaluate_selection_constraints(
        [_video("V1", 2701), _video("V2", 2400), _video("V3", 2000)], constraints
    )

    tight_count = build_playlist_constraints(
        topic="tight",
        target_total_minutes=10,
        max_videos=2,
    )
    assert evaluate_selection_constraints(
        [_video("A", 200), _video("B", 200), _video("C", 200)], tight_count
    ) == ["exceeds_max_videos"]


def test_UT_SOLV_WINDOW_config_defaults_and_direct_dataclass_guards() -> None:
    custom_cfg = PlaylistConfig(
        duration_tolerance_fraction=0.10,
        default_max_videos=12,
        default_privacy_status="unlisted",
        allow_unknown_language=True,
    )
    constraints = build_playlist_constraints(
        topic="rust",
        target_total_minutes=60,
        language="en-US",
        title="Rust Essentials",
        config=custom_cfg,
    )
    assert constraints.tolerance_percent == pytest.approx(10.0)
    assert constraints.target_min_seconds == 3240
    assert constraints.target_max_seconds == 3600
    assert constraints.effective_max_video_seconds == 3600
    assert constraints.max_videos == 12
    assert constraints.privacy_status == "unlisted"
    assert constraints.allow_unknown_language is True
    assert constraints.language == "en-US"
    assert constraints.title == "Rust Essentials"

    with pytest.raises(ValueError, match="target_max_seconds"):
        PlaylistConstraints("t", 1, 5, None, 10, None, False, None, "private", 0, 0, None)
    with pytest.raises(ValueError, match="target_min_seconds"):
        PlaylistConstraints("t", 1, 5, None, 10, None, False, None, "private", 100, 60, None)
    with pytest.raises(ValueError, match="max_video_seconds"):
        PlaylistConstraints("t", 1, 5, 1, 10, None, False, None, "private", 50, 60, 0)
    with pytest.raises(ValueError, match="max_videos"):
        PlaylistConstraints("t", 1, 5, None, 0, None, False, None, "private", 50, 60, None)


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"topic": "", "target_total_minutes": 60}, "topic"),
        ({"topic": "   ", "target_total_minutes": 60}, "topic"),
        ({"topic": 123, "target_total_minutes": 60}, "topic"),
        ({"topic": "ok\x00bad", "target_total_minutes": 60}, "topic"),
        ({"topic": "x" * 301, "target_total_minutes": 60}, "topic"),
        ({"topic": "python", "target_total_minutes": 0}, "target_total_minutes"),
        ({"topic": "python", "target_total_minutes": 601}, "target_total_minutes"),
        ({"topic": "python", "target_total_minutes": True}, "target_total_minutes"),
        (
            {"topic": "python", "target_total_minutes": 60, "tolerance_percent": -1},
            "tolerance_percent",
        ),
        (
            {"topic": "python", "target_total_minutes": 60, "tolerance_percent": 51},
            "tolerance_percent",
        ),
        (
            {"topic": "python", "target_total_minutes": 60, "max_video_minutes": 0.5},
            "max_video_minutes",
        ),
        ({"topic": "python", "target_total_minutes": 60, "max_videos": 0}, "max_videos"),
        ({"topic": "python", "target_total_minutes": 60, "max_videos": 51}, "max_videos"),
        ({"topic": "python", "target_total_minutes": 60, "max_videos": 5.5}, "max_videos"),
        ({"topic": "python", "target_total_minutes": 60, "language": "english words"}, "language"),
        ({"topic": "python", "target_total_minutes": 60, "language": "x"}, "language"),
        (
            {"topic": "python", "target_total_minutes": 60, "allow_unknown_language": "yes"},
            "allow_unknown_language",
        ),
        ({"topic": "python", "target_total_minutes": 60, "title": "t" * 151}, "title"),
        (
            {"topic": "python", "target_total_minutes": 60, "privacy_status": "friends"},
            "privacy_status",
        ),
    ],
)
def test_NT_VAL_invalid_playlist_constraints_raise_invalid_argument(
    kwargs: dict[str, object], field: str
) -> None:
    with pytest.raises(ToolError) as exc_info:
        build_playlist_constraints(**kwargs)
    assert exc_info.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc_info.value.details["field"] == field
