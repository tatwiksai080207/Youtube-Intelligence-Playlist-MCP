"""System tests for trusted playlist confirmation channels (MF-13, ST_FR5_CONFIRM, FR-5.4)."""

# ruff: noqa: N802
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from yt_intel_mcp.config import DraftConfig
from yt_intel_mcp.confirmation import (
    ConfirmationDecision,
    ConfirmationToken,
    ConfirmationTokenStore,
    has_elicitation_capability,
    request_trusted_confirmation,
    serve_local_confirmation_page,
)
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.playlist import (
    DraftStore,
    PlaylistDraft,
    build_playlist_constraints,
    solve_playlist_selection,
)


def _build_test_draft(
    store: DraftStore,
    *,
    topic: str = "quantum computing",
    title: str = "Curated Quantum Computing",
    privacy_status: str = "private",
    video_ids: tuple[str, ...] = ("vid_qc_01", "vid_qc_02"),
) -> PlaylistDraft:
    constraints = build_playlist_constraints(
        topic=topic,
        target_total_minutes=30,
        tolerance_percent=10,
        title=title,
        privacy_status=privacy_status,
    )
    videos = [
        VideoMeta(
            video_id=vid,
            title=f"Quantum Lecture Part {idx}",
            channel_id=f"UC_QC_{vid}",
            channel_title="Physics Institute",
            duration_seconds=900,
            default_audio_language="en",
        )
        for idx, vid in enumerate(video_ids, start=1)
    ]
    solution = solve_playlist_selection(videos, constraints)
    return store.create_from_solution(constraints, solution)


@pytest.mark.anyio
async def test_ST_FR5_CONFIRM_elicitation_accept_mints_valid_token(
    system_harness_factory: Callable[..., Any],
) -> None:
    current = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    draft_store = DraftStore(DraftConfig(ttl_seconds=600), clock=lambda: current)
    token_store = ConfirmationTokenStore(clock=lambda: current)
    draft = _build_test_draft(draft_store)

    async with system_harness_factory(
        transport="memory",
        enable_elicitation=True,
        elicitation_action="accept",
    ) as harness:
        assert has_elicitation_capability(harness.session) is True

        token = await request_trusted_confirmation(
            draft,
            "UC_MY_CHANNEL",
            token_store,
            session=harness.session,
            account_name="Alice Researcher",
        )

        assert isinstance(token, ConfirmationToken)
        assert token.is_accepted is True
        assert token.channel_id == "UC_MY_CHANNEL"
        assert token.draft_id == draft.draft_id
        assert token.ordered_video_ids == draft.ordered_video_ids
        assert token.consumed is False

        # Verify elicitation recorder captured the message with all required elements
        assert harness.elicitation.call_count == 1
        message = harness.elicitation.messages[0]
        assert "Alice Researcher (UC_MY_CHANNEL)" in message
        assert draft.title in message
        assert "private" in message
        assert "vid_qc_01" not in message  # Objective metadata displays title/channel
        assert "Quantum Lecture Part 1" in message
        assert "Physics Institute" in message

        # Token can be consumed cleanly
        consumed = token_store.consume(token, draft=draft, channel_id="UC_MY_CHANNEL")
        assert consumed.consumed is True


@pytest.mark.anyio
async def test_ST_FR5_CONFIRM_elicitation_decline_raises_confirmation_declined(
    system_harness_factory: Callable[..., Any],
) -> None:
    current = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    draft_store = DraftStore(DraftConfig(ttl_seconds=600), clock=lambda: current)
    token_store = ConfirmationTokenStore(clock=lambda: current)
    draft = _build_test_draft(draft_store)

    async with system_harness_factory(
        transport="memory",
        enable_elicitation=True,
        elicitation_action="decline",
    ) as harness:
        with pytest.raises(ToolError) as exc_info:
            await request_trusted_confirmation(
                draft,
                "UC_MY_CHANNEL",
                token_store,
                session=harness.session,
            )

        err = exc_info.value
        assert err.code is ErrorCode.CONFIRMATION_DECLINED
        assert err.details["draft_id"] == draft.draft_id

        # Verify token was minted with decline decision and cannot be consumed
        stored_token = token_store.get_for_draft(draft.draft_id)
        assert stored_token is not None
        assert stored_token.decision is ConfirmationDecision.DECLINE


@pytest.mark.anyio
async def test_ST_FR5_CONFIRM_elicitation_cancel_raises_confirmation_declined(
    system_harness_factory: Callable[..., Any],
) -> None:
    current = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    draft_store = DraftStore(DraftConfig(ttl_seconds=600), clock=lambda: current)
    token_store = ConfirmationTokenStore(clock=lambda: current)
    draft = _build_test_draft(draft_store)

    async with system_harness_factory(
        transport="memory",
        enable_elicitation=True,
        elicitation_action="cancel",
    ) as harness:
        with pytest.raises(ToolError) as exc_info:
            await request_trusted_confirmation(
                draft,
                "UC_MY_CHANNEL",
                token_store,
                session=harness.session,
            )

        err = exc_info.value
        assert err.code is ErrorCode.CONFIRMATION_DECLINED
        assert err.details["draft_id"] == draft.draft_id


@pytest.mark.anyio
async def test_ST_FR5_CONFIRM_local_page_accept_and_csrf_flow() -> None:
    current = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    draft_store = DraftStore(DraftConfig(ttl_seconds=600), clock=lambda: current)
    token_store = ConfirmationTokenStore(clock=lambda: current)
    draft = _build_test_draft(draft_store)

    def _simulate_browser_accept(url: str) -> None:
        def _run() -> None:
            import time

            time.sleep(0.05)
            # 1. GET page and parse csrf_token
            req = urllib.request.Request(url, headers={"User-Agent": "TestBrowser/1.0"})
            with urllib.request.urlopen(req) as response:
                assert response.status == 200
                csp = response.headers.get("Content-Security-Policy", "")
                assert "default-src 'none'" in csp
                assert "form-action 'self'" in csp
                body = response.read().decode("utf-8")
                assert draft.title in body
                assert "UC_USER_LOCAL" in body

                match = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
                assert match is not None
                csrf_token = match.group(1)

            # 2. POST accept
            post_data = urllib.parse.urlencode(
                {
                    "csrf_token": csrf_token,
                    "action": "accept",
                }
            ).encode("utf-8")
            post_req = urllib.request.Request(
                url,
                data=post_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(post_req) as post_resp:
                assert post_resp.status == 200
                post_body = post_resp.read().decode("utf-8")
                assert "Approved" in post_body

        import threading

        threading.Thread(target=_run, daemon=True).start()

    token = await serve_local_confirmation_page(
        draft,
        "UC_USER_LOCAL",
        token_store,
        browser_opener=_simulate_browser_accept,
        timeout_seconds=5.0,
    )

    assert isinstance(token, ConfirmationToken)
    assert token.is_accepted is True
    assert token.channel_id == "UC_USER_LOCAL"
    assert token.draft_id == draft.draft_id

    # Verify consumption
    consumed = token_store.consume(token, draft=draft, channel_id="UC_USER_LOCAL")
    assert consumed.consumed is True


@pytest.mark.anyio
async def test_ST_FR5_CONFIRM_local_page_decline() -> None:
    current = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    draft_store = DraftStore(DraftConfig(ttl_seconds=600), clock=lambda: current)
    token_store = ConfirmationTokenStore(clock=lambda: current)
    draft = _build_test_draft(draft_store)

    def _simulate_browser_decline(url: str) -> None:
        def _run() -> None:
            import time

            time.sleep(0.05)
            with urllib.request.urlopen(url) as response:
                body = response.read().decode("utf-8")
                match = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
                assert match is not None
                csrf_token = match.group(1)

            post_data = urllib.parse.urlencode(
                {
                    "csrf_token": csrf_token,
                    "action": "decline",
                }
            ).encode("utf-8")
            post_req = urllib.request.Request(
                url,
                data=post_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(post_req) as post_resp:
                assert post_resp.status == 200

        import threading

        threading.Thread(target=_run, daemon=True).start()

    with pytest.raises(ToolError) as exc_info:
        await serve_local_confirmation_page(
            draft,
            "UC_USER_LOCAL",
            token_store,
            browser_opener=_simulate_browser_decline,
            timeout_seconds=5.0,
        )

    err = exc_info.value
    assert err.code is ErrorCode.CONFIRMATION_DECLINED
    assert err.details["decision"] == "decline"


@pytest.mark.anyio
async def test_ST_FR5_CONFIRM_fallback_to_local_page_when_no_elicitation(
    system_harness_factory: Callable[..., Any],
) -> None:
    current = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    draft_store = DraftStore(DraftConfig(ttl_seconds=600), clock=lambda: current)
    token_store = ConfirmationTokenStore(clock=lambda: current)
    draft = _build_test_draft(draft_store)

    async with system_harness_factory(
        transport="memory",
        enable_elicitation=False,
    ) as harness:
        assert has_elicitation_capability(harness.session) is False

        def _client_accept(url: str) -> None:
            def _run() -> None:
                import time

                time.sleep(0.05)
                with urllib.request.urlopen(url) as resp:
                    body = resp.read().decode("utf-8")
                    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
                    assert match is not None
                    csrf_token = match.group(1)

                post_data = urllib.parse.urlencode(
                    {
                        "csrf_token": csrf_token,
                        "action": "accept",
                    }
                ).encode("utf-8")
                post_req = urllib.request.Request(
                    url,
                    data=post_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    method="POST",
                )
                with urllib.request.urlopen(post_req) as post_resp:
                    assert post_resp.status == 200

            import threading

            threading.Thread(target=_run, daemon=True).start()

        token = await request_trusted_confirmation(
            draft,
            "UC_FALLBACK_USER",
            token_store,
            session=harness.session,
            enable_loopback=True,
            browser_opener=_client_accept,
            timeout_seconds=5.0,
        )

        assert isinstance(token, ConfirmationToken)
        assert token.is_accepted is True
        assert token.channel_id == "UC_FALLBACK_USER"
        assert harness.elicitation.call_count == 0
