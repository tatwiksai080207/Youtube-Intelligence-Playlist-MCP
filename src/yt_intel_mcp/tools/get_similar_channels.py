"""Read-only get_similar_channels MCP tool handler (TS-11, FR-2.1, FR-2.2, INV-01)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from yt_intel_mcp.cache import CachedYouTubeProvider
from yt_intel_mcp.config import SimilarityConfig
from yt_intel_mcp.errors import ErrorCode, ToolError, success_response
from yt_intel_mcp.models import ChannelMeta, CostEstimate, QuotaUsed, UserEvent
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.sanitize import DEFAULT_MAX_TITLE_LENGTH, sanitize_single_line
from yt_intel_mcp.schemas import load_schema
from yt_intel_mcp.similarity.channels import (
    ChannelProfile,
    build_channel_profile,
    rank_similar_channels,
)
from yt_intel_mcp.similarity.text import build_search_query
from yt_intel_mcp.validation import ChannelReference, parse_channel_reference

__all__ = [
    "GET_SIMILAR_CHANNELS_DESCRIPTION",
    "SimilarChannelsRequest",
    "estimate_similar_channels_cost",
    "execute_get_similar_channels",
    "register_get_similar_channels",
    "validate_get_similar_channels_arguments",
]

GET_SIMILAR_CHANNELS_DESCRIPTION = (
    "Discover YouTube channels similar to a seed channel ID, @handle, or URL using objective "
    "metadata only (topics, keywords, and recent upload titles/tags) without subscriber counts "
    "(FR-2.1, FR-2.2, INV-01). Side effects: none (read only). "
    "Typical cost: <= 1 search call + <= 32 quota units."
)

_ALLOWED_FIELDS: frozenset[str] = frozenset(load_schema("get_similar_channels")["properties"])
_REQUIRED_FIELDS: tuple[str, ...] = tuple(load_schema("get_similar_channels")["required"])
_MAX_CANDIDATE_CHANNELS = 25
_MAX_UPLOAD_FETCHES = 28


@dataclass(frozen=True, slots=True)
class SimilarChannelsRequest:
    """Validated input arguments for get_similar_channels."""

    reference: ChannelReference
    max_results: int


def validate_get_similar_channels_arguments(
    arguments: Mapping[str, Any],
) -> SimilarChannelsRequest:
    """Strictly validate get_similar_channels arguments pre-quota (INV-02, NFR-5)."""
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
                f"Unexpected parameter {raw_key!r} is not allowed by get_similar_channels schema.",
                details={"field": str(raw_key)},
            )

    for req_key in _REQUIRED_FIELDS:
        if req_key not in arguments or arguments[req_key] is None:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Missing required parameter {req_key!r}.",
                details={"field": req_key},
            )

    reference = parse_channel_reference(arguments["channel"])

    raw_max = arguments.get("max_results", 10)
    if isinstance(raw_max, bool) or not isinstance(raw_max, int) or not (1 <= raw_max <= 50):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "max_results must be an integer between 1 and 50.",
            details={"field": "max_results"},
        )

    return SimilarChannelsRequest(reference=reference, max_results=raw_max)


def estimate_similar_channels_cost(quota_guard: QuotaGuard) -> CostEstimate:
    """Estimate bounded worst-case read cost (<= 1 search + 32 units)."""
    list_unit = quota_guard.estimate("channels.list", count=1).units
    search_cost = quota_guard.estimate("search.list", count=1)
    return CostEstimate(
        units=min(32, 32 * list_unit) + search_cost.units,
        search_calls=search_cost.search_calls,
        operation="get_similar_channels",
    )


def _provider_self_charges(provider: YouTubeProvider) -> bool:
    return isinstance(provider, CachedYouTubeProvider) or (
        getattr(provider, "quota_guard", None) is not None
    )


def _compute_delta_quota(
    *,
    units_before: int,
    searches_before: int,
    guard: QuotaGuard,
) -> QuotaUsed:
    after = guard.status()
    return QuotaUsed(
        units=max(0, after.units_used - units_before),
        search_calls=max(0, after.search_calls_used - searches_before),
    )


async def _run_counted_call(
    op_name: str,
    quota_guard: QuotaGuard,
    *,
    self_charges: bool,
    status_before_units: int,
    status_before_searches: int,
    coro: Any,
) -> Any:
    cost = quota_guard.estimate(op_name, count=1)
    try:
        result = await coro
    except ToolError as exc:
        if not self_charges:
            quota_guard.charge(cost)
            if exc.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM:
                quota_guard.mark_upstream_exhausted()
        used = _compute_delta_quota(
            units_before=status_before_units,
            searches_before=status_before_searches,
            guard=quota_guard,
        )
        raise ToolError(exc.code, exc.message, details=exc.details, quota_used=used) from exc
    if not self_charges:
        quota_guard.charge(cost)
    return result


async def _fetch_recent_uploads(
    channel: ChannelMeta,
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    self_charges: bool,
    status_before_units: int,
    status_before_searches: int,
) -> list[UserEvent]:
    if not channel.uploads_playlist_id:
        return []
    return await _run_counted_call(
        "playlistItems.list",
        quota_guard,
        self_charges=self_charges,
        status_before_units=status_before_units,
        status_before_searches=status_before_searches,
        coro=provider.list_playlist_items(channel.uploads_playlist_id, max_results=10),
    )


async def execute_get_similar_channels(
    arguments: Mapping[str, Any],
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    similarity_config: SimilarityConfig | None = None,
) -> dict[str, Any]:
    """Validate channel ref, preflight <= 1s + 32u, resolve, and rank similar channels."""
    req = validate_get_similar_channels_arguments(arguments)
    workflow_cost = estimate_similar_channels_cost(quota_guard)
    quota_guard.preflight(workflow_cost)

    status_before = quota_guard.status()
    self_charges = _provider_self_charges(provider)

    # 1. Resolve seed channel by ID or @handle (1 u).
    seed_channel: ChannelMeta | None = None
    if req.reference.kind == "channel_id":
        resolved = await _run_counted_call(
            "channels.list",
            quota_guard,
            self_charges=self_charges,
            status_before_units=status_before.units_used,
            status_before_searches=status_before.search_calls_used,
            coro=provider.get_channels([req.reference.value]),
        )
        seed_channel = resolved[0] if resolved else None
    else:
        seed_channel = await _run_counted_call(
            "channels.list",
            quota_guard,
            self_charges=self_charges,
            status_before_units=status_before.units_used,
            status_before_searches=status_before.search_calls_used,
            coro=provider.get_channel_by_handle(req.reference.value),
        )

    if seed_channel is None:
        used_on_missing = _compute_delta_quota(
            units_before=status_before.units_used,
            searches_before=status_before.search_calls_used,
            guard=quota_guard,
        )
        # G-01 Option A: reuse INVALID_ARGUMENT when channel resolution finds no channel.
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            f"Channel {req.reference.value!r} was not found.",
            details={"channel": req.reference.value, "reason": "channel_not_found"},
            quota_used=used_on_missing,
        )

    # 2. Fetch seed recent uploads (<= 1 u) and build query.
    seed_uploads = await _fetch_recent_uploads(
        seed_channel,
        provider=provider,
        quota_guard=quota_guard,
        self_charges=self_charges,
        status_before_units=status_before.units_used,
        status_before_searches=status_before.search_calls_used,
    )
    seed_profile = build_channel_profile(seed_channel, seed_uploads)

    query = build_search_query(seed_channel.title, seed_channel.keywords, max_terms=5)
    if not query:
        query = sanitize_single_line(seed_channel.title, max_length=100) or seed_channel.channel_id

    # 3. Search candidate channels (1 s).
    hits = await _run_counted_call(
        "search.list",
        quota_guard,
        self_charges=self_charges,
        status_before_units=status_before.units_used,
        status_before_searches=status_before.search_calls_used,
        coro=provider.search_channels(query, max_results=_MAX_CANDIDATE_CHANNELS),
    )

    cand_ids: list[str] = []
    seen_ids: set[str] = {seed_channel.channel_id}
    for hit in hits:
        if hit.kind != "channel" or hit.item_id in seen_ids:
            continue
        seen_ids.add(hit.item_id)
        cand_ids.append(hit.item_id)
        if len(cand_ids) >= _MAX_CANDIDATE_CHANNELS:
            break

    # 4. Fetch candidate channel metadata (<= 1 u) and recent uploads (within <= 32 u).
    candidate_profiles: list[ChannelProfile] = []
    if cand_ids:
        cand_channels = await _run_counted_call(
            "channels.list",
            quota_guard,
            self_charges=self_charges,
            status_before_units=status_before.units_used,
            status_before_searches=status_before.search_calls_used,
            coro=provider.get_channels(cand_ids),
        )
        for ch in cand_channels[:_MAX_UPLOAD_FETCHES]:
            uploads = await _fetch_recent_uploads(
                ch,
                provider=provider,
                quota_guard=quota_guard,
                self_charges=self_charges,
                status_before_units=status_before.units_used,
                status_before_searches=status_before.search_calls_used,
            )
            candidate_profiles.append(build_channel_profile(ch, uploads))

    actual_used = _compute_delta_quota(
        units_before=status_before.units_used,
        searches_before=status_before.search_calls_used,
        guard=quota_guard,
    )

    ranking = rank_similar_channels(
        seed_profile,
        candidate_profiles,
        max_results=req.max_results,
        similarity_config=similarity_config,
    )
    clean_seed_title = sanitize_single_line(seed_channel.title, max_length=DEFAULT_MAX_TITLE_LENGTH)

    data: dict[str, Any] = {
        "seed_channel": {
            "channel_id": seed_channel.channel_id,
            "title": clean_seed_title,
            "custom_url": seed_channel.custom_url,
            "topic_categories": list(seed_channel.topic_categories),
            "keywords": list(seed_channel.keywords),
        },
        "query_used": query,
        "active_weights": {key: round(val, 6) for key, val in ranking.active_weights.items()},
        "results": [item.to_dict() for item in ranking.ranked_channels],
        "total_candidates_evaluated": ranking.total_candidates_evaluated,
        "metadata_only_notice": (
            "Channels ranked by objective metadata only (no subscriber or view counts)."
        ),
    }
    summary = (
        f"Found {len(ranking.ranked_channels)} similar channels for {clean_seed_title!r} "
        f"using objective metadata only ({ranking.total_candidates_evaluated} candidates)."
    )
    return success_response(summary, data, quota_used=actual_used)


def register_get_similar_channels(
    server: MCPServer,
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    similarity_config: SimilarityConfig | None = None,
) -> None:
    """Register the read-only get_similar_channels tool on an MCPServer."""

    @server.tool(
        name="get_similar_channels",
        title="Get Similar YouTube Channels",
        description=GET_SIMILAR_CHANNELS_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Get Similar YouTube Channels",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    async def get_similar_channels(
        ctx: Context[Any, Any],
        channel: object = None,
        max_results: object = 10,
    ) -> CallToolResult:
        arguments: dict[str, Any] = {"channel": channel, "max_results": max_results}
        raw_params = getattr(ctx, "input_params", None) or getattr(ctx, "_input_params", None)
        raw_args = getattr(raw_params, "arguments", None)
        if isinstance(raw_args, Mapping):
            arguments = dict(raw_args)

        try:
            payload = await execute_get_similar_channels(
                arguments,
                provider=provider,
                quota_guard=quota_guard,
                similarity_config=similarity_config,
            )
        except ToolError as exc:
            err_payload = exc.to_envelope()
            return CallToolResult(
                is_error=True,
                content=[TextContent(type="text", text=json.dumps(err_payload))],
                structured_content=err_payload,
            )

        return CallToolResult(
            is_error=False,
            content=[TextContent(type="text", text=json.dumps(payload))],
            structured_content=payload,
        )

    registered_tool = server._tool_manager.get_tool("get_similar_channels")
    if registered_tool is not None:  # pragma: no branch
        registered_tool.parameters = load_schema("get_similar_channels")
