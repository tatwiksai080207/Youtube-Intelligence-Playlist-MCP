"""ISO-8601 duration parsing and human-readable formatting helpers (TS-07, FR-4.1, FR-5.1)."""

from __future__ import annotations

import re

__all__ = [
    "format_duration",
    "format_duration_clock",
    "format_iso8601_duration",
    "is_live_or_zero_duration",
    "parse_iso8601_duration",
    "parse_optional_duration",
]

_ISO_DURATION_RE = re.compile(
    r"^\s*P(?:"
    r"(?P<weeks>\d+)W"
    r"|(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+(?:[.,]\d+)?)S)?)?"
    r")\s*$"
)


def parse_iso8601_duration(value: str) -> int:
    """Parse an ISO-8601 video duration (`PT#H#M#S`, `P#DT...`, `P0D`) into integer seconds."""
    if not isinstance(value, str):
        raise ValueError(f"Duration value must be a string, got {type(value).__name__}.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Duration string must not be empty.")

    normalized = cleaned.upper()
    match = _ISO_DURATION_RE.fullmatch(normalized)
    if match is None:
        raise ValueError(f"Invalid ISO-8601 duration: {value!r}.")

    groups = match.groupdict()
    has_time_designator = "T" in normalized
    time_parts = (groups["hours"], groups["minutes"], groups["seconds"])
    if has_time_designator and all(part is None for part in time_parts):
        raise ValueError(f"ISO-8601 duration has empty time section: {value!r}.")

    all_parts = (groups["weeks"], groups["days"], *time_parts)
    if all(part is None for part in all_parts):
        raise ValueError(f"ISO-8601 duration must contain at least one unit: {value!r}.")

    weeks = int(groups["weeks"]) if groups["weeks"] is not None else 0
    days = int(groups["days"]) if groups["days"] is not None else 0
    hours = int(groups["hours"]) if groups["hours"] is not None else 0
    minutes = int(groups["minutes"]) if groups["minutes"] is not None else 0
    sec_raw = groups["seconds"]
    seconds = float(sec_raw.replace(",", ".")) if sec_raw is not None else 0.0

    total_seconds = ((weeks * 7 + days) * 24 + hours) * 3600 + minutes * 60 + seconds
    return round(total_seconds)


def parse_optional_duration(value: str | None) -> int | None:
    """Parse an optional ISO-8601 duration string, returning None when absent or blank."""
    if value is None or not value.strip():
        return None
    return parse_iso8601_duration(value)


def is_live_or_zero_duration(
    duration: str | int | None,
    *,
    live_broadcast_content: str = "none",
) -> bool:
    """Return True when a video is live or carries zero/missing duration (INV-03, INV-07)."""
    if live_broadcast_content.strip().lower() not in {"", "none"}:
        return True
    if duration is None:
        return True
    if isinstance(duration, bool):
        raise ValueError("Duration must be an integer, string, or None, not bool.")
    seconds = parse_iso8601_duration(duration) if isinstance(duration, str) else duration
    return seconds <= 0


def format_duration(seconds: int | None, *, live: bool = False) -> str:
    """Format non-negative integer seconds into a concise human-readable duration (NFR-9)."""
    if live:
        return "Live"
    if seconds is None:
        return "Unknown"
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        raise ValueError(f"Duration seconds must be an int or None, got {type(seconds).__name__}.")
    if seconds < 0:
        raise ValueError(f"Duration seconds must be non-negative, got {seconds}.")
    if seconds == 0:
        return "0s"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts)


def format_duration_clock(seconds: int | None) -> str:
    """Format non-negative seconds as clock display (`MM:SS` or `H:MM:SS`)."""
    if seconds is None:
        return "--:--"
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        raise ValueError(f"Duration seconds must be an int or None, got {type(seconds).__name__}.")
    if seconds < 0:
        raise ValueError(f"Duration seconds must be non-negative, got {seconds}.")

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_iso8601_duration(seconds: int) -> str:
    """Format non-negative integer seconds into canonical ISO-8601 `PT...` notation."""
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        raise ValueError(f"Duration seconds must be an int, got {type(seconds).__name__}.")
    if seconds < 0:
        raise ValueError(f"Duration seconds must be non-negative, got {seconds}.")
    if seconds == 0:
        return "PT0S"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = ["PT"]
    if hours:
        parts.append(f"{hours}H")
    if minutes:
        parts.append(f"{minutes}M")
    if secs:
        parts.append(f"{secs}S")
    return "".join(parts)
