"""Abstract YouTubeProvider Protocol freezing the SE-6 / FR-8.1 boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from yt_intel_mcp.models import (
    ChannelMeta,
    CreatedPlaylist,
    PlaylistSummary,
    SearchHit,
    UserEvent,
    VideoMeta,
)

__all__ = ["YouTubeProvider"]


@runtime_checkable
class YouTubeProvider(Protocol):
    """Dependency-inverted interface to YouTube Data API v3 operations.

    All implementations (fixture and live) MUST exclude video/channel statistics
    and MUST NOT expose playlist update or delete operations (SRS Section 1.2).
    """

    async def get_videos(self, video_ids: Sequence[str]) -> list[VideoMeta]:
        """Fetch objective metadata for up to 50 video IDs per call."""
        ...

    async def search_videos(
        self,
        query: str,
        *,
        max_results: int = 25,
        video_duration: Literal["any", "short", "medium", "long"] | None = None,
        relevance_language: str | None = None,
        region_code: str | None = None,
        page_token: str | None = None,
    ) -> list[SearchHit]:
        """Search YouTube for candidate videos matching query and filters."""
        ...

    async def search_channels(
        self,
        query: str,
        *,
        max_results: int = 25,
        relevance_language: str | None = None,
        page_token: str | None = None,
    ) -> list[SearchHit]:
        """Search YouTube for candidate channels matching query."""
        ...

    async def get_channels(self, channel_ids: Sequence[str]) -> list[ChannelMeta]:
        """Fetch objective metadata for up to 50 channel IDs per call."""
        ...

    async def get_channel_by_handle(self, handle: str) -> ChannelMeta | None:
        """Resolve an @handle via channels.list?forHandle and return metadata if found (FR-2.1)."""
        ...

    async def get_my_channel(self) -> ChannelMeta:
        """Fetch the authenticated user's primary YouTube channel metadata."""
        ...

    async def list_subscriptions_mine(self, *, max_results: int = 50) -> list[UserEvent]:
        """List authenticated subscriptions with action timestamps."""
        ...

    async def list_playlists_mine(self, *, max_results: int = 50) -> list[PlaylistSummary]:
        """List playlists owned by the authenticated user."""
        ...

    async def list_playlist_items(
        self,
        playlist_id: str,
        *,
        max_results: int = 50,
    ) -> list[UserEvent]:
        """List items in a playlist with playlist-item insertion timestamps."""
        ...

    async def list_liked_videos_rated(self, *, max_results: int = 50) -> list[VideoMeta]:
        """List videos rated 'like' via videos.list (no user rating timestamp)."""
        ...

    async def get_video_categories(self, *, region_code: str = "US") -> dict[str, str]:
        """Fetch video category ID to title mapping for a YouTube region code."""
        ...

    async def insert_playlist(
        self,
        *,
        title: str,
        description: str = "",
        privacy_status: Literal["private", "unlisted", "public"] = "private",
    ) -> CreatedPlaylist:
        """Create a new YouTube playlist after trusted user confirmation (FR-5.5)."""
        ...

    async def insert_playlist_item(
        self,
        *,
        playlist_id: str,
        video_id: str,
        position: int | None = None,
    ) -> str:
        """Insert a video into a newly created YouTube playlist, returning the item ID."""
        ...
