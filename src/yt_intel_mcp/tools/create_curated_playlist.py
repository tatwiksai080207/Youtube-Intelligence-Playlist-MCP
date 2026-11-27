"""Confirmed create_curated_playlist MCP tool handler (MF-14, FR-5.4, FR-5.5, FR-6.2, FR-7.1)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from typing import Any

import mcp.types as types
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from yt_intel_mcp.auth.oauth import check_channel_presence, ensure_write_scope
from yt_intel_mcp.auth.token_store import TokenStore
from yt_intel_mcp.cache import CachedYouTubeProvider
from yt_intel_mcp.confirmation import (
    ConfirmationTokenStore,
    request_trusted_confirmation,
)
from yt_intel_mcp.errors import ErrorCode, ToolError, success_response
from yt_intel_mcp.models import CostEstimate
from yt_intel_mcp.playlist.drafts import DRAFT_ID_RE, DraftStore, PlaylistDraft
from yt_intel_mcp.playlist.writer import (
    check_draft_staleness,
    write_curated_playlist,
)
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.schemas import load_schema

__all__ = [
    "CREATE_PLAYLIST_DESCRIPTION",
    "execute_create_curated_playlist",
    "register_create_curated_playlist",
    "validate_create_curated_playlist_arguments",
]

logger = logging.getLogger(__name__)

CREATE_PLAYLIST_DESCRIPTION = (
    "Create a new YouTube playlist from an active, immutable draft after trusted human in the "
    "loop confirmation (FR-5.4, FR-5.5, FR-6.2, FR-7.1, write side effect). Requires an unexpired "
    "draft_id and user confirmation via MCP elicitation dialog or local loopback page. Preflights "
    "exact write quota (50 units + 50 units per video) and inserts videos with zero retries, "
    "returning a COMPLETE or PARTIAL report."
)

_ALLOWED_FIELDS: frozenset[str] = frozenset(load_schema("create_curated_playlist")["properties"])
_REQUIRED_FIELDS: tuple[str, ...] = tuple(load_schema("create_curated_playlist")["required"])


def validate_create_curated_playlist_arguments(arguments: Mapping[str, Any]) -> str:
    """Strictly validate create_curated_playlist arguments before spending quota (INV-13, NFR-5)."""
    if not isinstance(arguments, Mapping):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "Tool arguments must be a JSON object.",
            details={"field": "arguments"},
        )

    for raw_key in arguments:
        if raw_key not in _ALLOWED_FIELDS:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                (
                    f"Unexpected parameter {raw_key!r} is not allowed by "
                    "create_curated_playlist schema."
                ),
                details={"field": str(raw_key)},
            )

    for req_key in _REQUIRED_FIELDS:
        if req_key not in arguments or arguments[req_key] is None:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Missing required parameter {req_key!r}.",
                details={"field": req_key},
            )

    raw_draft_id = arguments["draft_id"]
    if not isinstance(raw_draft_id, str):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "Parameter 'draft_id' must be a string.",
            details={"field": "draft_id"},
        )

    clean_id = raw_draft_id.strip()
    if DRAFT_ID_RE.fullmatch(clean_id) is None:
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            f"Parameter 'draft_id' ({raw_draft_id!r}) does not match expected format.",
            details={"field": "draft_id"},
        )

    return clean_id


def _provider_self_charges(provider: YouTubeProvider) -> bool:
    return isinstance(provider, CachedYouTubeProvider) or (
        getattr(provider, "quota_guard", None) is not None
        or getattr(provider, "_quota_guard", None) is not None
    )


async def execute_create_curated_playlist(
    arguments: Mapping[str, Any],
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    draft_store: DraftStore,
    confirmation_store: ConfirmationTokenStore | None = None,
    token_store: TokenStore | None = None,
    context: Any | None = None,
    session: Any | None = None,
    enable_loopback: bool = True,
    browser_opener: Callable[[str], None] | None = None,
    timeout_seconds: float = 120.0,
    channel_id_override: str | None = None,
    account_name: str | None = None,
) -> dict[str, Any]:
    """Execute the frozen ADR-0004 9-step playlist creation sequence."""
    # Step 1: Validate draft_id schema, look up immutable Draft, verify unexpired
    draft_id = validate_create_curated_playlist_arguments(arguments)
    draft: PlaylistDraft = draft_store.get(draft_id)

    # Step 2: Read current local auth session identity
    channel_id: str
    resolved_account_name = account_name
    if channel_id_override is not None:
        channel_id = channel_id_override
    elif token_store is not None:
        loaded = token_store.load_bundle()
        if loaded is None:
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "Authentication required before creating playlist. No active OAuth token found.",
                details={"authenticated": False},
            )
        bundle, _ = loaded
        if bundle.channel_id:
            channel_id = bundle.channel_id
        else:
            ch_meta = await check_channel_presence(provider, token_store)
            channel_id = ch_meta.channel_id
            if resolved_account_name is None:
                resolved_account_name = ch_meta.title
    else:
        my_ch = getattr(provider, "_my_channel", None)
        if my_ch is not None and getattr(my_ch, "channel_id", None):
            channel_id = my_ch.channel_id
            if resolved_account_name is None:
                resolved_account_name = getattr(my_ch, "title", None)
        else:
            channel_id = "UC_DEFAULT_CHANNEL"

    # Step 3 & Step 4: Obtain trusted confirmation and consume single-use bound token
    c_store = confirmation_store if confirmation_store is not None else ConfirmationTokenStore()
    token = await request_trusted_confirmation(
        draft,
        channel_id,
        c_store,
        context=context,
        session=session,
        enable_loopback=enable_loopback,
        browser_opener=browser_opener,
        timeout_seconds=timeout_seconds,
        account_name=resolved_account_name,
    )
    c_store.consume(token, draft=draft, channel_id=channel_id)

    # Step 5: Preflight combined workflow budget and execute fresh get_videos stale check
    num_videos = len(draft.videos)
    recheck_units = (num_videos + 49) // 50
    exact_write_units = 50 + 50 * num_videos
    combined_units = recheck_units + exact_write_units

    combined_cost = CostEstimate(
        units=combined_units,
        search_calls=0,
        operation="playlist_creation_workflow",
    )
    quota_guard.preflight(combined_cost)

    stale_cost = CostEstimate(
        units=recheck_units,
        search_calls=0,
        operation="videos.list",
    )
    self_charges = _provider_self_charges(provider)
    try:
        if hasattr(provider, "get_videos_uncached"):
            fresh_videos = await provider.get_videos_uncached(draft.ordered_video_ids)
        else:
            fresh_videos = await provider.get_videos(draft.ordered_video_ids)
    except ToolError as exc:
        if not self_charges:
            quota_guard.charge(stale_cost)
            if exc.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM:
                quota_guard.mark_upstream_exhausted()
        raise

    if not self_charges:
        quota_guard.charge(stale_cost)

    check_draft_staleness(draft, fresh_videos)

    # Step 6: Ensure write scope youtube.force-ssl
    if token_store is not None:
        ensure_write_scope(token_store, interactive=False)

    # Step 7: Verify authenticated YouTube channel and assert channel_id matches token
    channel_meta = await check_channel_presence(provider, token_store)
    if channel_meta.channel_id != token.channel_id:
        raise ToolError(
            ErrorCode.CONFIRMATION_MISMATCH,
            (
                f"Authenticated channel {channel_meta.channel_id!r} does not match "
                f"confirmed channel {token.channel_id!r}."
            ),
            details={
                "expected_channel_id": token.channel_id,
                "actual_channel_id": channel_meta.channel_id,
            },
        )

    # Step 8: Run exact write preflight for 50 + 50 * len(videos) units
    write_cost = CostEstimate(
        units=exact_write_units,
        search_calls=0,
        operation="playlist_write_execution",
    )
    quota_guard.preflight(write_cost)

    # Step 9: Dispatch insert_playlist and ordered insert_playlist_item with 0 retries
    outcome = await write_curated_playlist(draft, provider)
    return success_response(summary=outcome.summary, data=outcome.to_dict())


def register_create_curated_playlist(
    server: MCPServer,
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    draft_store: DraftStore,
    confirmation_store: ConfirmationTokenStore | None = None,
    token_store: TokenStore | None = None,
    enable_loopback: bool = True,
    browser_opener: Callable[[str], None] | None = None,
    timeout_seconds: float = 120.0,
    channel_id_override: str | None = None,
) -> None:
    """Register create_curated_playlist tool on an MCP server instance."""

    @server.tool(
        name="create_curated_playlist",
        title="Create Curated YouTube Playlist",
        description=CREATE_PLAYLIST_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Create Curated YouTube Playlist",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    async def create_curated_playlist(
        ctx: Context[Any, Any],
        draft_id: object = None,
    ) -> types.CallToolResult:
        arguments: dict[str, Any] = {"draft_id": draft_id}
        raw_params = getattr(ctx, "input_params", None) or getattr(ctx, "_input_params", None)
        raw_args = getattr(raw_params, "arguments", None)
        if isinstance(raw_args, Mapping):
            arguments = dict(raw_args)

        try:
            payload = await execute_create_curated_playlist(
                arguments,
                provider=provider,
                quota_guard=quota_guard,
                draft_store=draft_store,
                confirmation_store=confirmation_store,
                token_store=token_store,
                context=ctx,
                session=getattr(ctx, "session", None),
                enable_loopback=enable_loopback,
                browser_opener=browser_opener,
                timeout_seconds=timeout_seconds,
                channel_id_override=channel_id_override,
            )
        except ToolError as exc:
            err_payload = exc.to_envelope()
            return types.CallToolResult(
                is_error=True,
                content=[types.TextContent(type="text", text=json.dumps(err_payload))],
                structured_content=err_payload,
            )

        return types.CallToolResult(
            is_error=False,
            content=[types.TextContent(type="text", text=json.dumps(payload))],
            structured_content=payload,
        )

    registered_tool = server._tool_manager.get_tool("create_curated_playlist")
    if registered_tool is not None:
        registered_tool.parameters = load_schema("create_curated_playlist")
