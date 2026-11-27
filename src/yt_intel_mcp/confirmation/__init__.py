"""Confirmation subsystem for human in the loop trusted authorization.

Requirements: FR-5.4, INV-13, INV-14, INV-22.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from yt_intel_mcp.confirmation.elicit import (
    PlaylistConfirmationForm,
    has_elicitation_capability,
    request_confirmation_via_elicitation,
)
from yt_intel_mcp.confirmation.local_page import (
    DEFAULT_LOOPBACK_HOST,
    LocalConfirmationPageServer,
    serve_local_confirmation_page,
)
from yt_intel_mcp.confirmation.summary import (
    format_confirmation_summary_html,
    format_confirmation_summary_text,
)
from yt_intel_mcp.confirmation.tokens import (
    CONFIRMATION_TOKEN_ID_RE,
    ConfirmationDecision,
    ConfirmationToken,
    ConfirmationTokenStore,
)
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.playlist.drafts import PlaylistDraft

__all__ = [
    "CONFIRMATION_TOKEN_ID_RE",
    "DEFAULT_LOOPBACK_HOST",
    "ConfirmationDecision",
    "ConfirmationToken",
    "ConfirmationTokenStore",
    "LocalConfirmationPageServer",
    "PlaylistConfirmationForm",
    "format_confirmation_summary_html",
    "format_confirmation_summary_text",
    "has_elicitation_capability",
    "request_confirmation_via_elicitation",
    "request_trusted_confirmation",
    "serve_local_confirmation_page",
]


async def request_trusted_confirmation(
    draft: PlaylistDraft,
    channel_id: str,
    token_store: ConfirmationTokenStore,
    *,
    context: Any | None = None,
    session: Any | None = None,
    enable_loopback: bool = True,
    browser_opener: Callable[[str], None] | None = None,
    timeout_seconds: float = 120.0,
    account_name: str | None = None,
) -> ConfirmationToken:
    """Obtain out of band trusted confirmation via elicitation or loopback (FR-5.4, INV-13).

    If the client declares the elicitation capability, Channel A (MCP dialog) is selected.
    If elicitation is not available, Channel B (127.0.0.1 loopback page) is attempted.
    If neither channel is available, CONFIRMATION_UNAVAILABLE is raised with zero writes.
    """
    target_session = session
    if target_session is None and context is not None:
        target_session = getattr(context, "session", None)
        if target_session is None and hasattr(context, "request_context"):
            target_session = getattr(context.request_context, "session", None)

    if has_elicitation_capability(target_session):
        return await request_confirmation_via_elicitation(
            draft,
            channel_id,
            token_store,
            context=context,
            session=target_session,
            account_name=account_name,
        )

    if enable_loopback:
        return await serve_local_confirmation_page(
            draft,
            channel_id,
            token_store,
            browser_opener=browser_opener,
            timeout_seconds=timeout_seconds,
            account_name=account_name,
        )

    raise ToolError(
        ErrorCode.CONFIRMATION_UNAVAILABLE,
        (
            "No trusted confirmation channel is available. MCP client does not "
            "advertise elicitation capability and local loopback confirmation is disabled."
        ),
        details={"draft_id": draft.draft_id},
    )
