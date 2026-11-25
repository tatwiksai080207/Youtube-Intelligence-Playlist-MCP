"""Untrusted metadata sanitization stubs reserved for MF-07 (NFR-6, INV-22)."""

from __future__ import annotations

from yt_intel_mcp.models import VideoMeta

__all__ = [
    "DEFAULT_MAX_DESCRIPTION_LENGTH",
    "DEFAULT_MAX_TITLE_LENGTH",
    "sanitize_text",
    "sanitize_video_meta",
]

DEFAULT_MAX_TITLE_LENGTH = 200
DEFAULT_MAX_DESCRIPTION_LENGTH = 1000


def sanitize_text(
    text: str,
    *,
    max_length: int = DEFAULT_MAX_DESCRIPTION_LENGTH,
) -> str:
    """Sanitize untrusted YouTube metadata text against prompt injection (MF-07)."""
    _ = (text, max_length)
    raise NotImplementedError("Metadata sanitization is scheduled for task MF-07.")


def sanitize_video_meta(video: VideoMeta) -> VideoMeta:
    """Return a VideoMeta instance with untrusted text fields sanitized (MF-07)."""
    _ = video
    raise NotImplementedError("Metadata sanitization is scheduled for task MF-07.")
