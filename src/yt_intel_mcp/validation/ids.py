"""Strict YouTube video, channel, and playlist identifier/URL validation (TS-06, INV-02)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import SplitResult, parse_qs, urlsplit

from yt_intel_mcp.errors import ErrorCode, ToolError

__all__ = [
    "ALLOWED_CHANNEL_HOSTS",
    "ALLOWED_SHORT_VIDEO_HOSTS",
    "ALLOWED_YOUTUBE_HOSTS",
    "ChannelReference",
    "extract_channel_id",
    "extract_playlist_id",
    "extract_video_id",
    "parse_channel_reference",
]

_MAX_INPUT_LENGTH = 512

ALLOWED_YOUTUBE_HOSTS: frozenset[str] = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }
)
ALLOWED_SHORT_VIDEO_HOSTS: frozenset[str] = frozenset({"youtu.be", "www.youtu.be"})
ALLOWED_CHANNEL_HOSTS: frozenset[str] = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com"}
)

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_HANDLE_RE = re.compile(r"^@[A-Za-z0-9](?:[A-Za-z0-9._-]{1,28}[A-Za-z0-9])$")
_PLAYLIST_ID_RE = re.compile(r"^(?:PL|UU|LL|FL|RD|OLAK5uy_)[A-Za-z0-9_-]{10,64}$")

_VIDEO_PATH_PREFIXES: frozenset[str] = frozenset({"shorts", "live", "embed", "v"})
_CHANNEL_SUBPAGES: frozenset[str] = frozenset(
    {"featured", "videos", "shorts", "streams", "playlists", "community", "about"}
)


@dataclass(frozen=True, slots=True)
class ChannelReference:
    """Validated YouTube channel target resolved cleanly without API calls."""

    kind: Literal["channel_id", "handle"]
    value: str


def _invalid_argument(field: str, message: str) -> ToolError:
    return ToolError(ErrorCode.INVALID_ARGUMENT, message, details={"field": field})


def _require_clean_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise _invalid_argument(field, f"Parameter '{field}' must be a non-empty string.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise _invalid_argument(field, f"Parameter '{field}' contains invalid control characters.")
    cleaned = value.strip()
    if not cleaned:
        raise _invalid_argument(field, f"Parameter '{field}' must not be empty.")
    if len(cleaned) > _MAX_INPUT_LENGTH:
        raise _invalid_argument(
            field, f"Parameter '{field}' exceeds maximum length of {_MAX_INPUT_LENGTH} characters."
        )
    return cleaned


def _parse_youtube_url(raw: str, *, field: str, allowed_hosts: frozenset[str]) -> SplitResult:
    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise _invalid_argument(field, f"Parameter '{field}' must use an http or https URL.")
    if parsed.username is not None or parsed.password is not None:
        raise _invalid_argument(field, f"Parameter '{field}' must not include URL userinfo.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise _invalid_argument(field, f"Parameter '{field}' has an invalid URL port.") from exc
    if port is not None:
        raise _invalid_argument(field, f"Parameter '{field}' must not specify custom URL ports.")
    host = (parsed.hostname or "").lower()
    if host not in allowed_hosts:
        raise _invalid_argument(
            field, f"URL host '{host or '<empty>'}' is not an allow-listed YouTube domain."
        )
    return parsed


def _is_valid_handle(candidate: str) -> bool:
    return bool(_HANDLE_RE.fullmatch(candidate)) and ".." not in candidate


def _extract_video_id_from_url(raw: str) -> str:
    parsed = _parse_youtube_url(
        raw,
        field="video_id",
        allowed_hosts=ALLOWED_YOUTUBE_HOSTS | ALLOWED_SHORT_VIDEO_HOSTS,
    )
    host = (parsed.hostname or "").lower()
    segments = [segment for segment in parsed.path.split("/") if segment]

    if host in ALLOWED_SHORT_VIDEO_HOSTS:
        if len(segments) == 1 and _VIDEO_ID_RE.fullmatch(segments[0]):
            return segments[0]
        raise _invalid_argument("video_id", "Short youtu.be URL must contain an 11-char video ID.")

    if segments == ["watch"]:
        values = parse_qs(parsed.query, keep_blank_values=True).get("v", [])
        if len(values) == 1 and _VIDEO_ID_RE.fullmatch(values[0]):
            return values[0]
        raise _invalid_argument("video_id", "Watch URL must include a valid 11-char 'v' video ID.")

    if (
        len(segments) == 2
        and segments[0] in _VIDEO_PATH_PREFIXES
        and _VIDEO_ID_RE.fullmatch(segments[1])
    ):
        return segments[1]

    raise _invalid_argument("video_id", "Unsupported YouTube video URL format.")


def extract_video_id(value: str) -> str:
    """Extract and validate an 11-character YouTube video ID from an ID or URL (FR-1.1)."""
    cleaned = _require_clean_text(value, "video_id")
    if _VIDEO_ID_RE.fullmatch(cleaned):
        return cleaned
    if "://" in cleaned:
        return _extract_video_id_from_url(cleaned)
    raise _invalid_argument(
        "video_id",
        "Expected an 11-character YouTube video ID or an official YouTube video URL.",
    )


def parse_channel_reference(value: str) -> ChannelReference:
    """Parse and validate a YouTube channel ID, @handle, or channel URL (FR-2.1)."""
    cleaned = _require_clean_text(value, "channel")
    if _CHANNEL_ID_RE.fullmatch(cleaned):
        return ChannelReference(kind="channel_id", value=cleaned)
    if _is_valid_handle(cleaned):
        return ChannelReference(kind="handle", value=cleaned)

    if "://" in cleaned:
        parsed = _parse_youtube_url(cleaned, field="channel", allowed_hosts=ALLOWED_CHANNEL_HOSTS)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if (
            len(segments) == 2
            and segments[0] == "channel"
            and _CHANNEL_ID_RE.fullmatch(segments[1])
        ):
            return ChannelReference(kind="channel_id", value=segments[1])
        if (
            segments
            and _is_valid_handle(segments[0])
            and (len(segments) == 1 or (len(segments) == 2 and segments[1] in _CHANNEL_SUBPAGES))
        ):
            return ChannelReference(kind="handle", value=segments[0])
        raise _invalid_argument(
            "channel",
            "Channel URL must point to /channel/UC... or /@handle on an official YouTube domain.",
        )

    raise _invalid_argument(
        "channel",
        "Expected a 24-character UC... channel ID, @handle, or official YouTube channel URL.",
    )


def extract_channel_id(value: str) -> str:
    """Extract and validate a canonical YouTube UC... channel ID or @handle (FR-2.1)."""
    return parse_channel_reference(value).value


def extract_playlist_id(value: str) -> str:
    """Extract and validate a YouTube playlist ID from an ID or /playlist URL (NFR-5)."""
    cleaned = _require_clean_text(value, "playlist_id")
    if _PLAYLIST_ID_RE.fullmatch(cleaned):
        return cleaned
    if "://" in cleaned:
        parsed = _parse_youtube_url(
            cleaned, field="playlist_id", allowed_hosts=ALLOWED_CHANNEL_HOSTS
        )
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments == ["playlist"]:
            values = parse_qs(parsed.query, keep_blank_values=True).get("list", [])
            if len(values) == 1 and _PLAYLIST_ID_RE.fullmatch(values[0]):
                return values[0]
        raise _invalid_argument(
            "playlist_id",
            "Playlist URL must point to /playlist?list=<playlist_id> on an allow-listed host.",
        )
    raise _invalid_argument(
        "playlist_id",
        "Expected a valid YouTube playlist ID or /playlist?list=... URL.",
    )
