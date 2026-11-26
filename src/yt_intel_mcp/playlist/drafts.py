"""Immutable expiring server-side playlist drafts (MF-11, FR-5.3, INV-12)."""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from yt_intel_mcp.config import DraftConfig
from yt_intel_mcp.durations import format_duration, format_duration_clock
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.playlist.constraints import MAX_TITLE_LENGTH, PlaylistConstraints
from yt_intel_mcp.playlist.language import AudioLanguageStatus
from yt_intel_mcp.playlist.solver import PlaylistSolution, SelectedPlaylistVideo
from yt_intel_mcp.sanitize import sanitize_single_line

__all__ = [
    "DRAFT_ID_RE",
    "DraftStore",
    "DraftVideo",
    "PlaylistDraft",
]

DRAFT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_draft_title(constraints: PlaylistConstraints, clean_topic: str) -> str:
    if constraints.title is not None:
        sanitized_explicit = sanitize_single_line(constraints.title, max_length=MAX_TITLE_LENGTH)
        if sanitized_explicit:
            return sanitized_explicit
    fallback = sanitize_single_line(f"Curated: {clean_topic}", max_length=MAX_TITLE_LENGTH)
    return fallback or "Curated Playlist"


@dataclass(frozen=True, slots=True)
class DraftVideo:
    """Immutable sanitized playlist entry inside a PlaylistDraft (FR-5.3, INV-12, INV-22)."""

    video_id: str
    title: str
    channel_id: str
    channel_title: str
    duration_seconds: int
    duration_human: str
    duration_clock: str
    audio_language: str | None
    audio_language_status: AudioLanguageStatus
    audio_language_label: str
    is_audio_language_unverified: bool
    relevance_score: float

    @classmethod
    def from_selected(cls, item: SelectedPlaylistVideo) -> DraftVideo:
        """Create a sanitized immutable DraftVideo from a solver selection entry."""
        clean_title = sanitize_single_line(item.video.title) or item.video.video_id
        clean_channel = sanitize_single_line(item.video.channel_title) or item.video.channel_id
        return cls(
            video_id=item.video.video_id,
            title=clean_title,
            channel_id=item.video.channel_id,
            channel_title=clean_channel,
            duration_seconds=item.duration_seconds,
            duration_human=format_duration(item.duration_seconds),
            duration_clock=format_duration_clock(item.duration_seconds),
            audio_language=item.video.default_audio_language,
            audio_language_status=item.audio_language_status,
            audio_language_label=item.audio_language_label,
            is_audio_language_unverified=item.is_audio_language_unverified,
            relevance_score=item.relevance_score,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this draft video entry for MCP JSON display."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "duration_seconds": self.duration_seconds,
            "duration_human": self.duration_human,
            "duration_clock": self.duration_clock,
            "audio_language": self.audio_language,
            "audio_language_status": self.audio_language_status,
            "audio_language_label": self.audio_language_label,
            "is_audio_language_unverified": self.is_audio_language_unverified,
            "relevance_score": self.relevance_score,
        }


@dataclass(frozen=True, slots=True)
class PlaylistDraft:
    """Frozen immutable playlist draft expiring after DraftConfig.ttl_seconds (FR-5.3, INV-12)."""

    draft_id: str
    title: str
    privacy_status: Literal["private", "unlisted", "public"]
    topic: str
    constraints: PlaylistConstraints
    videos: tuple[DraftVideo, ...]
    total_duration_seconds: int
    total_duration_human: str
    target_min_seconds: int
    target_max_seconds: int
    candidates_retrieved: int
    candidates_eligible: int
    created_at_utc: datetime
    expires_at_utc: datetime

    @property
    def ordered_video_ids(self) -> tuple[str, ...]:
        """Return ordered tuple of approved video IDs preserved across confirmation and writes."""
        return tuple(video.video_id for video in self.videos)

    def is_expired(self, now_utc: datetime | None = None) -> bool:
        """Return True when the draft TTL has elapsed."""
        now = _ensure_utc(now_utc) if now_utc is not None else datetime.now(UTC)
        return now >= self.expires_at_utc

    def to_view(self, *, now_utc: datetime | None = None) -> dict[str, Any]:
        """Serialize the canonical INV-12 read-only draft view with fresh mutable containers."""
        now = _ensure_utc(now_utc) if now_utc is not None else datetime.now(UTC)
        remaining_seconds = max(0, round((self.expires_at_utc - now).total_seconds()))
        return {
            "draft_id": self.draft_id,
            "title": self.title,
            "privacy_status": self.privacy_status,
            "topic": self.topic,
            "video_count": len(self.videos),
            "videos": [video.to_dict() for video in self.videos],
            "total_duration_seconds": self.total_duration_seconds,
            "total_duration_human": self.total_duration_human,
            "target_window": {
                "min_seconds": self.target_min_seconds,
                "max_seconds": self.target_max_seconds,
                "min_human": format_duration(self.target_min_seconds),
                "max_human": format_duration(self.target_max_seconds),
                "tolerance_percent": self.constraints.tolerance_percent,
            },
            "constraints": {
                "target_total_minutes": self.constraints.target_total_minutes,
                "tolerance_percent": self.constraints.tolerance_percent,
                "max_video_minutes": self.constraints.max_video_minutes,
                "max_videos": self.constraints.max_videos,
                "language": self.constraints.language,
                "allow_unknown_language": self.constraints.allow_unknown_language,
            },
            "candidates_retrieved": self.candidates_retrieved,
            "candidates_eligible": self.candidates_eligible,
            "created_at_utc": self.created_at_utc.isoformat(),
            "expires_at_utc": self.expires_at_utc.isoformat(),
            "expires_in_seconds": remaining_seconds,
            "side_effects": "none",
        }


class DraftStore:
    """Server-side store managing immutable expiring PlaylistDraft objects (FR-5.3, INV-12)."""

    def __init__(
        self,
        config: DraftConfig | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config or DraftConfig()
        if self._config.ttl_seconds <= 0:
            raise ValueError(
                f"DraftConfig.ttl_seconds must be positive, got {self._config.ttl_seconds}."
            )
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))
        self._drafts: dict[str, PlaylistDraft] = {}

    @property
    def ttl_seconds(self) -> int:
        """Return configured draft lifetime in seconds."""
        return self._config.ttl_seconds

    def _now_utc(self) -> datetime:
        return _ensure_utc(self._clock())

    def create_from_solution(
        self,
        constraints: PlaylistConstraints,
        solution: PlaylistSolution,
    ) -> PlaylistDraft:
        """Freeze a solved candidate selection into an immutable expiring PlaylistDraft."""
        created_at = self._now_utc()
        expires_at = created_at + timedelta(seconds=self._config.ttl_seconds)
        clean_topic = sanitize_single_line(constraints.topic, max_length=300) or "playlist"
        clean_title = _format_draft_title(constraints, clean_topic)
        draft_videos = tuple(DraftVideo.from_selected(item) for item in solution.selected_videos)

        draft_id = f"draft_{created_at.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(6)}"
        while draft_id in self._drafts:  # pragma: no cover
            draft_id = f"draft_{created_at.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(6)}"

        draft = PlaylistDraft(
            draft_id=draft_id,
            title=clean_title,
            privacy_status=constraints.privacy_status,
            topic=clean_topic,
            constraints=constraints,
            videos=draft_videos,
            total_duration_seconds=solution.total_duration_seconds,
            total_duration_human=solution.total_duration_human,
            target_min_seconds=solution.target_min_seconds,
            target_max_seconds=solution.target_max_seconds,
            candidates_retrieved=solution.candidates_retrieved,
            candidates_eligible=solution.candidates_eligible,
            created_at_utc=created_at,
            expires_at_utc=expires_at,
        )
        self._drafts[draft_id] = draft
        return draft

    def get(self, draft_id: object) -> PlaylistDraft:
        """Fetch an active draft or raise INVALID_ARGUMENT / DRAFT_EXPIRED cleanly."""
        if not isinstance(draft_id, str):
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "Parameter 'draft_id' must be a string.",
                details={"field": "draft_id"},
            )
        clean_id = draft_id.strip()
        if DRAFT_ID_RE.fullmatch(clean_id) is None:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Parameter 'draft_id' ({draft_id!r}) does not match expected draft ID format.",
                details={"field": "draft_id"},
            )
        draft = self._drafts.get(clean_id)
        if draft is None:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Unknown playlist draft {clean_id!r}.",
                details={"field": "draft_id"},
            )
        now = self._now_utc()
        if draft.is_expired(now):
            raise ToolError(
                ErrorCode.DRAFT_EXPIRED,
                (
                    f"Playlist draft {clean_id!r} expired at {draft.expires_at_utc.isoformat()} "
                    "and can no longer be created. Generate a new draft via draft_curated_playlist."
                ),
                details={
                    "draft_id": clean_id,
                    "created_at_utc": draft.created_at_utc.isoformat(),
                    "expires_at_utc": draft.expires_at_utc.isoformat(),
                },
            )
        return draft

    def purge_expired(self) -> int:
        """Delete expired drafts from memory and return the count removed."""
        now = self._now_utc()
        expired_ids = [did for did, draft in self._drafts.items() if draft.is_expired(now)]
        for did in expired_ids:
            del self._drafts[did]
        return len(expired_ids)

    def list_active_ids(self) -> tuple[str, ...]:
        """Return tuple of currently active unexpired draft IDs."""
        now = self._now_utc()
        return tuple(did for did, draft in self._drafts.items() if not draft.is_expired(now))
