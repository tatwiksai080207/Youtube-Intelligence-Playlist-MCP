"""Unit tests for engagement buckets, zero/live exclusion, and period comparisons (TS-14)."""

# ruff: noqa: N802
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from yt_intel_mcp.analysis.engagement import (
    WATCH_HISTORY_DISCLAIMER,
    analyze_engagement_events,
    classify_duration_bucket,
)
from yt_intel_mcp.models import EventSource, EventTimeKind, UserEvent


def test_UT_STAT_BUCKET_exact_duration_boundaries() -> None:
    assert classify_duration_bucket(239) == "short"
    assert classify_duration_bucket(240) == "medium"
    assert classify_duration_bucket(1200) == "medium"
    assert classify_duration_bucket(1201) == "long"
    assert classify_duration_bucket(0) == "excluded"
    assert classify_duration_bucket(None) == "excluded"


def test_UT_STAT_ZERO_excludes_live_and_zero_from_buckets_and_median() -> None:
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    events = [
        UserEvent(
            source=EventSource.PLAYLIST_ITEM,
            time_kind=EventTimeKind.DATED,
            event_time=now - timedelta(days=1),
            video_id="vidShort001",
            title="Short Clip",
            duration_seconds=239,
            category_id="28",
        ),
        UserEvent(
            source=EventSource.PLAYLIST_ITEM,
            time_kind=EventTimeKind.DATED,
            event_time=now - timedelta(days=2),
            video_id="vidMed00002",
            title="Medium Talk",
            duration_seconds=240,
            category_id="28",
        ),
        UserEvent(
            source=EventSource.PLAYLIST_ITEM,
            time_kind=EventTimeKind.DATED,
            event_time=now - timedelta(days=3),
            video_id="vidLong0003",
            title="Long Lecture",
            duration_seconds=1201,
            category_id="27",
        ),
        UserEvent(
            source=EventSource.LIKED_VIDEO,
            time_kind=EventTimeKind.UNDATED,
            video_id="vidLive0004",
            title="Live Stream",
            duration_seconds=0,
        ),
    ]

    result = analyze_engagement_events(
        events,
        timeframe="30d",
        category_names={"28": "Science & Technology", "27": "Education"},
        now_utc=now,
    )
    buckets = result.duration_buckets
    assert buckets.short_count == 1
    assert buckets.medium_count == 1
    assert buckets.long_count == 1
    assert buckets.excluded_live_or_zero_count == 1
    assert buckets.median_seconds == pytest.approx(240.0)
    assert result.watch_history_disclaimer == WATCH_HISTORY_DISCLAIMER


def test_UT_STAT_TS_period_comparisons_and_cadence_guard() -> None:
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)

    # Undated / first_observed only -> no_activity in dated window and insufficient_dated_data.
    undated_only = [
        UserEvent(
            source=EventSource.LIKED_VIDEO,
            time_kind=EventTimeKind.UNDATED,
            video_id="vidU0000001",
            title="Undated Like",
            duration_seconds=300,
        ),
        UserEvent(
            source=EventSource.LIKED_VIDEO,
            time_kind=EventTimeKind.FIRST_OBSERVED,
            video_id="vidF0000002",
            title="First Observed Like",
            duration_seconds=300,
        ),
    ]
    res_no_act = analyze_engagement_events(undated_only, timeframe="30d", now_utc=now)
    assert res_no_act.period_comparison.status == "no_activity"
    assert res_no_act.period_comparison.percent_delta is None
    assert res_no_act.cadence_status == "insufficient_dated_data"
    assert res_no_act.monthly_trends == ()
    assert res_no_act.timestamp_coverage.to_dict() == {
        "total": 2,
        "dated": 0,
        "undated": 1,
        "first_observed": 1,
    }

    # Current window has 2 dated events, previous has 0 -> new_activity, <5 cadence guard.
    new_act_events = [
        UserEvent(
            source=EventSource.PLAYLIST_ITEM,
            time_kind=EventTimeKind.DATED,
            event_time=now - timedelta(days=i + 1),
            video_id=f"vidN000000{i}",
            title=f"Python Talk {i}",
            duration_seconds=400,
        )
        for i in range(2)
    ]
    res_new = analyze_engagement_events(new_act_events, timeframe="30d", now_utc=now)
    assert res_new.period_comparison.status == "new_activity"
    assert res_new.cadence_status == "insufficient_dated_data"

    # Sufficient dated data (6 in current, 4 in previous -> +50.0% delta).
    compared_events = [
        UserEvent(
            source=EventSource.PLAYLIST_ITEM,
            time_kind=EventTimeKind.DATED,
            event_time=now - timedelta(days=i + 1),
            video_id=f"vidC000000{i}",
            title=f"Python Asyncio {i}",
            duration_seconds=500,
        )
        for i in range(6)
    ] + [
        UserEvent(
            source=EventSource.PLAYLIST_ITEM,
            time_kind=EventTimeKind.DATED,
            event_time=now - timedelta(days=35 + i),
            video_id=f"vidP000000{i}",
            title=f"Rust Systems {i}",
            duration_seconds=500,
        )
        for i in range(4)
    ]
    res_cmp = analyze_engagement_events(compared_events, timeframe="30d", now_utc=now)
    assert res_cmp.cadence_status == "sufficient_data"
    assert res_cmp.period_comparison.status == "compared"
    assert res_cmp.period_comparison.percent_delta == pytest.approx(50.0)
