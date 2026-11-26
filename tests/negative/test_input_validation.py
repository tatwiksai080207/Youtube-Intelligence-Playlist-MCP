"""Negative tests for strict pre-quota input validation (NT_VAL, INV-02, NFR-5)."""

# ruff: noqa: N802
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from yt_intel_mcp.config import QuotaConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import CostEstimate, QuotaUsed
from yt_intel_mcp.provider import FixtureYouTubeProvider
from yt_intel_mcp.quota.guard import QuotaStatus
from yt_intel_mcp.validation import (
    extract_channel_id,
    extract_playlist_id,
    extract_video_id,
    validate_float_range,
    validate_int_range,
    validate_max_results,
    validate_scoring_weights,
    validate_sources,
    validate_timeframe,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class _SpyQuotaGuard:
    """Spy guard asserting zero preflight or charge calls on invalid input."""

    def __init__(self) -> None:
        self.preflights: list[CostEstimate] = []
        self.charges: list[CostEstimate] = []
        cfg = QuotaConfig()
        self._status = QuotaStatus(
            units_used=0,
            units_limit=cfg.daily_units_limit,
            units_remaining=cfg.daily_units_limit,
            search_calls_used=0,
            search_calls_limit=cfg.daily_search_limit,
            search_calls_remaining=cfg.daily_search_limit,
            reset_at=datetime(2026, 11, 27, 8, 0, tzinfo=UTC),
            upstream_exhausted=False,
        )

    def estimate(self, operation: str, *, count: int = 1) -> CostEstimate:
        return CostEstimate(units=count, search_calls=0, operation=operation)

    def preflight(self, cost: CostEstimate) -> QuotaStatus:
        self.preflights.append(cost)
        return self._status

    def charge(self, cost: CostEstimate) -> QuotaStatus:
        self.charges.append(cost)
        return self._status

    def mark_upstream_exhausted(self, reset_at: datetime | None = None) -> QuotaStatus:
        del reset_at
        return self._status

    def status(self) -> QuotaStatus:
        return self._status


@pytest.mark.parametrize(
    "bad_video",
    [
        "",
        "   ",
        "too_short",
        "way_too_long_1234",
        "dQw4w9WgXc!",
        "dQw4 w9WgXc",
        "dQw4w9WgXcQ\n",
        "x" * 513,
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://evil.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
        "https://not-youtube.com/dQw4w9WgXcQ",
        "https://user@www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com:8443/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com:invalid/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&v=other123456",
        "https://youtu.be/dQw4w9WgXcQ/extra",
        "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw",
        "youtube.com/watch?v=dQw4w9WgXcQ",
    ],
)
def test_NT_VAL_invalid_video_inputs_raise_invalid_argument(bad_video: str) -> None:
    with pytest.raises(ToolError) as exc_info:
        extract_video_id(bad_video)
    assert exc_info.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc_info.value.quota_used == QuotaUsed(units=0, search_calls=0)


@pytest.mark.parametrize(
    "bad_channel",
    [
        "",
        "   ",
        "@",
        "@ab",
        "@bad..handle",
        "@handle with space",
        "UC_short",
        "PLuAXFkgsw1L7xaCfnd5JJOw",
        "x" * 513,
        "https://evil.com/@SystemsCraft",
        "https://youtu.be/@SystemsCraft",
        "https://www.youtube.com/c/SystemsCraft",
        "https://www.youtube.com/user/SystemsCraft",
        "https://www.youtube.com/channel/UC_invalid",
        "https://www.youtube.com/@ab/videos",
        "https://www.youtube.com/@SystemsCraft/unknown_tab",
        "https://user:pass@www.youtube.com/@SystemsCraft",
    ],
)
def test_NT_VAL_invalid_channel_inputs_raise_invalid_argument(bad_channel: str) -> None:
    with pytest.raises(ToolError) as exc_info:
        extract_channel_id(bad_channel)
    assert exc_info.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc_info.value.quota_used == QuotaUsed(units=0, search_calls=0)


@pytest.mark.parametrize(
    "bad_playlist",
    [
        "",
        "PL_123",
        "XX1234567890abcdef",
        "https://evil.com/playlist?list=PL1234567890abcdef",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1234567890abcdef",
        "https://www.youtube.com/playlist?list=bad",
    ],
)
def test_NT_VAL_invalid_playlist_inputs_raise_invalid_argument(bad_playlist: str) -> None:
    with pytest.raises(ToolError) as exc_info:
        extract_playlist_id(bad_playlist)
    assert exc_info.value.code is ErrorCode.INVALID_ARGUMENT


@pytest.mark.parametrize("bad_max", [0, -1, 51, 100, True, False, "10", 5.5, None])
def test_NT_VAL_invalid_max_results_rejected(bad_max: Any) -> None:
    with pytest.raises(ToolError) as exc_info:
        validate_max_results(bad_max)
    assert exc_info.value.code is ErrorCode.INVALID_ARGUMENT


def test_NT_VAL_invalid_numeric_weights_sources_and_timeframe_rejected() -> None:
    with pytest.raises(ToolError) as err_int:
        validate_int_range(True, "limit", minimum=1, maximum=10)
    assert err_int.value.code is ErrorCode.INVALID_ARGUMENT

    for bad_float in (float("nan"), float("inf"), -0.1, 1.1, True, "0.5"):
        with pytest.raises(ToolError) as err_flt:
            validate_float_range(bad_float, "weight", minimum=0.0, maximum=1.0)
        assert err_flt.value.code is ErrorCode.INVALID_ARGUMENT

    for bad_weights in (
        {},
        "title",
        {"view_count": 0.5},
        {"like_count": 0.2, "title": 0.8},
        {"title": 0.0, "tags": 0.0},
        {"title": -0.5},
    ):
        with pytest.raises(ToolError) as err_w:
            validate_scoring_weights(bad_weights)
        assert err_w.value.code is ErrorCode.INVALID_ARGUMENT

    for bad_sources in (
        [],
        "liked_video",
        ["watch_history"],
        ["liked_video", "liked_video"],
        [123],
    ):
        with pytest.raises(ToolError) as err_src:
            validate_sources(bad_sources)
        assert err_src.value.code is ErrorCode.INVALID_ARGUMENT

    for bad_tf in ("1d", "all_time", 90, None):
        with pytest.raises(ToolError) as err_tf:
            validate_timeframe(bad_tf)
        assert err_tf.value.code is ErrorCode.INVALID_ARGUMENT


def test_NT_VAL_validation_rejection_spends_zero_quota_and_zero_provider_calls() -> None:
    guard = _SpyQuotaGuard()
    provider = FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=guard)

    async def pre_quota_video_lookup(raw_video: str) -> dict[str, Any]:
        try:
            video_id = extract_video_id(raw_video)
        except ToolError as err:
            return err.to_envelope()
        guard.preflight(guard.estimate("videos.list"))
        await provider.get_videos([video_id])
        return {"ok": True}

    envelope = asyncio.run(pre_quota_video_lookup("https://evil.com/watch?v=dQw4w9WgXcQ"))
    assert envelope["code"] == "INVALID_ARGUMENT"
    assert envelope["quota_used"] == {"units": 0, "search_calls": 0}
    assert guard.preflights == []
    assert guard.charges == []
    assert provider.calls == []
    assert provider.total_quota_used == QuotaUsed()
