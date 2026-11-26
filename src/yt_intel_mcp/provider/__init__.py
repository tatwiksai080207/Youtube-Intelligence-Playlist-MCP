"""YouTube Data API v3 provider abstraction boundary (SE-6, FR-8.1)."""

from __future__ import annotations

from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.provider.fixture import (
    FixtureCallRecord,
    FixtureErrorRule,
    FixtureYouTubeProvider,
    InsertedPlaylistItem,
)

__all__ = [
    "FixtureCallRecord",
    "FixtureErrorRule",
    "FixtureYouTubeProvider",
    "InsertedPlaylistItem",
    "YouTubeProvider",
]
