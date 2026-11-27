"""YouTube Data API v3 provider abstraction boundary (SE-6, FR-8.1)."""

from __future__ import annotations

from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.provider.fixture import (
    FixtureCallRecord,
    FixtureErrorRule,
    FixtureYouTubeProvider,
    InsertedPlaylistItem,
)
from yt_intel_mcp.provider.live import (
    FORBIDDEN_PARTS,
    YOUTUBE_API_BASE_URL,
    LiveHttpTransport,
    LiveYouTubeProvider,
    UrllibLiveHttpTransport,
)

__all__ = [
    "FORBIDDEN_PARTS",
    "YOUTUBE_API_BASE_URL",
    "FixtureCallRecord",
    "FixtureErrorRule",
    "FixtureYouTubeProvider",
    "InsertedPlaylistItem",
    "LiveHttpTransport",
    "LiveYouTubeProvider",
    "UrllibLiveHttpTransport",
    "YouTubeProvider",
]
