"""Constrained playlist curation domain modules (MF-08..MF-11, MF-14)."""

from __future__ import annotations

from yt_intel_mcp.playlist.constraints import (
    MAX_PLAYLIST_VIDEOS,
    MAX_TARGET_MINUTES,
    MAX_TOLERANCE_PERCENT,
    MAX_VIDEO_LIMIT_MINUTES,
    MIN_PLAYLIST_VIDEOS,
    MIN_TARGET_MINUTES,
    MIN_TOLERANCE_PERCENT,
    MIN_VIDEO_LIMIT_MINUTES,
    PlaylistConstraints,
    build_playlist_constraints,
    evaluate_selection_constraints,
    is_total_in_window,
    is_video_duration_eligible,
)
from yt_intel_mcp.playlist.drafts import (
    DRAFT_ID_RE,
    DraftStore,
    DraftVideo,
    PlaylistDraft,
)
from yt_intel_mcp.playlist.language import (
    UNVERIFIED_AUDIO_LANGUAGE_LABEL,
    AudioLanguageStatus,
    LanguageCheckResult,
    evaluate_video_audio_language,
    filter_videos_by_language,
    is_video_language_eligible,
    primary_language_subtag,
)
from yt_intel_mcp.playlist.solver import (
    BindingConstraint,
    PlaylistSolution,
    SelectedPlaylistVideo,
    SolverAlgorithm,
    score_candidates_for_topic,
    solve_playlist_selection,
)
from yt_intel_mcp.playlist.writer import (
    FailedVideoItem,
    InsertedVideoItem,
    PlaylistWriteOutcome,
    UnattemptedVideoItem,
    check_draft_staleness,
    write_curated_playlist,
)

__all__ = [
    "DRAFT_ID_RE",
    "MAX_PLAYLIST_VIDEOS",
    "MAX_TARGET_MINUTES",
    "MAX_TOLERANCE_PERCENT",
    "MAX_VIDEO_LIMIT_MINUTES",
    "MIN_PLAYLIST_VIDEOS",
    "MIN_TARGET_MINUTES",
    "MIN_TOLERANCE_PERCENT",
    "MIN_VIDEO_LIMIT_MINUTES",
    "UNVERIFIED_AUDIO_LANGUAGE_LABEL",
    "AudioLanguageStatus",
    "BindingConstraint",
    "DraftStore",
    "DraftVideo",
    "FailedVideoItem",
    "InsertedVideoItem",
    "LanguageCheckResult",
    "PlaylistConstraints",
    "PlaylistDraft",
    "PlaylistSolution",
    "PlaylistWriteOutcome",
    "SelectedPlaylistVideo",
    "SolverAlgorithm",
    "UnattemptedVideoItem",
    "build_playlist_constraints",
    "check_draft_staleness",
    "evaluate_selection_constraints",
    "evaluate_video_audio_language",
    "filter_videos_by_language",
    "is_total_in_window",
    "is_video_duration_eligible",
    "is_video_language_eligible",
    "primary_language_subtag",
    "score_candidates_for_topic",
    "solve_playlist_selection",
    "write_curated_playlist",
]
