"""Channel A: MCP elicitation dialog confirmation (FR-5.4, INV-13, INV-22)."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from yt_intel_mcp.confirmation.summary import format_confirmation_summary_text
from yt_intel_mcp.confirmation.tokens import (
    ConfirmationDecision,
    ConfirmationToken,
    ConfirmationTokenStore,
)
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.playlist.drafts import PlaylistDraft

logger = logging.getLogger(__name__)

__all__ = [
    "PlaylistConfirmationForm",
    "has_elicitation_capability",
    "request_confirmation_via_elicitation",
]


class PlaylistConfirmationForm(BaseModel):
    """Schema for boolean playlist creation confirmation dialog."""

    confirm: bool = Field(
        default=True,
        description="Set to true to confirm creating this curated playlist in your YouTube library",
    )


def has_elicitation_capability(session_or_context: Any) -> bool:
    """Return True if the active client session declared the elicitation capability."""
    if session_or_context is None:
        return False

    if hasattr(session_or_context, "elicitation_enabled"):
        return bool(session_or_context.elicitation_enabled)

    session = getattr(session_or_context, "session", session_or_context)
    if hasattr(session, "request_context"):
        session = getattr(session.request_context, "session", session)

    caps = getattr(session, "client_capabilities", None)
    if caps is not None:
        return getattr(caps, "elicitation", None) is not None

    try:
        from mcp.client.session import _default_elicitation_callback

        cb = getattr(session, "_elicitation_callback", None)
        if cb is not None:
            return cb is not _default_elicitation_callback
    except ImportError:
        pass

    return False


async def request_confirmation_via_elicitation(
    draft: PlaylistDraft,
    channel_id: str,
    token_store: ConfirmationTokenStore,
    *,
    context: Any | None = None,
    session: Any | None = None,
    account_name: str | None = None,
) -> ConfirmationToken:
    """Request human in the loop confirmation through an MCP elicitation dialog (FR-5.4)."""
    target_session = session
    if target_session is None and context is not None:
        target_session = getattr(context, "session", None)
        if target_session is None and hasattr(context, "request_context"):
            target_session = getattr(context.request_context, "session", None)

    if target_session is None or not has_elicitation_capability(target_session):
        raise ToolError(
            ErrorCode.CONFIRMATION_UNAVAILABLE,
            "MCP client does not advertise the elicitation capability.",
            details={"draft_id": draft.draft_id, "channel": "elicitation"},
        )

    summary_text = format_confirmation_summary_text(draft, channel_id, account_name=account_name)

    try:
        if context is not None and hasattr(context, "elicit"):
            result = await context.elicit(
                message=summary_text,
                schema=PlaylistConfirmationForm,
            )
            action = getattr(result, "action", "decline")
        elif hasattr(target_session, "elicit_form"):
            result = await target_session.elicit_form(
                message=summary_text,
                requested_schema=PlaylistConfirmationForm.model_json_schema(),
            )
            action = getattr(result, "action", "decline")
        elif hasattr(target_session, "_elicitation_callback"):
            import inspect

            import mcp.types as types
            from mcp.client.session import ClientRequestContext

            req_params = types.ElicitRequestFormParams(
                message=summary_text,
                requested_schema=PlaylistConfirmationForm.model_json_schema(),
            )
            req_ctx = ClientRequestContext(session=target_session, request_id="sim_confirm")
            cb = target_session._elicitation_callback
            cb_res = cb(req_ctx, req_params)
            if inspect.isawaitable(cb_res):
                cb_res = await cb_res
            action = getattr(cb_res, "action", "decline")
        else:
            raise ToolError(
                ErrorCode.CONFIRMATION_UNAVAILABLE,
                "No valid elicitation dispatcher found on active session.",
                details={"draft_id": draft.draft_id},
            )
    except Exception as exc:
        logger.warning("MCP elicitation call failed: %s", exc)
        token_store.mint_for_draft(draft, channel_id, decision=ConfirmationDecision.DECLINE)
        raise ToolError(
            ErrorCode.CONFIRMATION_DECLINED,
            f"Playlist creation confirmation failed or was rejected: {exc}",
            details={"draft_id": draft.draft_id, "error": str(exc)},
        ) from exc

    if action == "accept":
        return token_store.mint_for_draft(draft, channel_id, decision=ConfirmationDecision.ACCEPT)

    token_store.mint_for_draft(draft, channel_id, decision=ConfirmationDecision.DECLINE)
    raise ToolError(
        ErrorCode.CONFIRMATION_DECLINED,
        f"Playlist creation confirmation for draft {draft.draft_id!r} was {action}ed by user.",
        details={"draft_id": draft.draft_id, "action": action},
    )
