"""Read-only get_recommendations MCP tool handler (TS-13, FR-3.3, INV-06)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import mcp.types as types
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from yt_intel_mcp.analysis.events import events_from_liked_videos, normalize_user_events
from yt_intel_mcp.analysis.profile import build_interest_profile
from yt_intel_mcp.analysis.recommend import score_recommendations
from yt_intel_mcp.cache import CachedYouTubeProvider
from yt_intel_mcp.config import ProfileConfig
from yt_intel_mcp.errors import ErrorCode, ToolError, success_response
from yt_intel_mcp.models import CostEstimate, EventSource, QuotaUsed, UserEvent, VideoMeta
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.schemas import load_schema
from yt_intel_mcp.store import SQLiteStore

__all__ = [
    "GET_RECOMMENDATIONS_DESCRIPTION",
    "RECOMMEND_MAX_PLAYLISTS",
    "RECOMMEND_MAX_SEARCH_CALLS",
    "RECOMMEND_MAX_UNIT_BUDGET",
    "RecommendationsRequest",
    "estimate_recommendations_cost",
    "execute_get_recommendations",
    "register_get_recommendations",
    "validate_get_recommendations_arguments",
]

GET_RECOMMENDATIONS_DESCRIPTION = (
    "Generate personalized YouTube video recommendations from explicit user library signals "
    "(likes, subscriptions, playlists) with 90-day half-life decay and zero watch-history "
    "or popularity signals (FR-3.1..3.3, INV-04..06). Excludes already liked or saved videos "
    "and attaches a human-readable reason per recommendation. Side effects: none (read only). "
    "Typical cost: <= 3 search calls + <= 25 quota units."
)

RECOMMEND_MAX_SEARCH_CALLS = 3
RECOMMEND_MAX_PLAYLISTS = 5
RECOMMEND_MAX_UNIT_BUDGET = 25

_ALLOWED_FIELDS: frozenset[str] = frozenset(load_schema("get_recommendations")["properties"])
_VALID_SOURCES: tuple[EventSource, ...] = (
    EventSource.LIKED_VIDEO,
    EventSource.SUBSCRIPTION,
    EventSource.PLAYLIST_ITEM,
)
_SOURCE_BY_VALUE: dict[str, EventSource] = {src.value: src for src in _VALID_SOURCES}


@dataclass(frozen=True, slots=True)
class RecommendationsRequest:
    """Validated input arguments for get_recommendations."""

    max_results: int
    sources: tuple[EventSource, ...]


def validate_get_recommendations_arguments(arguments: Mapping[str, Any]) -> RecommendationsRequest:
    """Strictly validate get_recommendations arguments pre-quota (NFR-5)."""
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
                f"Unexpected parameter {raw_key!r} is not allowed by get_recommendations schema.",
                details={"field": str(raw_key)},
            )

    raw_max = arguments.get("max_results", 10)
    if isinstance(raw_max, bool) or not isinstance(raw_max, int) or not (1 <= raw_max <= 50):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "max_results must be an integer between 1 and 50.",
            details={"field": "max_results"},
        )

    raw_sources = arguments.get("sources")
    if raw_sources is None:
        return RecommendationsRequest(max_results=raw_max, sources=_VALID_SOURCES)

    if isinstance(raw_sources, str) or not isinstance(raw_sources, Sequence):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "sources must be a non-empty array of EventSource values.",
            details={"field": "sources"},
        )
    if not (1 <= len(raw_sources) <= 3):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "sources must contain between 1 and 3 unique signal sources.",
            details={"field": "sources"},
        )

    parsed_sources: list[EventSource] = []
    for item in raw_sources:
        if not isinstance(item, str) or item not in _SOURCE_BY_VALUE:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Unsupported signal source {item!r}.",
                details={"field": "sources"},
            )
        src = _SOURCE_BY_VALUE[item]
        if src in parsed_sources:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Duplicate signal source {item!r} in sources.",
                details={"field": "sources"},
            )
        parsed_sources.append(src)

    return RecommendationsRequest(max_results=raw_max, sources=tuple(parsed_sources))


def estimate_recommendations_cost(
    request: RecommendationsRequest,
    quota_guard: QuotaGuard,
) -> CostEstimate:
    """Estimate bounded worst-case quota cost (<= 3 searches + <= 25 units, ADR-0007)."""
    list_unit = quota_guard.estimate("videos.list", count=1).units
    search_cost = quota_guard.estimate("search.list", count=RECOMMEND_MAX_SEARCH_CALLS)

    signal_calls = 0
    if EventSource.SUBSCRIPTION in request.sources:
        signal_calls += 1
    if EventSource.PLAYLIST_ITEM in request.sources:
        signal_calls += 1 + RECOMMEND_MAX_PLAYLISTS
    if EventSource.LIKED_VIDEO in request.sources:
        signal_calls += 1
    enrichment_calls = 1

    unit_budget = min(RECOMMEND_MAX_UNIT_BUDGET, (signal_calls + enrichment_calls) * list_unit)
    return CostEstimate(
        units=unit_budget + search_cost.units,
        search_calls=search_cost.search_calls,
        operation="get_recommendations",
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


async def execute_get_recommendations(
    arguments: Mapping[str, Any],
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    store: SQLiteStore | None = None,
    profile_config: ProfileConfig | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Validate input, preflight <= 3s + <= 25u, build profile, search, and rank."""
    req = validate_get_recommendations_arguments(arguments)
    workflow_cost = estimate_recommendations_cost(req, quota_guard)
    quota_guard.preflight(workflow_cost)

    status_before = quota_guard.status()
    self_charges = _provider_self_charges(provider)
    reference_now = (now_utc or datetime.now(UTC)).astimezone(UTC)

    collected_events: list[UserEvent] = []

    if EventSource.SUBSCRIPTION in req.sources:
        subs = await _run_counted_call(
            "subscriptions.list",
            quota_guard,
            self_charges=self_charges,
            status_before_units=status_before.units_used,
            status_before_searches=status_before.search_calls_used,
            coro=provider.list_subscriptions_mine(max_results=50),
        )
        collected_events.extend(normalize_user_events(subs, store=store, now_utc=reference_now))

    if EventSource.PLAYLIST_ITEM in req.sources:
        playlists = await _run_counted_call(
            "playlists.list",
            quota_guard,
            self_charges=self_charges,
            status_before_units=status_before.units_used,
            status_before_searches=status_before.search_calls_used,
            coro=provider.list_playlists_mine(max_results=50),
        )
        for playlist in playlists[:RECOMMEND_MAX_PLAYLISTS]:
            items = await _run_counted_call(
                "playlistItems.list",
                quota_guard,
                self_charges=self_charges,
                status_before_units=status_before.units_used,
                status_before_searches=status_before.search_calls_used,
                coro=provider.list_playlist_items(playlist.playlist_id, max_results=50),
            )
            collected_events.extend(normalize_user_events(items, store=store, now_utc=reference_now))

    if EventSource.LIKED_VIDEO in req.sources:
        liked = await _run_counted_call(
            "videos.list",
            quota_guard,
            self_charges=self_charges,
            status_before_units=status_before.units_used,
            status_before_searches=status_before.search_calls_used,
            coro=provider.list_liked_videos_rated(max_results=50),
        )
        collected_events.extend(
            events_from_liked_videos(liked, store=store, now_utc=reference_now)
        )

    try:
        profile = build_interest_profile(
            collected_events,
            now_utc=reference_now,
            config=profile_config,
            max_queries=RECOMMEND_MAX_SEARCH_CALLS,
        )
    except ToolError as exc:
        used_on_empty = _compute_delta_quota(
            units_before=status_before.units_used,
            searches_before=status_before.search_calls_used,
            guard=quota_guard,
        )
        raise ToolError(
            exc.code, exc.message, details=exc.details, quota_used=used_on_empty
        ) from exc

    candidate_ids: list[str] = []
    seen_ids: set[str] = set(profile.excluded_video_ids)
    for query in profile.search_queries[:RECOMMEND_MAX_SEARCH_CALLS]:
        if not query.strip():
            continue
        hits = await _run_counted_call(
            "search.list",
            quota_guard,
            self_charges=self_charges,
            status_before_units=status_before.units_used,
            status_before_searches=status_before.search_calls_used,
            coro=provider.search_videos(query, max_results=25),
        )
        for hit in hits:
            if hit.kind != "video" or hit.item_id in seen_ids:
                continue
            seen_ids.add(hit.item_id)
            candidate_ids.append(hit.item_id)
            if len(candidate_ids) >= 50:
                break
        if len(candidate_ids) >= 50:
            break

    candidates: list[VideoMeta] = []
    if candidate_ids:
        candidates = await _run_counted_call(
            "videos.list",
            quota_guard,
            self_charges=self_charges,
            status_before_units=status_before.units_used,
            status_before_searches=status_before.search_calls_used,
            coro=provider.get_videos(candidate_ids[:50]),
        )

    actual_used = _compute_delta_quota(
        units_before=status_before.units_used,
        searches_before=status_before.search_calls_used,
        guard=quota_guard,
    )

    ranked = score_recommendations(profile, candidates, max_results=req.max_results)
    data: dict[str, Any] = {
        "sources_used": [src.value for src in req.sources],
        "queries_used": list(profile.search_queries),
        "top_profile_terms": list(profile.top_terms[:10]),
        "timestamp_coverage": profile.coverage.to_dict(),
        "excluded_seen_count": ranked.excluded_seen_count,
        "excluded_unavailable_count": ranked.excluded_unavailable_count,
        "recommendations": [item.to_dict() for item in ranked.recommendations],
        "metadata_only_notice": (
            "Recommendations derived from explicit YouTube library signals and objective metadata "
            "only (no watch history or popularity signals)."
        ),
    }
    summary = (
        f"Generated {len(ranked.recommendations)} recommendations from "
        f"{profile.coverage.total} explicit library signals."
    )
    return success_response(summary, data, quota_used=actual_used)


def register_get_recommendations(
    server: MCPServer,
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    store: SQLiteStore | None = None,
    profile_config: ProfileConfig | None = None,
) -> None:
    """Register the read-only get_recommendations tool on an MCPServer."""

    @server.tool(
        name="get_recommendations",
        title="Get Personalized YouTube Recommendations",
        description=GET_RECOMMENDATIONS_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Get Personalized YouTube Recommendations",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    async def get_recommendations(
        ctx: Context[Any, Any],
        max_results: object = 10,
        sources: object = None,
    ) -> types.CallToolResult:
        arguments: dict[str, Any] = {"max_results": max_results}
        if sources is not None:
            arguments["sources"] = sources

        raw_params = getattr(ctx, "input_params", None) or getattr(ctx, "_input_params", None)
        raw_args = getattr(raw_params, "arguments", None)
        if isinstance(raw_args, Mapping):
            arguments = dict(raw_args)

        try:
            payload = await execute_get_recommendations(
                arguments,
                provider=provider,
                quota_guard=quota_guard,
                store=store,
                profile_config=profile_config,
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

    registered_tool = server._tool_manager.get_tool("get_recommendations")
    if registered_tool is not None:  # pragma: no branch
        registered_tool.parameters = load_schema("get_recommendations")
