"""YouTube video, channel, and playlist ID/URL extractor stubs for TS-06 (FR-1.1, FR-2.1)."""

from __future__ import annotations

__all__ = [
    "extract_channel_id",
    "extract_playlist_id",
    "extract_video_id",
]


def extract_video_id(value: str) -> str:
    """Extract and validate a YouTube video ID from a raw ID or URL (TS-06)."""
    _ = value
    raise NotImplementedError("ID/URL validation is scheduled for task TS-06.")


def extract_channel_id(value: str) -> str:
    """Extract and validate a YouTube channel ID or handle reference (TS-06)."""
    _ = value
    raise NotImplementedError("ID/URL validation is scheduled for task TS-06.")


def extract_playlist_id(value: str) -> str:
    """Extract and validate a YouTube playlist ID from a raw ID or URL (TS-06)."""
    _ = value
    raise NotImplementedError("ID/URL validation is scheduled for task TS-06.")
