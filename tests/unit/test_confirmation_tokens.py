"""Unit tests for ConfirmationToken and ConfirmationTokenStore (MF-12, FR-5.4, INV-14)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from yt_intel_mcp.config import DraftConfig
from yt_intel_mcp.confirmation import (
    CONFIRMATION_TOKEN_ID_RE,
    ConfirmationDecision,
    ConfirmationToken,
    ConfirmationTokenStore,
)
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.playlist import (
    DraftStore,
    PlaylistDraft,
    build_playlist_constraints,
    solve_playlist_selection,
)


def _make_sample_draft(now: datetime) -> PlaylistDraft:
    draft_store = DraftStore(DraftConfig(ttl_seconds=600), clock=lambda: now)
    constraints = build_playlist_constraints(
        topic="raft consensus",
        target_total_minutes=20,
        title="Raft Protocol Overview",
        privacy_status="private",
    )
    videos = [
        VideoMeta(
            video_id="vid_raft_1",
            title="Raft Algorithm Explained",
            channel_id="UC_RAFT",
            channel_title="Consensus Labs",
            duration_seconds=600,
            default_audio_language="en",
        ),
        VideoMeta(
            video_id="vid_raft_2",
            title="Raft Leader Election",
            channel_id="UC_RAFT",
            channel_title="Consensus Labs",
            duration_seconds=600,
            default_audio_language="en",
        ),
    ]
    solution = solve_playlist_selection(videos, constraints)
    return draft_store.create_from_solution(constraints, solution)


def test_mint_and_get_lifecycle() -> None:
    now = datetime(2026, 11, 27, 11, 0, tzinfo=UTC)
    store = ConfirmationTokenStore(clock=lambda: now)

    draft = _make_sample_draft(now)
    token = store.mint_for_draft(draft, channel_id="UC_AUTH_USER")

    assert isinstance(token, ConfirmationToken)
    assert CONFIRMATION_TOKEN_ID_RE.fullmatch(token.token_id)
    assert token.channel_id == "UC_AUTH_USER"
    assert token.draft_id == draft.draft_id
    assert token.ordered_video_ids == ("vid_raft_1", "vid_raft_2")
    assert token.title == "Raft Protocol Overview"
    assert token.privacy_status == "private"
    assert token.expires_at_utc == draft.expires_at_utc
    assert token.decision is ConfirmationDecision.ACCEPT
    assert token.is_accepted is True
    assert token.consumed is False
    assert token.consumed_at_utc is None

    # Lookup by draft id and token id
    assert store.get_for_draft(draft.draft_id) is token
    assert store.get(token.token_id) is token
    assert store.get_for_draft("nonexistent") is None
    assert store.get("nonexistent") is None
    assert store.get_for_draft(123) is None  # type: ignore[arg-type]
    assert store.get(123) is None  # type: ignore[arg-type]


def test_mint_argument_validation() -> None:
    now = datetime(2026, 11, 27, 11, 0, tzinfo=UTC)
    store = ConfirmationTokenStore(clock=lambda: now)

    with pytest.raises(ToolError) as exc:
        store.mint(
            channel_id="",
            draft_id="draft_1",
            ordered_video_ids=["v1"],
            title="Title",
            privacy_status="private",
            expires_at_utc=now,
        )
    assert exc.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc.value.details["field"] == "channel_id"

    with pytest.raises(ToolError) as exc:
        store.mint(
            channel_id="UC_1",
            draft_id="",
            ordered_video_ids=["v1"],
            title="Title",
            privacy_status="private",
            expires_at_utc=now,
        )
    assert exc.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc.value.details["field"] == "draft_id"

    with pytest.raises(ToolError) as exc:
        store.mint(
            channel_id="UC_1",
            draft_id="draft_1",
            ordered_video_ids=["v1"],
            title="Title",
            privacy_status="private",
            expires_at_utc=now,
            decision="unsupported_decision",
        )
    assert exc.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc.value.details["field"] == "decision"

    with pytest.raises(ToolError) as exc:
        store.mint_for_draft("not a draft", channel_id="UC_1")  # type: ignore[arg-type]
    assert exc.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc.value.details["field"] == "draft"


def test_purge_expired_tokens() -> None:
    now = datetime(2026, 11, 27, 11, 0, tzinfo=UTC)
    store = ConfirmationTokenStore(clock=lambda: now)

    draft1 = _make_sample_draft(now)
    token1 = store.mint_for_draft(draft1, channel_id="UC_USER_1")

    # Draft 2 with later expiry
    draft2 = _make_sample_draft(now + timedelta(seconds=300))
    token2 = store.mint_for_draft(draft2, channel_id="UC_USER_2")

    assert set(store.list_active_draft_ids(now)) == {draft1.draft_id, draft2.draft_id}

    # At now + 601s, draft 1 is expired, draft 2 is still valid
    check_time = now + timedelta(seconds=601)
    assert store.list_active_draft_ids(check_time) == (draft2.draft_id,)

    purged_count = store.purge_expired(check_time)
    assert purged_count == 1
    assert store.get_for_draft(draft1.draft_id) is None
    assert store.get(token1.token_id) is None
    assert store.get_for_draft(draft2.draft_id) is token2


def test_clear_tokens() -> None:
    now = datetime(2026, 11, 27, 11, 0, tzinfo=UTC)
    store = ConfirmationTokenStore(clock=lambda: now)

    draft = _make_sample_draft(now)
    store.mint_for_draft(draft, channel_id="UC_USER")

    assert len(store.list_active_draft_ids()) == 1
    store.clear()
    assert len(store.list_active_draft_ids()) == 0
    assert store.get_for_draft(draft.draft_id) is None


def test_consume_with_unregistered_token_object() -> None:
    now = datetime(2026, 11, 27, 11, 0, tzinfo=UTC)
    store = ConfirmationTokenStore(clock=lambda: now)
    draft = _make_sample_draft(now)

    foreign_token = ConfirmationToken(
        token_id="tok_foreign_unregistered_secret",
        channel_id="UC_USER",
        draft_id=draft.draft_id,
        ordered_video_ids=draft.ordered_video_ids,
        title=draft.title,
        privacy_status=draft.privacy_status,
        expires_at_utc=draft.expires_at_utc,
        decision=ConfirmationDecision.ACCEPT,
        created_at_utc=now,
    )

    with pytest.raises(ToolError) as exc:
        store.consume(foreign_token, draft=draft, channel_id="UC_USER")
    assert exc.value.code is ErrorCode.CONFIRMATION_MISMATCH


def test_consume_for_draft_invalid_draft_id_type() -> None:
    now = datetime(2026, 11, 27, 11, 0, tzinfo=UTC)
    store = ConfirmationTokenStore(clock=lambda: now)
    draft = _make_sample_draft(now)

    with pytest.raises(ToolError) as exc:
        store.consume_for_draft(12345, draft=draft, channel_id="UC_USER")  # type: ignore[arg-type]
    assert exc.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc.value.details["field"] == "draft_id"


def test_consume_invalid_draft_type() -> None:
    now = datetime(2026, 11, 27, 11, 0, tzinfo=UTC)
    store = ConfirmationTokenStore(clock=lambda: now)
    draft = _make_sample_draft(now)
    token = store.mint_for_draft(draft, channel_id="UC_USER")

    with pytest.raises(ToolError) as exc:
        store.consume(token, draft="not a draft", channel_id="UC_USER")  # type: ignore[arg-type]
    assert exc.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc.value.details["field"] == "draft"
