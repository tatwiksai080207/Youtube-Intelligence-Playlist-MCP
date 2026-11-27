"""Unit tests for strict event-time extraction and first_observed provenance (UT_STAT_TS)."""

# ruff: noqa: N802
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from yt_intel_mcp.analysis.events import (
    events_from_liked_videos,
    extract_event_time_from_record,
    normalize_user_event,
    normalize_user_events,
    summarize_timestamp_coverage,
)
from yt_intel_mcp.models import EventSource, EventTimeKind, UserEvent, VideoMeta
from yt_intel_mcp.store import SQLiteStore


def test_UT_STAT_TS_extract_event_time_enforces_inv04_allow_list() -> None:
    sub_record = {"snippet": {"publishedAt": "2026-10-01T12:00:00Z"}}
    assert extract_event_time_from_record(EventSource.SUBSCRIPTION, sub_record) == datetime(
        2026, 10, 1, 12, 0, tzinfo=UTC
    )

    # playlist_item MUST read snippet.publishedAt and NEVER contentDetails.videoPublishedAt.
    pi_dated = {
        "snippet": {"publishedAt": "2026-10-15T08:00:00Z"},
        "contentDetails": {"videoPublishedAt": "2020-01-01T00:00:00Z"},
    }
    assert extract_event_time_from_record(EventSource.PLAYLIST_ITEM, pi_dated) == datetime(
        2026, 10, 15, 8, 0, tzinfo=UTC
    )

    pi_missing_action_time = {
        "snippet": {"title": "Saved video"},
        "contentDetails": {"videoPublishedAt": "2020-01-01T00:00:00Z"},
    }
    assert extract_event_time_from_record(EventSource.PLAYLIST_ITEM, pi_missing_action_time) is None

    # videos.list(myRating='like') carries global video upload date -> MUST return None.
    liked_video_resource = {
        "kind": "youtube#video",
        "snippet": {"publishedAt": "2022-05-01T00:00:00Z"},
    }
    assert extract_event_time_from_record(EventSource.LIKED_VIDEO, liked_video_resource) is None

    # Likes playlist item carries user action timestamp -> extracted.
    likes_playlist_item = {
        "kind": "youtube#playlistItem",
        "snippet": {"playlistId": "LL123", "publishedAt": "2026-11-10T09:30:00Z"},
        "contentDetails": {"videoPublishedAt": "2019-01-01T00:00:00Z"},
    }
    assert extract_event_time_from_record(EventSource.LIKED_VIDEO, likes_playlist_item) == datetime(
        2026, 11, 10, 9, 30, tzinfo=UTC
    )


def test_UT_STAT_TS_liked_videos_never_copy_upload_date_and_first_observed_policy(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "obs.db")
    t1 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
    t2 = t1 + timedelta(days=5)

    videos = [
        VideoMeta(
            video_id="vidLike0001",
            title="Rust Async Runtime",
            channel_id="UC_RUST_01",
            published_at=datetime(2021, 1, 1, 0, 0, tzinfo=UTC),
            tags=("rust", "async"),
            category_id="28",
            duration_seconds=900,
        )
    ]

    first_pass = events_from_liked_videos(videos, store=store, now_utc=t1)
    assert len(first_pass) == 1
    assert first_pass[0].event_time is None
    assert first_pass[0].time_kind is EventTimeKind.UNDATED

    second_pass = events_from_liked_videos(videos, store=store, now_utc=t2)
    assert len(second_pass) == 1
    assert second_pass[0].event_time is None
    assert second_pass[0].time_kind is EventTimeKind.FIRST_OBSERVED

    # Revoke/purge clears first_observed so next observation starts fresh as UNDATED.
    store.purge_personal_data()
    third_pass = events_from_liked_videos(videos, store=store, now_utc=t2)
    assert third_pass[0].time_kind is EventTimeKind.UNDATED


def test_UT_STAT_TS_normalize_and_coverage_summary() -> None:
    dated_ev = UserEvent(
        source=EventSource.SUBSCRIPTION,
        time_kind=EventTimeKind.DATED,
        event_time=datetime(2026, 11, 20, 12, 0, tzinfo=UTC),
        channel_id="UC_SUB_01",
        title="Systems Craft",
    )
    undated_ev = UserEvent(
        source=EventSource.LIKED_VIDEO,
        time_kind=EventTimeKind.UNDATED,
        video_id="vid00000001",
        title="Asyncio Deep Dive",
    )
    first_obs_ev = UserEvent(
        source=EventSource.LIKED_VIDEO,
        time_kind=EventTimeKind.FIRST_OBSERVED,
        video_id="vid00000002",
        title="SQLite WAL",
    )
    normalized = normalize_user_events([dated_ev, undated_ev, first_obs_ev])
    coverage = summarize_timestamp_coverage(normalized)
    assert coverage.to_dict() == {
        "total": 3,
        "dated": 1,
        "undated": 1,
        "first_observed": 1,
    }

    # Event tagged DATED with None event_time degrades safely to UNDATED.
    broken = normalize_user_event(
        UserEvent(source=EventSource.PLAYLIST_ITEM, time_kind=EventTimeKind.DATED, event_time=None)
    )
    assert broken.time_kind is EventTimeKind.UNDATED
