"""Unit tests for 90-day half-life interest profile builder (UT_PROF, FR-3.2, INV-05)."""

# ruff: noqa: N802
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from yt_intel_mcp.analysis.profile import (
    build_interest_profile,
    compute_event_weight,
    deduplicate_events,
)
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import EventSource, EventTimeKind, UserEvent


def test_UT_PROF_half_life_decay_and_neutral_undated_weights() -> None:
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)

    ev_today = UserEvent(
        source=EventSource.PLAYLIST_ITEM,
        time_kind=EventTimeKind.DATED,
        event_time=now,
        video_id="vidToday001",
        title="Python Asyncio",
    )
    ev_90d = UserEvent(
        source=EventSource.PLAYLIST_ITEM,
        time_kind=EventTimeKind.DATED,
        event_time=now - timedelta(days=90),
        video_id="vid90d00001",
        title="Rust Systems",
    )
    ev_180d = UserEvent(
        source=EventSource.PLAYLIST_ITEM,
        time_kind=EventTimeKind.DATED,
        event_time=now - timedelta(days=180),
        video_id="vid180d0001",
        title="C++ Concurrency",
    )
    ev_undated = UserEvent(
        source=EventSource.LIKED_VIDEO,
        time_kind=EventTimeKind.UNDATED,
        video_id="vidUndated1",
        title="SQLite Internals",
    )
    ev_first_obs = UserEvent(
        source=EventSource.LIKED_VIDEO,
        time_kind=EventTimeKind.FIRST_OBSERVED,
        video_id="vidFirstOb1",
        title="Distributed Consensus",
    )

    assert compute_event_weight(ev_today, now_utc=now) == pytest.approx(1.0)
    assert compute_event_weight(ev_90d, now_utc=now) == pytest.approx(0.5)
    assert compute_event_weight(ev_180d, now_utc=now) == pytest.approx(0.25)
    assert compute_event_weight(ev_undated, now_utc=now) == pytest.approx(0.5)
    assert compute_event_weight(ev_first_obs, now_utc=now) == pytest.approx(0.5)


def test_UT_PROF_cross_source_dedup_uses_max_weight_and_merges_sources() -> None:
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    liked_undated = UserEvent(
        source=EventSource.LIKED_VIDEO,
        time_kind=EventTimeKind.UNDATED,
        video_id="vidShared01",
        channel_id="UC_SHARED",
        title="Deterministic MCP Servers",
        category_id="28",
        tags=("python", "mcp"),
    )
    playlist_recent = UserEvent(
        source=EventSource.PLAYLIST_ITEM,
        time_kind=EventTimeKind.DATED,
        event_time=now - timedelta(days=1),
        video_id="vidShared01",
        channel_id="UC_SHARED",
        playlist_id="PL_MAIN",
        title="Deterministic MCP Servers",
        category_id="28",
        tags=("python", "mcp"),
    )

    deduped = deduplicate_events([liked_undated, playlist_recent], now_utc=now)
    assert len(deduped) == 1
    assert deduped[0].weight > 0.99
    assert set(deduped[0].sources) == {EventSource.LIKED_VIDEO, EventSource.PLAYLIST_ITEM}


def test_UT_PROF_build_interest_profile_ranks_terms_queries_and_exclusions() -> None:
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    events = [
        UserEvent(
            source=EventSource.PLAYLIST_ITEM,
            time_kind=EventTimeKind.DATED,
            event_time=now,
            video_id="vidPy000001",
            channel_id="UC_PY",
            title="Python Asyncio Coroutines",
            category_id="28",
            tags=("python", "asyncio"),
        ),
        UserEvent(
            source=EventSource.SUBSCRIPTION,
            time_kind=EventTimeKind.DATED,
            event_time=now - timedelta(days=90),
            channel_id="UC_RUST",
            title="Rust Systems Engineering",
            tags=("rust",),
        ),
        UserEvent(
            source=EventSource.LIKED_VIDEO,
            time_kind=EventTimeKind.UNDATED,
            video_id="vidPy000002",
            channel_id="UC_PY",
            title="Python Structured Concurrency",
            category_id="28",
            tags=("python",),
        ),
    ]

    profile = build_interest_profile(events, now_utc=now, max_queries=3)
    assert profile.top_terms[0] == "python"
    assert profile.term_weights["python"] == pytest.approx(1.5)
    assert profile.category_weights["28"] == pytest.approx(1.5)
    assert profile.channel_weights["UC_PY"] == pytest.approx(1.5)
    assert profile.excluded_video_ids == frozenset({"vidPy000001", "vidPy000002"})
    assert 1 <= len(profile.search_queries) <= 3
    assert profile.coverage.to_dict() == {
        "total": 3,
        "dated": 2,
        "undated": 1,
        "first_observed": 0,
    }


def test_UT_PROF_empty_signals_raises_insufficient_user_signal() -> None:
    with pytest.raises(ToolError) as exc_info:
        build_interest_profile([])
    assert exc_info.value.code is ErrorCode.INSUFFICIENT_USER_SIGNAL
