"""Unit tests for immutable expiring PlaylistDraft and DraftStore (MF-11, FR-5.3, INV-12)."""

# ruff: noqa: N802
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from yt_intel_mcp.config import DraftConfig, QuotaConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import QuotaUsed, VideoMeta
from yt_intel_mcp.playlist import (
    DRAFT_ID_RE,
    UNVERIFIED_AUDIO_LANGUAGE_LABEL,
    DraftStore,
    DraftVideo,
    PlaylistDraft,
    build_playlist_constraints,
    solve_playlist_selection,
)
from yt_intel_mcp.quota.guard import QuotaStatus
from yt_intel_mcp.tools import estimate_draft_workflow_cost, validate_draft_arguments


def test_INV_12_draft_immutability_sanitization_and_10_minute_expiry() -> None:
    now = datetime(2026, 11, 26, 15, 0, tzinfo=UTC)
    store = DraftStore(DraftConfig(ttl_seconds=600), clock=lambda: now)
    assert store.ttl_seconds == 600

    constraints = build_playlist_constraints(
        topic="python asyncio",
        target_total_minutes=30,
        tolerance_percent=5,
        language="en",
        allow_unknown_language=True,
        title="My <Python>\u200b Asyncio https://evil.example List",
    )
    videos = [
        VideoMeta(
            video_id="vid_clean_1",
            title="Asyncio\u202e Secrets https://evil.example/a",
            channel_id="UC_1",
            channel_title="Systems\u200b Craft https://evil.example/c",
            duration_seconds=960,
            default_audio_language="en-US",
        ),
        VideoMeta(
            video_id="vid_unk_002",
            title="Python Coroutines Unverified",
            channel_id="UC_2",
            channel_title="",
            duration_seconds=840,
            default_audio_language=None,
        ),
    ]
    solution = solve_playlist_selection(videos, constraints)
    draft = store.create_from_solution(constraints, solution)

    assert isinstance(draft, PlaylistDraft)
    assert DRAFT_ID_RE.fullmatch(draft.draft_id)
    assert draft.title == "My <Python> Asyncio List"
    assert draft.privacy_status == "private"
    assert draft.total_duration_seconds == 1800
    assert draft.total_duration_human == "30m"
    assert draft.ordered_video_ids == ("vid_clean_1", "vid_unk_002")

    first: DraftVideo = draft.videos[0]
    assert "https://" not in first.title
    assert "\u202e" not in first.title
    assert "https://" not in first.channel_title
    assert draft.videos[1].channel_title == "UC_2"
    assert draft.videos[1].is_audio_language_unverified is True
    assert draft.videos[1].audio_language_label == UNVERIFIED_AUDIO_LANGUAGE_LABEL

    # Immutability: frozen dataclass raises FrozenInstanceError on field mutation
    with pytest.raises(FrozenInstanceError):
        draft.title = "Tampered Title"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first.duration_seconds = 1  # type: ignore[misc]

    view = draft.to_view(now_utc=now)
    view["videos"].append({"video_id": "injected"})
    view["title"] = "Mutated Copy"
    assert len(draft.videos) == 2
    assert draft.title == "My <Python> Asyncio List"

    # Active at 599s, expired strictly at 600s (10 minutes)
    now = now + timedelta(seconds=599)
    assert store.get(draft.draft_id) == draft
    assert store.list_active_ids() == (draft.draft_id,)

    now = datetime(2026, 11, 26, 15, 0, tzinfo=UTC) + timedelta(seconds=600)
    with pytest.raises(ToolError) as expired_err:
        store.get(draft.draft_id)
    assert expired_err.value.code is ErrorCode.DRAFT_EXPIRED
    assert expired_err.value.details["draft_id"] == draft.draft_id
    assert store.list_active_ids() == ()
    assert store.purge_expired() == 1

    # After purge, lookup raises INVALID_ARGUMENT cleanly
    with pytest.raises(ToolError) as unknown_err:
        store.get(draft.draft_id)
    assert unknown_err.value.code is ErrorCode.INVALID_ARGUMENT
    assert unknown_err.value.details["field"] == "draft_id"


def test_INV_02_draft_store_and_argument_validation_guards() -> None:
    with pytest.raises(ValueError, match="ttl_seconds"):
        DraftStore(DraftConfig(ttl_seconds=0))

    store = DraftStore()
    for bad_id in (123, "", "short", "bad id spaces", "draft_x" * 25):
        with pytest.raises(ToolError) as err:
            store.get(bad_id)
        assert err.value.code is ErrorCode.INVALID_ARGUMENT
        assert err.value.details["field"] == "draft_id"

    with pytest.raises(ToolError) as not_mapping:
        validate_draft_arguments(["not", "a", "dict"])  # type: ignore[arg-type]
    assert not_mapping.value.code is ErrorCode.INVALID_ARGUMENT

    with pytest.raises(ToolError) as extra_err:
        validate_draft_arguments({"topic": "python", "target_total_minutes": 20, "approved": True})
    assert extra_err.value.code is ErrorCode.INVALID_ARGUMENT
    assert extra_err.value.details["field"] == "approved"

    with pytest.raises(ToolError) as missing_err:
        validate_draft_arguments({"topic": "python"})
    assert missing_err.value.code is ErrorCode.INVALID_ARGUMENT
    assert missing_err.value.details["field"] == "target_total_minutes"

    with pytest.raises(ToolError) as url_only_topic:
        validate_draft_arguments({"topic": "https://evil.invalid/only", "target_total_minutes": 20})
    assert url_only_topic.value.code is ErrorCode.INVALID_ARGUMENT
    assert url_only_topic.value.details["field"] == "topic"

    # Naive datetime normalization + G-03 workflow cost estimate check
    naive_store = DraftStore(clock=lambda: datetime(2026, 11, 26, 15, 0))
    constraints = validate_draft_arguments(
        {"topic": "python asyncio", "target_total_minutes": 20, "max_videos": 8}
    )
    sol = solve_playlist_selection(
        [VideoMeta(video_id="V1", title="Python Asyncio", duration_seconds=1200)],
        constraints,
    )
    created = naive_store.create_from_solution(constraints, sol)
    assert created.created_at_utc.tzinfo is UTC
    assert created.is_expired(datetime(2026, 11, 26, 15, 9)) is False
    assert created.is_expired(datetime(2026, 11, 26, 15, 10)) is True

    class _SimpleGuard:
        def __init__(self) -> None:
            self.cfg = QuotaConfig()

        def estimate(self, operation: str, *, count: int = 1) -> object:
            units = 50 * count if "insert" in operation else (count if "videos" in operation else 0)
            searches = count if "search" in operation else 0
            from yt_intel_mcp.models import CostEstimate

            return CostEstimate(units=units, search_calls=searches, operation=operation)

        def preflight(self, cost: object) -> QuotaStatus:  # pragma: no cover
            del cost
            return self.status()

        def charge(self, cost: object) -> QuotaStatus:  # pragma: no cover
            del cost
            return self.status()

        def mark_upstream_exhausted(
            self, reset_at: datetime | None = None
        ) -> QuotaStatus:  # pragma: no cover
            del reset_at
            return self.status()

        def status(self) -> QuotaStatus:  # pragma: no cover
            return QuotaStatus(0, 10000, 10000, 0, 100, 100, datetime.now(UTC))

    est = estimate_draft_workflow_cost(constraints, _SimpleGuard())  # type: ignore[arg-type]
    assert est.units == 455
    assert est.search_calls == 3
    assert QuotaUsed(units=est.units, search_calls=est.search_calls).to_dict() == {
        "units": 455,
        "search_calls": 3,
    }
