"""Read-only analyze_engagement tool and youtube://user/context resource (TS-14, FR-4)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from yt_intel_mcp.analysis.engagement import (
    VALID_TIMEFRAMES,
    Timeframe,
    analyze_engagement_events,
)
from yt_intel_mcp.analysis.events import events_from_liked_videos, normalize_user_events
from yt_intel_mcp.cache import CachedYouTubeProvider
from yt_intel_mcp.config import EngagementConfig
from yt_intel_mcp.errors import ErrorCode, ToolError, success_response
from yt_intel_mcp.models import CostEstimate, QuotaUsed, UserEvent
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.schemas import load_schema
from yt_intel_mcp.store import SQLiteStore

__all__ = [
    "ANALYZE_ENGAGEMENT_DESCRIPTION",
    "USER_CONTEXT_RESOURCE_URI",
    "AnalyzeEngagementRequest",
    "estimate_engagement_cost",
    "execute_analyze_engagement",
    "read_user_context_resource",
    "register_analyze_engagement",
    "validate_analyze_engagement_arguments",
]

USER_CONTEXT_RESOURCE_URI = "youtube://user/context"
ANALYZE_ENGAGEMENT_DESCRIPTION = (
    "Compute aggregate topic shares, duration buckets (<4m, 4-20m, >20m), monthly activity "
    "trends, and period comparisons from explicit YouTube library actions (FR-4.1..4.3, NFR-7). "
    "Returns aggregates only with timestamp coverage counts and a watch-history disclaimer. "
    "Side effects: none (read only). Typical cost: <= 9 quota units, 0 search calls."
)

_ALLOWED_FIELDS: frozenset[str] = frozenset(load_schema("analyze_engagement")["properties"])
_MAX_PLAYLISTS = 5


@dataclass(frozen=True, slots=True)
class AnalyzeEngagementRequest:
    """Validated input arguments for analyze_engagement."""

    timeframe: Timeframe
    compare_with_previous_period: bool


def validate_analyze_engagement_arguments(arguments: Mapping[str, Any]) -> AnalyzeEngagementRequest:
    """Strictly validate analyze_engagement arguments pre-quota (NFR-5)."""
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
                f"Unexpected parameter {raw_key!r} is not allowed by analyze_engagement schema.",
                details={"field": str(raw_key)},
            )

    raw_tf = arguments.get("timeframe", "90d")
    if not isinstance(raw_tf, str) or raw_tf not in VALID_TIMEFRAMES:
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            f"timeframe must be one of {', '.join(VALID_TIMEFRAMES)}.",
            details={"field": "timeframe"},
        )

    raw_cmp = arguments.get("compare_with_previous_period", True)
    if not isinstance(raw_cmp, bool):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "compare_with_previous_period must be a boolean.",
            details={"field": "compare_with_previous_period"},
        )

    return AnalyzeEngagementRequest(
        timeframe=cast(Timeframe, raw_tf),
        compare_with_previous_period=raw_cmp,
    )


def estimate_engagement_cost(quota_guard: QuotaGuard) -> CostEstimate:
    """Estimate bounded read cost for analyze_engagement (0 search calls)."""
    list_unit = quota_guard.estimate("videos.list", count=1).units
    # subscriptions(1) + playlists(1) + <=5 playlistItems(5) + liked(1) + categories(1) = 9u
    return CostEstimate(units=9 * list_unit, search_calls=0, operation="analyze_engagement")


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


async def execute_analyze_engagement(
    arguments: Mapping[str, Any],
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    store: SQLiteStore | None = None,
    engagement_config: EngagementConfig | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Validate input, preflight <= 9u, collect explicit signals, and return aggregates."""
    req = validate_analyze_engagement_arguments(arguments)
    workflow_cost = estimate_engagement_cost(quota_guard)
    quota_guard.preflight(workflow_cost)

    status_before = quota_guard.status()
    self_charges = _provider_self_charges(provider)
    reference_now = (now_utc or datetime.now(UTC)).astimezone(UTC)

    collected_events: list[UserEvent] = []

    subs = await _run_counted_call(
        "subscriptions.list",
        quota_guard,
        self_charges=self_charges,
        status_before_units=status_before.units_used,
        status_before_searches=status_before.search_calls_used,
        coro=provider.list_subscriptions_mine(max_results=50),
    )
    collected_events.extend(normalize_user_events(subs, store=store, now_utc=reference_now))

    playlists = await _run_counted_call(
        "playlists.list",
        quota_guard,
        self_charges=self_charges,
        status_before_units=status_before.units_used,
        status_before_searches=status_before.search_calls_used,
        coro=provider.list_playlists_mine(max_results=50),
    )
    for playlist in playlists[:_MAX_PLAYLISTS]:
        items = await _run_counted_call(
            "playlistItems.list",
            quota_guard,
            self_charges=self_charges,
            status_before_units=status_before.units_used,
            status_before_searches=status_before.search_calls_used,
            coro=provider.list_playlist_items(playlist.playlist_id, max_results=50),
        )
        collected_events.extend(normalize_user_events(items, store=store, now_utc=reference_now))

    liked = await _run_counted_call(
        "videos.list",
        quota_guard,
        self_charges=self_charges,
        status_before_units=status_before.units_used,
        status_before_searches=status_before.search_calls_used,
        coro=provider.list_liked_videos_rated(max_results=50),
    )
    collected_events.extend(events_from_liked_videos(liked, store=store, now_utc=reference_now))

    actual_used = _compute_delta_quota(
        units_before=status_before.units_used,
        searches_before=status_before.search_calls_used,
        guard=quota_guard,
    )
    if not collected_events:
        raise ToolError(
            ErrorCode.INSUFFICIENT_USER_SIGNAL,
            "No explicit YouTube library signals (likes, playlists, or subscriptions) were found.",
            details={"reason": "empty_user_signals"},
            quota_used=actual_used,
        )

    categories = await _run_counted_call(
        "videoCategories.list",
        quota_guard,
        self_charges=self_charges,
        status_before_units=status_before.units_used,
        status_before_searches=status_before.search_calls_used,
        coro=provider.get_video_categories(region_code="US"),
    )
    actual_used = _compute_delta_quota(
        units_before=status_before.units_used,
        searches_before=status_before.search_calls_used,
        guard=quota_guard,
    )

    analysis = analyze_engagement_events(
        collected_events,
        timeframe=req.timeframe,
        compare_with_previous_period=req.compare_with_previous_period,
        category_names=categories,
        now_utc=reference_now,
        config=engagement_config,
    )
    data = analysis.to_dict()
    summary = (
        f"Engagement summary ({req.timeframe}): {analysis.total_signals} explicit signals, "
        f"{analysis.timestamp_coverage.dated} dated, cadence {analysis.cadence_status}."
    )
    return success_response(summary, data, quota_used=actual_used)


async def read_user_context_resource(
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    store: SQLiteStore | None = None,
    engagement_config: EngagementConfig | None = None,
) -> str:
    """Serialize aggregate-only youtube://user/context JSON document (NFR-7)."""
    payload = await execute_analyze_engagement(
        {"timeframe": "90d", "compare_with_previous_period": True},
        provider=provider,
        quota_guard=quota_guard,
        store=store,
        engagement_config=engagement_config,
    )
    return json.dumps(payload["data"], indent=2)


def register_analyze_engagement(
    server: MCPServer,
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    store: SQLiteStore | None = None,
    engagement_config: EngagementConfig | None = None,
) -> None:
    """Register the read-only analyze_engagement tool and youtube://user/context resource."""

    @server.tool(
        name="analyze_engagement",
        title="Analyze Explicit YouTube Engagement",
        description=ANALYZE_ENGAGEMENT_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Analyze Explicit YouTube Engagement",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    async def analyze_engagement(
        ctx: Context[Any, Any],
        timeframe: object = "90d",
        compare_with_previous_period: object = True,
    ) -> CallToolResult:
        arguments: dict[str, Any] = {
            "timeframe": timeframe,
            "compare_with_previous_period": compare_with_previous_period,
        }
        raw_params = getattr(ctx, "input_params", None) or getattr(ctx, "_input_params", None)
        raw_args = getattr(raw_params, "arguments", None)
        if isinstance(raw_args, Mapping):
            arguments = dict(raw_args)

        try:
            payload = await execute_analyze_engagement(
                arguments,
                provider=provider,
                quota_guard=quota_guard,
                store=store,
                engagement_config=engagement_config,
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

    registered_tool = server._tool_manager.get_tool("analyze_engagement")
    if registered_tool is not None:  # pragma: no branch
        registered_tool.parameters = load_schema("analyze_engagement")

    @server.resource(
        USER_CONTEXT_RESOURCE_URI,
        name="youtube-user-context",
        title="Aggregated User YouTube Context",
        description=(
            "Privacy-preserving aggregate summary of explicit YouTube library signals "
            "(no raw personal IDs or watch history)."
        ),
        mime_type="application/json",
    )
    async def user_context_resource() -> str:
        return await read_user_context_resource(
            provider=provider,
            quota_guard=quota_guard,
            store=store,
            engagement_config=engagement_config,
        )
