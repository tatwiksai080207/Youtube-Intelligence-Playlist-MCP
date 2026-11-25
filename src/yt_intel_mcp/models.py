"""Frozen domain models and objective metadata contracts for yt-intel-mcp."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

__all__ = [
    "ChannelMeta",
    "CostEstimate",
    "CreatedPlaylist",
    "EventSource",
    "EventTimeKind",
    "PlaylistSummary",
    "QuotaUsed",
    "SearchHit",
    "UserEvent",
    "VideoMeta",
]


class EventSource(StrEnum):
    """Explicit YouTube library signal source supported by SRS FR-3 and FR-4."""

    SUBSCRIPTION = "subscription"
    PLAYLIST_ITEM = "playlist_item"
    LIKED_VIDEO = "liked_video"


class EventTimeKind(StrEnum):
    """Provenance of a user action timestamp (INV-04, INV-05, INV-08)."""

    DATED = "dated"
    UNDATED = "undated"
    FIRST_OBSERVED = "first_observed"


@dataclass(frozen=True, slots=True)
class QuotaUsed:
    """Cumulative YouTube Data API quota consumed during a tool invocation."""

    units: int = 0
    search_calls: int = 0

    def __post_init__(self) -> None:
        if self.units < 0:
            raise ValueError("QuotaUsed.units must be non-negative.")
        if self.search_calls < 0:
            raise ValueError("QuotaUsed.search_calls must be non-negative.")

    def __add__(self, other: QuotaUsed) -> QuotaUsed:
        return QuotaUsed(
            units=self.units + other.units,
            search_calls=self.search_calls + other.search_calls,
        )

    def to_dict(self) -> dict[str, int]:
        """Serialize quota usage into the canonical MCP response envelope dict."""
        return {"units": self.units, "search_calls": self.search_calls}


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Preflight cost estimate checked against the dual daily quota ledger."""

    units: int
    search_calls: int = 0
    operation: str = ""

    def __post_init__(self) -> None:
        if self.units < 0:
            raise ValueError("CostEstimate.units must be non-negative.")
        if self.search_calls < 0:
            raise ValueError("CostEstimate.search_calls must be non-negative.")

    def to_quota_used(self) -> QuotaUsed:
        """Convert this cost estimate into an equivalent QuotaUsed record."""
        return QuotaUsed(units=self.units, search_calls=self.search_calls)


@dataclass(frozen=True, slots=True)
class VideoMeta:
    """Objective video metadata excluding popularity or engagement statistics (INV-01)."""

    video_id: str
    title: str
    description: str = ""
    channel_id: str = ""
    channel_title: str = ""
    published_at: datetime | None = None
    tags: tuple[str, ...] = ()
    category_id: str | None = None
    category_name: str | None = None
    duration_seconds: int | None = None
    default_audio_language: str | None = None
    default_language: str | None = None
    live_broadcast_content: str = "none"
    is_embeddable: bool = True
    privacy_status: str = "public"
    is_age_restricted: bool = False
    is_available: bool = True


@dataclass(frozen=True, slots=True)
class ChannelMeta:
    """Objective channel metadata excluding subscriber or view counts (INV-01)."""

    channel_id: str
    title: str
    description: str = ""
    custom_url: str | None = None
    published_at: datetime | None = None
    country: str | None = None
    default_language: str | None = None
    topic_categories: tuple[str, ...] = ()
    uploads_playlist_id: str | None = None
    likes_playlist_id: str | None = None


@dataclass(frozen=True, slots=True)
class SearchHit:
    """Normalized candidate hit returned by YouTube search.list."""

    kind: Literal["video", "channel"]
    item_id: str
    title: str
    description: str = ""
    channel_id: str = ""
    channel_title: str = ""
    published_at: datetime | None = None
    live_broadcast_content: str = "none"


@dataclass(frozen=True, slots=True)
class PlaylistSummary:
    """Summary of an authenticated user's YouTube playlist."""

    playlist_id: str
    title: str
    description: str = ""
    channel_id: str = ""
    channel_title: str = ""
    published_at: datetime | None = None
    item_count: int = 0
    privacy_status: str = "private"


@dataclass(frozen=True, slots=True)
class CreatedPlaylist:
    """Metadata returned when a new YouTube playlist is created (FR-5.5)."""

    playlist_id: str
    title: str
    description: str = ""
    privacy_status: Literal["private", "unlisted", "public"] = "private"
    channel_id: str = ""
    published_at: datetime | None = None
    url: str = ""


@dataclass(frozen=True, slots=True)
class UserEvent:
    """Normalized user signal event for profile building and engagement analysis."""

    source: EventSource
    time_kind: EventTimeKind = EventTimeKind.UNDATED
    event_time: datetime | None = None
    video_id: str | None = None
    channel_id: str | None = None
    playlist_id: str | None = None
    title: str = ""
    category_id: str | None = None
    duration_seconds: int | None = None
    tags: tuple[str, ...] = ()
