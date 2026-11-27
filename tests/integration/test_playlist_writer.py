"""Integration tests for playlist writer and partial outcome reporting.

Covers MF-14, IT_DRAFT, and IT_DRAFT_PARTIAL.
"""

# ruff: noqa: N802
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import pytest

from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import ChannelMeta, CreatedPlaylist, VideoMeta
from yt_intel_mcp.playlist.constraints import build_playlist_constraints
from yt_intel_mcp.playlist.drafts import DraftStore, PlaylistDraft
from yt_intel_mcp.playlist.solver import solve_playlist_selection
from yt_intel_mcp.playlist.writer import (
    PlaylistWriteOutcome,
    write_curated_playlist,
)


def _build_test_draft(
    *,
    video_durations: tuple[int, ...] = (600, 600, 600),
    target_total_minutes: int = 30,
    tolerance_percent: int = 10,
    topic: str = "quantum algorithms",
    title: str = "Curated Quantum Algorithms",
) -> PlaylistDraft:
    """Helper to build an immutable PlaylistDraft with specific video durations."""
    current = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    draft_store = DraftStore(clock=lambda: current)
    constraints = build_playlist_constraints(
        topic=topic,
        target_total_minutes=target_total_minutes,
        tolerance_percent=tolerance_percent,
        title=title,
        privacy_status="private",
    )
    videos = [
        VideoMeta(
            video_id=f"vid_qc_{idx:02d}",
            title=f"Quantum Lecture Part {idx}",
            channel_id=f"UC_QC_{idx}",
            channel_title="Physics Institute",
            duration_seconds=dur,
            default_audio_language="en",
        )
        for idx, dur in enumerate(video_durations, start=1)
    ]
    solution = solve_playlist_selection(videos, constraints)
    return draft_store.create_from_solution(constraints, solution)


class _RecordingProvider:
    """Mock provider recording calls, write counts, and allowing simulated item errors."""

    def __init__(self) -> None:
        self.inserted_playlists: list[dict[str, Any]] = []
        self.inserted_items: list[dict[str, Any]] = []
        self.item_errors: dict[str, ToolError] = {}
        self.playlist_error: ToolError | None = None
        self.insert_item_attempts: dict[str, int] = {}

    async def get_my_channel(self) -> ChannelMeta:
        return ChannelMeta(channel_id="UC_TEST_CHANNEL", title="Test Channel")

    async def insert_playlist(
        self,
        *,
        title: str,
        description: str = "",
        privacy_status: Literal["private", "unlisted", "public"] = "private",
    ) -> CreatedPlaylist:
        if self.playlist_error is not None:
            raise self.playlist_error
        pl_id = f"PL_TEST_{len(self.inserted_playlists) + 1:04d}"
        created = CreatedPlaylist(
            playlist_id=pl_id,
            title=title,
            description=description,
            privacy_status=privacy_status,
            channel_id="UC_TEST_CHANNEL",
            url=f"https://www.youtube.com/playlist?list={pl_id}",
        )
        self.inserted_playlists.append(
            {
                "title": title,
                "description": description,
                "privacy_status": privacy_status,
                "playlist_id": pl_id,
            }
        )
        return created

    async def insert_playlist_item(
        self,
        *,
        playlist_id: str,
        video_id: str,
        position: int | None = None,
    ) -> str:
        self.insert_item_attempts[video_id] = self.insert_item_attempts.get(video_id, 0) + 1
        if video_id in self.item_errors:
            raise self.item_errors[video_id]
        item_id = f"PLI_{video_id}_{len(self.inserted_items) + 1}"
        self.inserted_items.append(
            {
                "playlist_id": playlist_id,
                "video_id": video_id,
                "position": position,
                "item_id": item_id,
            }
        )
        return item_id


@pytest.mark.anyio
async def test_IT_DRAFT_successful_complete_playlist_creation() -> None:
    """Verify clean complete write path with 0 retries and exact ordered insertion."""
    draft = _build_test_draft(video_durations=(600, 600, 600))
    provider = _RecordingProvider()

    outcome = await write_curated_playlist(draft, provider)  # type: ignore[arg-type]

    assert isinstance(outcome, PlaylistWriteOutcome)
    assert outcome.status == "COMPLETE"
    assert outcome.playlist_id == "PL_TEST_0001"
    assert outcome.playlist_url == "https://www.youtube.com/playlist?list=PL_TEST_0001"
    assert outcome.title == "Curated Quantum Algorithms"
    assert outcome.privacy_status == "private"
    assert outcome.total_duration_seconds == 1800
    assert outcome.video_count == 3
    assert len(outcome.inserted_videos) == 3
    assert len(outcome.failed_videos) == 0
    assert len(outcome.unattempted_videos) == 0
    assert len(outcome.unmet_constraints) == 0

    # Verify provider was called in exact approved order with 0 retries
    assert len(provider.inserted_playlists) == 1
    assert provider.inserted_playlists[0]["privacy_status"] == "private"
    assert len(provider.inserted_items) == 3
    for idx, expected_vid in enumerate(draft.ordered_video_ids):
        record = provider.inserted_items[idx]
        assert record["video_id"] == expected_vid
        assert record["position"] == idx
        # Verify exactly 1 insertion attempt (0 retries)
        assert provider.insert_item_attempts[expected_vid] == 1

    payload = outcome.to_dict()
    assert payload["status"] == "COMPLETE"
    assert payload["video_count"] == 3
    assert payload["approved_video_count"] == 3


@pytest.mark.anyio
async def test_IT_DRAFT_PARTIAL_item_failure_continues_subsequent_inserts() -> None:
    """Verify non-fatal item error records failure and continues subsequent items (INV-17)."""
    draft = _build_test_draft(video_durations=(600, 600, 600), target_total_minutes=30)
    provider = _RecordingProvider()

    # Fail the second video with a non-fatal item error
    failed_vid = draft.ordered_video_ids[1]
    provider.item_errors[failed_vid] = ToolError(
        ErrorCode.VIDEO_UNAVAILABLE,
        f"Video {failed_vid} is blocked in country",
        details={"video_id": failed_vid},
    )

    outcome = await write_curated_playlist(draft, provider)  # type: ignore[arg-type]

    assert outcome.status == "PARTIAL"
    assert len(outcome.inserted_videos) == 2
    assert len(outcome.failed_videos) == 1
    assert len(outcome.unattempted_videos) == 0

    # Failed item recorded accurately with reason
    failed_item = outcome.failed_videos[0]
    assert failed_item.video_id == failed_vid
    assert failed_item.error_code == "VIDEO_UNAVAILABLE"
    assert "blocked in country" in failed_item.reason

    # Inserted videos are items 0 and 2
    inserted_vids = [item.video_id for item in outcome.inserted_videos]
    assert inserted_vids == [draft.ordered_video_ids[0], draft.ordered_video_ids[2]]

    # 1200s total duration is below 30m window floor (27m = 1620s)
    assert outcome.total_duration_seconds == 1200
    assert any("below target window floor" in msg for msg in outcome.unmet_constraints)

    # Provider attempted item 1, item 2 (failed), and item 3 (succeeded)
    assert len(provider.inserted_items) == 2
    assert provider.insert_item_attempts[draft.ordered_video_ids[0]] == 1
    assert provider.insert_item_attempts[failed_vid] == 1
    assert provider.insert_item_attempts[draft.ordered_video_ids[2]] == 1


@pytest.mark.anyio
async def test_IT_DRAFT_PARTIAL_quota_exhausted_halts_immediately_and_marks_unattempted() -> None:
    """Verify quota or auth error halts loop immediately and marks unattempted items."""
    draft = _build_test_draft(
        video_durations=(350, 400, 350, 350), target_total_minutes=25, tolerance_percent=10
    )
    provider = _RecordingProvider()

    # Fail the second video with upstream quota exhaustion
    halt_vid = draft.ordered_video_ids[1]
    provider.item_errors[halt_vid] = ToolError(
        ErrorCode.QUOTA_EXHAUSTED_UPSTREAM,
        "Daily YouTube Data API v3 quota exhausted upstream",
        details={"endpoint": "playlistItems.insert"},
    )

    outcome = await write_curated_playlist(draft, provider)  # type: ignore[arg-type]

    assert outcome.status == "PARTIAL"
    assert len(outcome.inserted_videos) == 1
    assert len(outcome.failed_videos) == 1
    assert len(outcome.unattempted_videos) == 2

    # Item 1 succeeded
    assert outcome.inserted_videos[0].video_id == draft.ordered_video_ids[0]

    # Item 2 recorded as failed with QUOTA_EXHAUSTED_UPSTREAM
    assert outcome.failed_videos[0].video_id == halt_vid
    assert outcome.failed_videos[0].error_code == "QUOTA_EXHAUSTED_UPSTREAM"

    # Items 3 and 4 marked as unattempted
    unattempted_vids = [item.video_id for item in outcome.unattempted_videos]
    assert unattempted_vids == [draft.ordered_video_ids[2], draft.ordered_video_ids[3]]
    for unattempted_item in outcome.unattempted_videos:
        assert "Halted due to preceding quota or authorization error" in unattempted_item.reason

    # Verify provider never attempted items 3 or 4
    assert draft.ordered_video_ids[2] not in provider.insert_item_attempts
    assert draft.ordered_video_ids[3] not in provider.insert_item_attempts


@pytest.mark.anyio
async def test_IT_DRAFT_zero_retries_on_write() -> None:
    """Verify write operations are dispatched with exactly zero retries (NFR-8, INV-24)."""
    draft = _build_test_draft(video_durations=(600, 600), target_total_minutes=20)
    provider = _RecordingProvider()

    outcome = await write_curated_playlist(draft, provider)  # type: ignore[arg-type]
    assert outcome.status == "COMPLETE"

    for vid in draft.ordered_video_ids:
        assert provider.insert_item_attempts[vid] == 1
