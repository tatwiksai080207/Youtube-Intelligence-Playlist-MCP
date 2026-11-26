"""Spoken audio-language validation using snippet.defaultAudioLanguage only (MF-09, FR-5.1a)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.playlist.constraints import PlaylistConstraints

__all__ = [
    "UNVERIFIED_AUDIO_LANGUAGE_LABEL",
    "AudioLanguageStatus",
    "LanguageCheckResult",
    "evaluate_video_audio_language",
    "filter_videos_by_language",
    "is_video_language_eligible",
    "primary_language_subtag",
]

UNVERIFIED_AUDIO_LANGUAGE_LABEL = "Audio language unverified"

AudioLanguageStatus = Literal[
    "not_filtered",
    "verified",
    "unverified",
    "mismatch",
    "missing_excluded",
]

_PRIMARY_SUBTAG_RE = re.compile(r"^[A-Za-z]{2,3}$")


@dataclass(frozen=True, slots=True)
class LanguageCheckResult:
    """Outcome of FR-5.1a spoken audio-language eligibility evaluation for one video."""

    eligible: bool
    status: AudioLanguageStatus
    label: str
    audio_language: str | None = None
    primary_subtag: str | None = None


def primary_language_subtag(tag: str | None) -> str | None:
    """Extract normalized lowercase BCP 47 primary language subtag from a language tag."""
    if tag is None:
        return None
    cleaned = tag.strip()
    if not cleaned:
        return None
    parts = re.split(r"[-_]", cleaned, maxsplit=1)
    primary = parts[0]
    if _PRIMARY_SUBTAG_RE.fullmatch(primary) is None:
        return None
    return primary.lower()


def evaluate_video_audio_language(
    video: VideoMeta,
    requested_language: str | None,
    *,
    allow_unknown_language: bool = False,
) -> LanguageCheckResult:
    """Evaluate FR-5.1a spoken language eligibility using defaultAudioLanguage only (INV-10)."""
    requested_primary: str | None = None
    if requested_language is not None:
        requested_primary = primary_language_subtag(requested_language)
        if requested_primary is None:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Requested language {requested_language!r} is not a valid BCP 47 tag.",
                details={"field": "language"},
            )

    raw_audio = video.default_audio_language.strip() if video.default_audio_language else ""
    audio_primary = primary_language_subtag(raw_audio) if raw_audio else None
    has_known_audio = bool(
        raw_audio
        and audio_primary is not None
        and not (audio_primary == "und" and requested_primary != "und")
    )
    resolved_audio = raw_audio if has_known_audio else None
    resolved_primary = audio_primary if has_known_audio else None

    if requested_primary is None:
        label = (
            f"Audio language: {resolved_audio}"
            if resolved_audio is not None
            else UNVERIFIED_AUDIO_LANGUAGE_LABEL
        )
        return LanguageCheckResult(
            eligible=True,
            status="not_filtered",
            label=label,
            audio_language=resolved_audio,
            primary_subtag=resolved_primary,
        )

    if not has_known_audio:
        if allow_unknown_language:
            return LanguageCheckResult(
                eligible=True,
                status="unverified",
                label=UNVERIFIED_AUDIO_LANGUAGE_LABEL,
                audio_language=None,
                primary_subtag=None,
            )
        return LanguageCheckResult(
            eligible=False,
            status="missing_excluded",
            label=UNVERIFIED_AUDIO_LANGUAGE_LABEL,
            audio_language=None,
            primary_subtag=None,
        )

    if resolved_primary == requested_primary:
        return LanguageCheckResult(
            eligible=True,
            status="verified",
            label=f"Audio language verified ({resolved_audio})",
            audio_language=resolved_audio,
            primary_subtag=resolved_primary,
        )

    return LanguageCheckResult(
        eligible=False,
        status="mismatch",
        label=f"Audio language mismatch ({resolved_audio})",
        audio_language=resolved_audio,
        primary_subtag=resolved_primary,
    )


def is_video_language_eligible(video: VideoMeta, constraints: PlaylistConstraints) -> bool:
    """Return True when a video passes FR-5.1a spoken audio-language constraints."""
    return evaluate_video_audio_language(
        video,
        constraints.language,
        allow_unknown_language=constraints.allow_unknown_language,
    ).eligible


def filter_videos_by_language(
    videos: Sequence[VideoMeta],
    constraints: PlaylistConstraints,
) -> tuple[
    list[tuple[VideoMeta, LanguageCheckResult]], list[tuple[VideoMeta, LanguageCheckResult]]
]:
    """Partition candidate videos into (eligible, excluded) pairs with FR-5.1a status labels."""
    eligible: list[tuple[VideoMeta, LanguageCheckResult]] = []
    excluded: list[tuple[VideoMeta, LanguageCheckResult]] = []
    for video in videos:
        result = evaluate_video_audio_language(
            video,
            constraints.language,
            allow_unknown_language=constraints.allow_unknown_language,
        )
        if result.eligible:
            eligible.append((video, result))
        else:
            excluded.append((video, result))
    return eligible, excluded
