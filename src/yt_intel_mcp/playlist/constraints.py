"""Playlist constraint validation and strict duration window logic (MF-08, FR-5.1, INV-09)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from yt_intel_mcp.config import PlaylistConfig
from yt_intel_mcp.durations import is_live_or_zero_duration
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.validation.bounds import validate_float_range, validate_int_range

__all__ = [
    "MAX_PLAYLIST_VIDEOS",
    "MAX_TARGET_MINUTES",
    "MAX_TOLERANCE_PERCENT",
    "MAX_VIDEO_LIMIT_MINUTES",
    "MIN_PLAYLIST_VIDEOS",
    "MIN_TARGET_MINUTES",
    "MIN_TOLERANCE_PERCENT",
    "MIN_VIDEO_LIMIT_MINUTES",
    "PlaylistConstraints",
    "build_playlist_constraints",
    "evaluate_selection_constraints",
    "is_total_in_window",
    "is_video_duration_eligible",
]

MIN_TARGET_MINUTES = 1.0
MAX_TARGET_MINUTES = 600.0
MIN_TOLERANCE_PERCENT = 0.0
MAX_TOLERANCE_PERCENT = 50.0
MIN_VIDEO_LIMIT_MINUTES = 1.0
MAX_VIDEO_LIMIT_MINUTES = 600.0
MIN_PLAYLIST_VIDEOS = 1
MAX_PLAYLIST_VIDEOS = 50
MAX_TOPIC_LENGTH = 300
MAX_TITLE_LENGTH = 150

_LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
_ALLOWED_PRIVACY_STATUSES: frozenset[str] = frozenset({"private", "unlisted", "public"})


def _invalid(field: str, message: str) -> ToolError:
    return ToolError(ErrorCode.INVALID_ARGUMENT, message, details={"field": field})


def _require_clean_text(value: object, field: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise _invalid(field, f"Parameter '{field}' must be a non-empty string.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise _invalid(field, f"Parameter '{field}' contains invalid control characters.")
    cleaned = value.strip()
    if not cleaned:
        raise _invalid(field, f"Parameter '{field}' must not be empty.")
    if len(cleaned) > max_length:
        raise _invalid(
            field,
            f"Parameter '{field}' exceeds maximum length of {max_length} characters.",
        )
    return cleaned


def _compute_min_seconds(target_max_seconds: int, tolerance_percent: float) -> int:
    """Compute exact integer-second floor ceil(T * (1 - tol)) without binary float drift."""
    ratio = (Decimal("100") - Decimal(str(tolerance_percent))) / Decimal("100")
    floor_seconds = (Decimal(target_max_seconds) * ratio).to_integral_value(rounding=ROUND_CEILING)
    return min(target_max_seconds, int(floor_seconds))


@dataclass(frozen=True, slots=True)
class PlaylistConstraints:
    """Validated immutable playlist curation constraints and integer-second window."""

    topic: str
    target_total_minutes: float
    tolerance_percent: float
    max_video_minutes: float | None
    max_videos: int
    language: str | None
    allow_unknown_language: bool
    title: str | None
    privacy_status: Literal["private", "unlisted", "public"]
    target_min_seconds: int
    target_max_seconds: int
    max_video_seconds: int | None

    def __post_init__(self) -> None:
        if self.target_max_seconds <= 0:
            raise ValueError("target_max_seconds must be positive.")
        if not 0 <= self.target_min_seconds <= self.target_max_seconds:
            raise ValueError("target_min_seconds must lie within [0, target_max_seconds].")
        if self.max_video_seconds is not None and self.max_video_seconds <= 0:
            raise ValueError("max_video_seconds must be positive when set.")
        if not MIN_PLAYLIST_VIDEOS <= self.max_videos <= MAX_PLAYLIST_VIDEOS:
            raise ValueError(
                f"max_videos must lie within [{MIN_PLAYLIST_VIDEOS}, {MAX_PLAYLIST_VIDEOS}]."
            )

    @property
    def effective_max_video_seconds(self) -> int:
        """Return the tightest per-video upper duration bound in seconds."""
        if self.max_video_seconds is None:
            return self.target_max_seconds
        return min(self.max_video_seconds, self.target_max_seconds)


def build_playlist_constraints(
    *,
    topic: object,
    target_total_minutes: object,
    tolerance_percent: object | None = None,
    max_video_minutes: object | None = None,
    max_videos: object | None = None,
    language: object | None = None,
    allow_unknown_language: object | None = None,
    title: object | None = None,
    privacy_status: object | None = None,
    config: PlaylistConfig | None = None,
) -> PlaylistConstraints:
    """Validate and freeze FR-5.1 playlist constraints before any quota spend (INV-02, INV-09)."""
    defaults = config or PlaylistConfig()

    clean_topic = _require_clean_text(topic, "topic", max_length=MAX_TOPIC_LENGTH)
    valid_target = validate_float_range(
        target_total_minutes,
        "target_total_minutes",
        minimum=MIN_TARGET_MINUTES,
        maximum=MAX_TARGET_MINUTES,
    )

    raw_tol: object = (
        defaults.duration_tolerance_fraction * 100.0
        if tolerance_percent is None
        else tolerance_percent
    )
    valid_tol = validate_float_range(
        raw_tol,
        "tolerance_percent",
        minimum=MIN_TOLERANCE_PERCENT,
        maximum=MAX_TOLERANCE_PERCENT,
    )

    valid_max_video: float | None = None
    if max_video_minutes is not None:
        valid_max_video = validate_float_range(
            max_video_minutes,
            "max_video_minutes",
            minimum=MIN_VIDEO_LIMIT_MINUTES,
            maximum=MAX_VIDEO_LIMIT_MINUTES,
        )

    raw_max_videos: object = defaults.default_max_videos if max_videos is None else max_videos
    valid_max_videos = validate_int_range(
        raw_max_videos,
        "max_videos",
        minimum=MIN_PLAYLIST_VIDEOS,
        maximum=MAX_PLAYLIST_VIDEOS,
    )

    valid_language: str | None = None
    if language is not None:
        cleaned_lang = _require_clean_text(language, "language", max_length=35)
        if len(cleaned_lang) < 2 or _LANGUAGE_RE.fullmatch(cleaned_lang) is None:
            raise _invalid(
                "language",
                "Parameter 'language' must be a valid BCP 47 language tag (e.g. 'en' or 'en-GB').",
            )
        valid_language = cleaned_lang

    raw_allow_unknown: object = (
        defaults.allow_unknown_language
        if allow_unknown_language is None
        else allow_unknown_language
    )
    if not isinstance(raw_allow_unknown, bool):
        raise _invalid("allow_unknown_language", "Parameter 'allow_unknown_language' must be bool.")

    valid_title: str | None = None
    if title is not None:
        valid_title = _require_clean_text(title, "title", max_length=MAX_TITLE_LENGTH)

    raw_privacy: object = (
        defaults.default_privacy_status if privacy_status is None else privacy_status
    )
    if not isinstance(raw_privacy, str) or raw_privacy not in _ALLOWED_PRIVACY_STATUSES:
        raise _invalid(
            "privacy_status",
            "Parameter 'privacy_status' must be one of 'private', 'unlisted', or 'public'.",
        )
    valid_privacy: Literal["private", "unlisted", "public"] = raw_privacy  # type: ignore[assignment]

    target_max_seconds = round(valid_target * 60)
    target_min_seconds = _compute_min_seconds(target_max_seconds, valid_tol)
    max_video_seconds = round(valid_max_video * 60) if valid_max_video is not None else None

    return PlaylistConstraints(
        topic=clean_topic,
        target_total_minutes=valid_target,
        tolerance_percent=valid_tol,
        max_video_minutes=valid_max_video,
        max_videos=valid_max_videos,
        language=valid_language,
        allow_unknown_language=raw_allow_unknown,
        title=valid_title,
        privacy_status=valid_privacy,
        target_min_seconds=target_min_seconds,
        target_max_seconds=target_max_seconds,
        max_video_seconds=max_video_seconds,
    )


def is_video_duration_eligible(video: VideoMeta, constraints: PlaylistConstraints) -> bool:
    """Return True when a video is playable, non-live, and <= max_video_minutes (inclusive)."""
    if not video.is_available:
        return False
    if video.privacy_status.strip().lower() == "private":
        return False
    if is_live_or_zero_duration(
        video.duration_seconds, live_broadcast_content=video.live_broadcast_content
    ):
        return False
    return (
        video.duration_seconds is not None
        and 1 <= video.duration_seconds <= constraints.effective_max_video_seconds
    )


def is_total_in_window(total_seconds: int, constraints: PlaylistConstraints) -> bool:
    """Return True when total duration lies within [T * (1 - tol), T] and never exceeds T."""
    if isinstance(total_seconds, bool):
        return False
    return constraints.target_min_seconds <= total_seconds <= constraints.target_max_seconds


def evaluate_selection_constraints(
    videos: Sequence[VideoMeta],
    constraints: PlaylistConstraints,
) -> list[str]:
    """Return unmet FR-5.1 constraint keys for a selected or inserted video list (empty if ok)."""
    unmet: list[str] = []
    if not videos:
        unmet.append("empty_selection")
        return unmet

    if len(videos) > constraints.max_videos:
        unmet.append("exceeds_max_videos")

    if any(not is_video_duration_eligible(video, constraints) for video in videos):
        unmet.append("video_ineligible")

    total_seconds = sum(
        video.duration_seconds for video in videos if video.duration_seconds is not None
    )
    if total_seconds < constraints.target_min_seconds:
        unmet.append("below_target_duration_floor")
    elif total_seconds > constraints.target_max_seconds:
        unmet.append("exceeds_target_duration_ceiling")

    return unmet
