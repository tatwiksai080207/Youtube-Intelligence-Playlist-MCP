"""Strict event-time extraction and first_observed provenance (TS-12, FR-3.1, INV-04, ADR-0007)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from yt_intel_mcp.models import EventSource, EventTimeKind, UserEvent, VideoMeta
from yt_intel_mcp.sanitize import sanitize_single_line
from yt_intel_mcp.store import SQLiteStore

__all__ = [
    "TimestampCoverage",
    "events_from_liked_videos",
    "extract_event_time_from_record",
    "normalize_user_event",
    "normalize_user_events",
    "summarize_timestamp_coverage",
]


@dataclass(frozen=True, slots=True)
class TimestampCoverage:
    """Breakdown of event timestamp provenance across user signals (FR-4.3, ADR-0007)."""

    total: int
    dated: int
    undated: int
    first_observed: int

    def to_dict(self) -> dict[str, int]:
        """Serialize timestamp coverage counts."""
        return {
            "total": self.total,
            "dated": self.dated,
            "undated": self.undated,
            "first_observed": self.first_observed,
        }


def _parse_utc_datetime(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.astimezone(UTC) if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def extract_event_time_from_record(
    source: EventSource,
    record: Mapping[str, Any],
) -> datetime | None:
    """Extract ONLY explicit user-action timestamps per INV-04.

    Prohibited fields (NEVER read):
    - ``videos.snippet.publishedAt`` (global video upload time)
    - ``playlistItems.contentDetails.videoPublishedAt`` (global video upload time)
    """
    snippet = record.get("snippet")
    if not isinstance(snippet, Mapping):
        return None

    if source in (EventSource.SUBSCRIPTION, EventSource.PLAYLIST_ITEM):
        return _parse_utc_datetime(snippet.get("publishedAt"))

    # LIKED_VIDEO: only playlistItems from the likes playlist carry user-action time.
    # A videos.list(myRating='like') item has kind='youtube#video' whose snippet.publishedAt
    # is the video's global upload timestamp, which MUST NEVER be treated as event_time.
    kind = str(record.get("kind", "")).strip()
    if kind == "youtube#video" or bool(record.get("is_video_resource", False)):
        return None
    if kind == "youtube#playlistItem" or "playlistId" in snippet or "resourceId" in snippet:
        return _parse_utc_datetime(snippet.get("publishedAt"))
    return None


def _resolve_item_id(event: UserEvent) -> str | None:
    if event.source is EventSource.SUBSCRIPTION:
        return event.channel_id
    return event.video_id or event.channel_id


def _lookup_or_record_first_observed(
    store: SQLiteStore,
    *,
    source: EventSource,
    item_id: str,
    now_utc: datetime,
) -> EventTimeKind:
    now_iso = now_utc.astimezone(UTC).isoformat()
    with store.transaction(immediate=True) as conn:
        row = conn.execute(
            """
            SELECT first_observed_utc
            FROM first_observed
            WHERE source = ? AND item_id = ?;
            """,
            (source.value, item_id),
        ).fetchone()
        if row is not None:
            return EventTimeKind.FIRST_OBSERVED
        conn.execute(
            """
            INSERT INTO first_observed (source, item_id, first_observed_utc)
            VALUES (?, ?, ?);
            """,
            (source.value, item_id, now_iso),
        )
        return EventTimeKind.UNDATED


def normalize_user_event(
    event: UserEvent,
    *,
    store: SQLiteStore | None = None,
    now_utc: datetime | None = None,
) -> UserEvent:
    """Normalize event_time to UTC and apply ADR-0007 G-05 first_observed provenance."""
    reference_now = (now_utc or datetime.now(UTC)).astimezone(UTC)

    if event.event_time is not None:
        utc_time = _parse_utc_datetime(event.event_time)
        if utc_time is not None:
            return UserEvent(
                source=event.source,
                time_kind=EventTimeKind.DATED,
                event_time=utc_time,
                video_id=event.video_id,
                channel_id=event.channel_id,
                playlist_id=event.playlist_id,
                title=event.title,
                category_id=event.category_id,
                duration_seconds=event.duration_seconds,
                tags=event.tags,
            )

    time_kind = event.time_kind
    if time_kind is EventTimeKind.DATED:
        time_kind = EventTimeKind.UNDATED

    if store is not None:
        item_id = _resolve_item_id(event)
        if item_id:
            time_kind = _lookup_or_record_first_observed(
                store,
                source=event.source,
                item_id=item_id,
                now_utc=reference_now,
            )

    return UserEvent(
        source=event.source,
        time_kind=time_kind,
        event_time=None,
        video_id=event.video_id,
        channel_id=event.channel_id,
        playlist_id=event.playlist_id,
        title=event.title,
        category_id=event.category_id,
        duration_seconds=event.duration_seconds,
        tags=event.tags,
    )


def normalize_user_events(
    events: Sequence[UserEvent],
    *,
    store: SQLiteStore | None = None,
    now_utc: datetime | None = None,
) -> list[UserEvent]:
    """Normalize a sequence of user events with consistent UTC and first_observed provenance."""
    reference_now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    return [normalize_user_event(ev, store=store, now_utc=reference_now) for ev in events]


def events_from_liked_videos(
    videos: Sequence[VideoMeta],
    *,
    store: SQLiteStore | None = None,
    now_utc: datetime | None = None,
) -> list[UserEvent]:
    """Convert videos.list(myRating='like') results to undated UserEvents (INV-04).

    VideoMeta.published_at is the global upload date and is NEVER copied to event_time.
    """
    reference_now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    events: list[UserEvent] = []
    for video in videos:
        raw_event = UserEvent(
            source=EventSource.LIKED_VIDEO,
            time_kind=EventTimeKind.UNDATED,
            event_time=None,
            video_id=video.video_id,
            channel_id=video.channel_id or None,
            title=sanitize_single_line(video.title),
            category_id=video.category_id,
            duration_seconds=video.duration_seconds,
            tags=tuple(cleaned for tag in video.tags if (cleaned := sanitize_single_line(tag))),
        )
        events.append(normalize_user_event(raw_event, store=store, now_utc=reference_now))
    return events


def summarize_timestamp_coverage(events: Sequence[UserEvent]) -> TimestampCoverage:
    """Count dated, undated, and first_observed events (FR-4.3, ADR-0007)."""
    dated = 0
    undated = 0
    first_observed = 0
    for ev in events:
        if ev.time_kind is EventTimeKind.DATED and ev.event_time is not None:
            dated += 1
        elif ev.time_kind is EventTimeKind.FIRST_OBSERVED:
            first_observed += 1
        else:
            undated += 1
    return TimestampCoverage(
        total=len(events),
        dated=dated,
        undated=undated,
        first_observed=first_observed,
    )
