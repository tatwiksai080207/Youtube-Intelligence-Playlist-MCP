"""Unit tests for objective recommendation scoring and attribution (FR-3.3, INV-01)."""

# ruff: noqa: N802
from __future__ import annotations

from datetime import UTC, datetime

from yt_intel_mcp.analysis.profile import build_interest_profile
from yt_intel_mcp.analysis.recommend import score_recommendations
from yt_intel_mcp.models import EventSource, EventTimeKind, UserEvent, VideoMeta


def test_FR3_score_recommendations_excludes_seen_and_unavailable_and_adds_reason() -> None:
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    events = [
        UserEvent(
            source=EventSource.LIKED_VIDEO,
            time_kind=EventTimeKind.DATED,
            event_time=now,
            video_id="seenVid0001",
            channel_id="UC_PY",
            title="Python Asyncio Internals",
            category_id="28",
            tags=("python", "asyncio"),
        )
    ]
    profile = build_interest_profile(events, now_utc=now)

    candidates = [
        VideoMeta(
            video_id="seenVid0001",
            title="Python Asyncio Internals",
            channel_id="UC_PY",
            category_id="28",
            tags=("python", "asyncio"),
        ),
        VideoMeta(
            video_id="privVid0002",
            title="Python Asyncio Private",
            privacy_status="private",
            is_available=False,
        ),
        VideoMeta(
            video_id="recNew00003",
            title="Structured Concurrency with Python Asyncio",
            channel_id="UC_PY",
            channel_title="Systems Craft",
            category_id="28",
            category_name="Science & Technology",
            duration_seconds=540,
            tags=("python", "asyncio"),
        ),
        VideoMeta(
            video_id="recOther004",
            title="Sourdough Baking Basics",
            channel_id="UC_BAKE",
            channel_title="Bread Lab",
            category_id="26",
            category_name="Howto & Style",
            duration_seconds=480,
            tags=("baking",),
        ),
    ]

    result = score_recommendations(profile, candidates, max_results=5)
    assert result.excluded_seen_count == 1
    assert result.excluded_unavailable_count == 1
    assert [r.video.video_id for r in result.recommendations] == ["recNew00003", "recOther004"]
    top = result.recommendations[0]
    assert "python" in top.matched_terms
    assert "Matches your interest in" in top.reason
    serialized = top.to_dict()
    assert serialized["video_id"] == "recNew00003"
    assert serialized["duration_human"] == "9m"
