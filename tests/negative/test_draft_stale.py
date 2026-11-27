"""Negative tests for stale draft detection before playlist writes.

Covers MF-14 and NT_DRAFT_STALE.
"""

# ruff: noqa: N802
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from yt_intel_mcp.confirmation import ConfirmationDecision, ConfirmationTokenStore
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import ChannelMeta, CostEstimate, VideoMeta
from yt_intel_mcp.playlist.constraints import build_playlist_constraints
from yt_intel_mcp.playlist.drafts import DraftStore, PlaylistDraft
from yt_intel_mcp.playlist.solver import solve_playlist_selection
from yt_intel_mcp.playlist.writer import check_draft_staleness
from yt_intel_mcp.quota.guard import QuotaStatus
from yt_intel_mcp.tools.create_curated_playlist import execute_create_curated_playlist


def _build_test_draft(
    *,
    video_durations: tuple[int, ...] = (600, 600, 600),
    target_total_minutes: int = 30,
    tolerance_percent: int = 10,
    language: str = "en",
    max_video_minutes: int | None = None,
) -> PlaylistDraft:
    """Helper to build an immutable PlaylistDraft."""
    current = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    draft_store = DraftStore(clock=lambda: current)
    constraints = build_playlist_constraints(
        topic="algorithms",
        target_total_minutes=target_total_minutes,
        tolerance_percent=tolerance_percent,
        max_video_minutes=max_video_minutes,
        language=language,
        allow_unknown_language=False,
        title="Curated Algorithms",
        privacy_status="private",
    )
    videos = [
        VideoMeta(
            video_id=f"vid_algo_{idx:02d}",
            title=f"Algorithm Lecture Part {idx}",
            channel_id=f"UC_ALGO_{idx}",
            channel_title="CS Department",
            duration_seconds=dur,
            default_audio_language=language,
        )
        for idx, dur in enumerate(video_durations, start=1)
    ]
    solution = solve_playlist_selection(videos, constraints)
    return draft_store.create_from_solution(constraints, solution)


class _DummyQuotaGuard:
    def estimate(self, operation: str, *, count: int = 1) -> CostEstimate:
        return CostEstimate(units=count, search_calls=0, operation=operation)

    def preflight(self, cost: CostEstimate) -> QuotaStatus:
        return QuotaStatus(
            units_used=0,
            units_limit=10000,
            units_remaining=10000,
            search_calls_used=0,
            search_calls_limit=100,
            search_calls_remaining=100,
            reset_at=datetime.now(UTC),
        )

    def charge(self, cost: CostEstimate) -> QuotaStatus:
        return self.preflight(cost)

    def mark_upstream_exhausted(self, reset_at: datetime | None = None) -> QuotaStatus:
        return self.preflight(CostEstimate(0, 0, "mock"))


class _MockStaleProvider:
    def __init__(self, fresh_videos: list[VideoMeta]) -> None:
        self.fresh_videos = fresh_videos
        self.inserted_playlists: list[dict[str, Any]] = []
        self.inserted_items: list[dict[str, Any]] = []
        self._my_channel = ChannelMeta(channel_id="UC_TEST_USER", title="Test User")

    async def get_my_channel(self) -> ChannelMeta:
        return self._my_channel

    async def get_videos(self, video_ids: list[str]) -> list[VideoMeta]:
        id_set = set(video_ids)
        return [v for v in self.fresh_videos if v.video_id in id_set]

    async def insert_playlist(self, **kwargs: Any) -> Any:
        self.inserted_playlists.append(kwargs)
        raise AssertionError("Write dispatched on stale draft!")

    async def insert_playlist_item(self, **kwargs: Any) -> str:
        self.inserted_items.append(kwargs)
        raise AssertionError("Item insert dispatched on stale draft!")


def test_NT_DRAFT_STALE_missing_video_raises_draft_stale() -> None:
    """Verify missing video in fresh query raises DRAFT_STALE (FR-5.5(1), INV-15)."""
    draft = _build_test_draft()
    # Return only 2 of the 3 approved videos
    fresh = [
        VideoMeta(
            video_id=draft.ordered_video_ids[0],
            title="Part 1",
            duration_seconds=600,
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[1],
            title="Part 2",
            duration_seconds=600,
            default_audio_language="en",
        ),
    ]

    with pytest.raises(ToolError) as exc_info:
        check_draft_staleness(draft, fresh)

    err = exc_info.value
    assert err.code is ErrorCode.DRAFT_STALE
    assert draft.ordered_video_ids[2] in err.message
    assert err.details["reason"] == "missing_or_deleted"


def test_NT_DRAFT_STALE_live_or_zero_duration_raises_draft_stale() -> None:
    """Verify video that transitioned to live stream raises DRAFT_STALE (FR-5.5(1))."""
    draft = _build_test_draft()
    fresh = [
        VideoMeta(
            video_id=draft.ordered_video_ids[0],
            title="Part 1",
            duration_seconds=600,
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[1],
            title="Part 2 (now live)",
            duration_seconds=0,  # live or zero duration
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[2],
            title="Part 3",
            duration_seconds=600,
            default_audio_language="en",
        ),
    ]

    with pytest.raises(ToolError) as exc_info:
        check_draft_staleness(draft, fresh)

    err = exc_info.value
    assert err.code is ErrorCode.DRAFT_STALE
    assert err.details["reason"] == "live_or_zero_duration"


def test_NT_DRAFT_STALE_duration_changed_raises_draft_stale() -> None:
    """Verify altered duration raises DRAFT_STALE (FR-5.5(1))."""
    draft = _build_test_draft()
    fresh = [
        VideoMeta(
            video_id=draft.ordered_video_ids[0],
            title="Part 1",
            duration_seconds=600,
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[1],
            title="Part 2",
            duration_seconds=850,  # duration changed
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[2],
            title="Part 3",
            duration_seconds=600,
            default_audio_language="en",
        ),
    ]

    with pytest.raises(ToolError) as exc_info:
        check_draft_staleness(draft, fresh)

    err = exc_info.value
    assert err.code is ErrorCode.DRAFT_STALE
    assert err.details["reason"] == "duration_changed"
    assert err.details["expected_duration"] == 600
    assert err.details["actual_duration"] == 850


def test_NT_DRAFT_STALE_audio_language_changed_raises_draft_stale() -> None:
    """Verify audio language changed to non-matching language raises DRAFT_STALE."""
    draft = _build_test_draft(language="en")
    fresh = [
        VideoMeta(
            video_id=draft.ordered_video_ids[0],
            title="Part 1",
            duration_seconds=600,
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[1],
            title="Part 2",
            duration_seconds=600,
            default_audio_language="es",  # changed to Spanish
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[2],
            title="Part 3",
            duration_seconds=600,
            default_audio_language="en",
        ),
    ]

    with pytest.raises(ToolError) as exc_info:
        check_draft_staleness(draft, fresh)

    err = exc_info.value
    assert err.code is ErrorCode.DRAFT_STALE
    assert err.details["reason"] == "language_ineligible"


def test_NT_DRAFT_STALE_max_video_minutes_exceeded_raises_draft_stale() -> None:
    """Verify video exceeding max_video_minutes raises DRAFT_STALE (FR-5.1, FR-5.5(1))."""
    draft = _build_test_draft(
        video_durations=(500, 500, 500),
        target_total_minutes=25,
        max_video_minutes=10,  # 600s max
    )
    fresh = [
        VideoMeta(
            video_id=draft.ordered_video_ids[0],
            title="Part 1",
            duration_seconds=500,
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[1],
            title="Part 2",
            duration_seconds=650,  # exceeds 10m (600s)
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[2],
            title="Part 3",
            duration_seconds=500,
            default_audio_language="en",
        ),
    ]

    with pytest.raises(ToolError) as exc_info:
        check_draft_staleness(draft, fresh)

    err = exc_info.value
    assert err.code is ErrorCode.DRAFT_STALE


@pytest.mark.anyio
async def test_NT_DRAFT_STALE_execute_create_curated_playlist_performs_zero_writes() -> None:
    """End-to-end tool check: stale pre-check raises DRAFT_STALE with 0 writes dispatched."""
    current = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    draft_store = DraftStore(clock=lambda: current)
    token_store = ConfirmationTokenStore(clock=lambda: current)

    draft = _build_test_draft()
    draft_store._drafts[draft.draft_id] = draft

    # Pre-mint an ACCEPT token so confirmation passes cleanly
    _token = token_store.mint_for_draft(
        draft,
        "UC_TEST_USER",
        decision=ConfirmationDecision.ACCEPT,
    )

    class _MockElicitationSession:
        elicitation_enabled = True

        async def _elicitation_callback(self, ctx: Any, req: Any) -> Any:
            import mcp.types as types

            return types.ElicitResult(action="accept", content={"confirm": True})

    # Provider returns stale video with altered duration
    stale_fresh = [
        VideoMeta(
            video_id=draft.ordered_video_ids[0],
            title="Part 1",
            duration_seconds=900,  # changed!
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[1],
            title="Part 2",
            duration_seconds=600,
            default_audio_language="en",
        ),
        VideoMeta(
            video_id=draft.ordered_video_ids[2],
            title="Part 3",
            duration_seconds=600,
            default_audio_language="en",
        ),
    ]
    provider = _MockStaleProvider(stale_fresh)
    guard = _DummyQuotaGuard()

    with pytest.raises(ToolError) as exc_info:
        await execute_create_curated_playlist(
            {"draft_id": draft.draft_id},
            provider=provider,  # type: ignore[arg-type]
            quota_guard=guard,
            draft_store=draft_store,
            confirmation_store=token_store,
            session=_MockElicitationSession(),
            channel_id_override="UC_TEST_USER",
        )

    err = exc_info.value
    assert err.code is ErrorCode.DRAFT_STALE
    assert "duration changed" in err.message

    # Assert ZERO write operations were dispatched
    assert len(provider.inserted_playlists) == 0
    assert len(provider.inserted_items) == 0
