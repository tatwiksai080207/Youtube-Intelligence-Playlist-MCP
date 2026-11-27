"""Ordered playlist write pipeline and partial outcome reporting (MF-14, FR-5.5, NFR-8)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from yt_intel_mcp.durations import format_duration, format_duration_clock, is_live_or_zero_duration
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.playlist.drafts import PlaylistDraft
from yt_intel_mcp.playlist.language import is_video_language_eligible
from yt_intel_mcp.provider.base import YouTubeProvider

__all__ = [
    "FailedVideoItem",
    "InsertedVideoItem",
    "PlaylistWriteOutcome",
    "UnattemptedVideoItem",
    "check_draft_staleness",
    "write_curated_playlist",
]

logger = logging.getLogger(__name__)

_FATAL_WRITE_ERROR_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.QUOTA_EXHAUSTED_UPSTREAM,
        ErrorCode.QUOTA_BUDGET_INSUFFICIENT,
        ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
        ErrorCode.SCOPE_INSUFFICIENT,
        ErrorCode.CHANNEL_REQUIRED,
    }
)


@dataclass(frozen=True, slots=True)
class InsertedVideoItem:
    """Record of a successfully inserted playlist item (FR-5.5, INV-16)."""

    video_id: str
    item_id: str
    title: str
    channel_title: str
    duration_seconds: int
    duration_human: str
    position: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON serializable dictionary."""
        return {
            "video_id": self.video_id,
            "item_id": self.item_id,
            "title": self.title,
            "channel_title": self.channel_title,
            "duration_seconds": self.duration_seconds,
            "duration_human": self.duration_human,
            "position": self.position,
        }


@dataclass(frozen=True, slots=True)
class FailedVideoItem:
    """Record of an approved video whose insertion failed during playlist writing (FR-5.5)."""

    video_id: str
    title: str
    channel_title: str
    duration_seconds: int
    reason: str
    error_code: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON serializable dictionary."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel_title": self.channel_title,
            "duration_seconds": self.duration_seconds,
            "reason": self.reason,
            "error_code": self.error_code,
        }


@dataclass(frozen=True, slots=True)
class UnattemptedVideoItem:
    """Record of an approved video left unattempted when write loop halted (FR-5.5)."""

    video_id: str
    title: str
    channel_title: str
    duration_seconds: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON serializable dictionary."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel_title": self.channel_title,
            "duration_seconds": self.duration_seconds,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PlaylistWriteOutcome:
    """Comprehensive playlist write outcome report distinguishing COMPLETE and PARTIAL."""

    status: Literal["COMPLETE", "PARTIAL"]
    playlist_id: str
    playlist_url: str
    title: str
    privacy_status: str
    target_total_minutes: float
    total_duration_seconds: int
    total_duration_human: str
    total_duration_clock: str
    video_count: int
    inserted_videos: tuple[InsertedVideoItem, ...]
    failed_videos: tuple[FailedVideoItem, ...]
    unattempted_videos: tuple[UnattemptedVideoItem, ...]
    unmet_constraints: tuple[str, ...]

    @property
    def summary(self) -> str:
        """Format human readable execution summary for canonical envelope."""
        if self.status == "COMPLETE":
            return (
                f"Successfully created playlist '{self.title}' ({self.playlist_id}) "
                f"with all {len(self.inserted_videos)} approved videos "
                f"(total duration: {self.total_duration_human}). Status: COMPLETE."
            )
        return (
            f"Created playlist '{self.title}' ({self.playlist_id}) with "
            f"{len(self.inserted_videos)}/{self.video_count} videos "
            f"(actual duration: {self.total_duration_human}). "
            f"{len(self.failed_videos)} failed, {len(self.unattempted_videos)} unattempted. "
            "Status: PARTIAL."
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON serializable dictionary matching SRS Section 4.5."""
        return {
            "status": self.status,
            "playlist_id": self.playlist_id,
            "playlist_url": self.playlist_url,
            "title": self.title,
            "privacy_status": self.privacy_status,
            "target_total_minutes": self.target_total_minutes,
            "total_duration_seconds": self.total_duration_seconds,
            "total_duration_human": self.total_duration_human,
            "total_duration_clock": self.total_duration_clock,
            "video_count": len(self.inserted_videos),
            "approved_video_count": self.video_count,
            "inserted_videos": [item.to_dict() for item in self.inserted_videos],
            "failed_videos": [item.to_dict() for item in self.failed_videos],
            "unattempted_videos": [item.to_dict() for item in self.unattempted_videos],
            "unmet_constraints": list(self.unmet_constraints),
        }


def check_draft_staleness(draft: PlaylistDraft, fresh_videos: Sequence[VideoMeta]) -> None:
    """Assert fresh provider metadata matches approved draft state before writing (FR-5.5(1)).

    Raises ToolError(DRAFT_STALE) with zero writes if any approved video is missing, deleted,
    became live, has zero duration, duration changed, audio language changed, or the selection
    no longer satisfies the approved tolerance window or max video minutes constraint.
    """
    fresh_by_id = {v.video_id: v for v in fresh_videos}

    # 1. Video presence and deletion checks
    for draft_video in draft.videos:
        vid = draft_video.video_id
        if vid not in fresh_by_id:
            raise ToolError(
                ErrorCode.DRAFT_STALE,
                (
                    f"Approved video {vid!r} ({draft_video.title!r}) is missing or was deleted "
                    "from YouTube. Zero writes performed."
                ),
                details={
                    "draft_id": draft.draft_id,
                    "video_id": vid,
                    "reason": "missing_or_deleted",
                },
            )

        fresh = fresh_by_id[vid]

        # 2. Live or zero duration detection
        if (
            fresh.duration_seconds is None
            or is_live_or_zero_duration(fresh.duration_seconds)
            or fresh.duration_seconds <= 0
        ):
            raise ToolError(
                ErrorCode.DRAFT_STALE,
                (
                    f"Approved video {vid!r} became a live stream or has zero duration "
                    f"({fresh.duration_seconds}s). Zero writes performed."
                ),
                details={
                    "draft_id": draft.draft_id,
                    "video_id": vid,
                    "duration_seconds": fresh.duration_seconds,
                    "reason": "live_or_zero_duration",
                },
            )

        # 3. Duration change detection
        if fresh.duration_seconds != draft_video.duration_seconds:
            raise ToolError(
                ErrorCode.DRAFT_STALE,
                (
                    f"Approved video {vid!r} duration changed from {draft_video.duration_seconds}s "
                    f"to {fresh.duration_seconds}s. Zero writes performed."
                ),
                details={
                    "draft_id": draft.draft_id,
                    "video_id": vid,
                    "expected_duration": draft_video.duration_seconds,
                    "actual_duration": fresh.duration_seconds,
                    "reason": "duration_changed",
                },
            )

        # 4. Spoken audio language eligibility check
        if not is_video_language_eligible(fresh, draft.constraints):
            raise ToolError(
                ErrorCode.DRAFT_STALE,
                (
                    f"Approved video {vid!r} audio language "
                    f"({fresh.default_audio_language!r}) no longer satisfies "
                    f"draft constraint {draft.constraints.language!r}. Zero writes performed."
                ),
                details={
                    "draft_id": draft.draft_id,
                    "video_id": vid,
                    "actual_audio_language": fresh.default_audio_language,
                    "constraint_language": draft.constraints.language,
                    "reason": "language_ineligible",
                },
            )

        # 5. Individual max video duration constraint
        if draft.constraints.max_video_seconds is not None:
            max_allowed_seconds = draft.constraints.max_video_seconds
            if fresh.duration_seconds > max_allowed_seconds:
                raise ToolError(
                    ErrorCode.DRAFT_STALE,
                    (
                        f"Approved video {vid!r} duration ({fresh.duration_seconds}s) exceeds "
                        f"maximum video limit ({max_allowed_seconds}s). Zero writes performed."
                    ),
                    details={
                        "draft_id": draft.draft_id,
                        "video_id": vid,
                        "duration_seconds": fresh.duration_seconds,
                        "max_allowed_seconds": max_allowed_seconds,
                        "reason": "max_video_duration_exceeded",
                    },
                )

    # 6. Total duration window re-verification
    total_fresh_duration = sum(
        (fresh_by_id[vid].duration_seconds or 0) for vid in draft.ordered_video_ids
    )
    min_window = draft.target_min_seconds
    max_window = draft.target_max_seconds

    if total_fresh_duration < min_window:
        raise ToolError(
            ErrorCode.DRAFT_STALE,
            (
                f"Total duration of approved videos ({total_fresh_duration}s) fell below "
                f"minimum target window ({min_window}s). Zero writes performed."
            ),
            details={
                "draft_id": draft.draft_id,
                "total_duration": total_fresh_duration,
                "min_target": min_window,
                "reason": "duration_below_window",
            },
        )

    if total_fresh_duration > max_window:
        raise ToolError(
            ErrorCode.DRAFT_STALE,
            (
                f"Total duration of approved videos ({total_fresh_duration}s) exceeded "
                f"maximum target window ({max_window}s). Zero writes performed."
            ),
            details={
                "draft_id": draft.draft_id,
                "total_duration": total_fresh_duration,
                "max_target": max_window,
                "reason": "duration_above_window",
            },
        )


async def write_curated_playlist(
    draft: PlaylistDraft,
    provider: YouTubeProvider,
) -> PlaylistWriteOutcome:
    """Execute ordered playlist creation and item insertions with zero write retries (FR-5.5).

    Creates the new playlist with the approved title and privacy setting (default private).
    Inserts approved videos in exact approved order. If an item fails due to a non-fatal error,
    records the failure and continues with subsequent items. If a quota or authorization error
    occurs, halts insertion immediately and marks remaining items as unattempted.
    """
    # 1. Create container playlist
    created = await provider.insert_playlist(
        title=draft.title,
        description=f"Curated playlist: {draft.topic}",
        privacy_status=draft.privacy_status,
    )
    playlist_id = created.playlist_id
    playlist_url = created.url or f"https://www.youtube.com/playlist?list={playlist_id}"

    inserted: list[InsertedVideoItem] = []
    failed: list[FailedVideoItem] = []
    unattempted: list[UnattemptedVideoItem] = []

    # 2. Ordered insertion of approved videos
    for idx, video in enumerate(draft.videos):
        try:
            item_id = await provider.insert_playlist_item(
                playlist_id=playlist_id,
                video_id=video.video_id,
                position=idx,
            )
            inserted.append(
                InsertedVideoItem(
                    video_id=video.video_id,
                    item_id=item_id,
                    title=video.title,
                    channel_title=video.channel_title,
                    duration_seconds=video.duration_seconds,
                    duration_human=video.duration_human,
                    position=idx,
                )
            )
        except ToolError as exc:
            logger.warning(
                "Failed to insert playlist item %s for draft %s: %s",
                video.video_id,
                draft.draft_id,
                exc,
            )
            failed.append(
                FailedVideoItem(
                    video_id=video.video_id,
                    title=video.title,
                    channel_title=video.channel_title,
                    duration_seconds=video.duration_seconds,
                    reason=exc.message,
                    error_code=exc.code.value,
                )
            )
            if exc.code in _FATAL_WRITE_ERROR_CODES:
                halt_reason = (
                    f"Halted due to preceding quota or authorization error ({exc.code.value})."
                )
                for rem in draft.videos[idx + 1 :]:
                    unattempted.append(
                        UnattemptedVideoItem(
                            video_id=rem.video_id,
                            title=rem.title,
                            channel_title=rem.channel_title,
                            duration_seconds=rem.duration_seconds,
                            reason=halt_reason,
                        )
                    )
                break
        except Exception as exc:  # pragma: no cover
            logger.error(
                "Unexpected failure inserting playlist item %s for draft %s: %s",
                video.video_id,
                draft.draft_id,
                exc,
            )
            failed.append(
                FailedVideoItem(
                    video_id=video.video_id,
                    title=video.title,
                    channel_title=video.channel_title,
                    duration_seconds=video.duration_seconds,
                    reason=str(exc),
                    error_code="UNKNOWN_ERROR",
                )
            )

    # 3. Evaluate outcome status and unmet constraints
    actual_duration = sum(item.duration_seconds for item in inserted)
    unmet: list[str] = []

    if failed or unattempted:
        unmet.append(f"Failed to insert {len(failed)} items; {len(unattempted)} items unattempted.")

    min_window = draft.target_min_seconds
    max_window = draft.target_max_seconds

    if actual_duration < min_window:
        unmet.append(
            f"Actual total duration {format_duration(actual_duration)} ({actual_duration}s) "
            f"is below target window floor {format_duration(min_window)} ({min_window}s)."
        )
    elif actual_duration > max_window:
        unmet.append(
            f"Actual total duration {format_duration(actual_duration)} ({actual_duration}s) "
            f"exceeds target window ceiling {format_duration(max_window)} ({max_window}s)."
        )

    status: Literal["COMPLETE", "PARTIAL"] = (
        "COMPLETE" if (len(inserted) == len(draft.videos) and not unmet) else "PARTIAL"
    )

    return PlaylistWriteOutcome(
        status=status,
        playlist_id=playlist_id,
        playlist_url=playlist_url,
        title=draft.title,
        privacy_status=draft.privacy_status,
        target_total_minutes=draft.constraints.target_total_minutes,
        total_duration_seconds=actual_duration,
        total_duration_human=format_duration(actual_duration),
        total_duration_clock=format_duration_clock(actual_duration),
        video_count=len(draft.videos),
        inserted_videos=tuple(inserted),
        failed_videos=tuple(failed),
        unattempted_videos=tuple(unattempted),
        unmet_constraints=tuple(unmet),
    )
