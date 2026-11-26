"""YouTube identifier, URL, and bounded parameter validators (TS-06, NFR-5, INV-02)."""

from __future__ import annotations

from yt_intel_mcp.validation.bounds import (
    ALLOWED_SCORING_WEIGHT_KEYS,
    ALLOWED_TIMEFRAMES,
    validate_float_range,
    validate_int_range,
    validate_max_results,
    validate_scoring_weights,
    validate_sources,
    validate_timeframe,
)
from yt_intel_mcp.validation.ids import (
    ALLOWED_CHANNEL_HOSTS,
    ALLOWED_SHORT_VIDEO_HOSTS,
    ALLOWED_YOUTUBE_HOSTS,
    ChannelReference,
    extract_channel_id,
    extract_playlist_id,
    extract_video_id,
    parse_channel_reference,
)

__all__ = [
    "ALLOWED_CHANNEL_HOSTS",
    "ALLOWED_SCORING_WEIGHT_KEYS",
    "ALLOWED_SHORT_VIDEO_HOSTS",
    "ALLOWED_TIMEFRAMES",
    "ALLOWED_YOUTUBE_HOSTS",
    "ChannelReference",
    "extract_channel_id",
    "extract_playlist_id",
    "extract_video_id",
    "parse_channel_reference",
    "validate_float_range",
    "validate_int_range",
    "validate_max_results",
    "validate_scoring_weights",
    "validate_sources",
    "validate_timeframe",
]
