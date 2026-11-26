"""Read-only draft_curated_playlist MCP tool handler (MF-11, FR-5.1..5.3, FR-6.2)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import mcp.types as types
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from yt_intel_mcp.cache import CachedYouTubeProvider
from yt_intel_mcp.config import AppConfig, PlaylistConfig
from yt_intel_mcp.errors import ErrorCode, ToolError, success_response
from yt_intel_mcp.models import CostEstimate, QuotaUsed, SearchHit, VideoMeta
from yt_intel_mcp.playlist.constraints import PlaylistConstraints, build_playlist_constraints
from yt_intel_mcp.playlist.drafts import DraftStore
from yt_intel_mcp.playlist.solver import PlaylistSolution, solve_playlist_selection
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.sanitize import sanitize_single_line
from yt_intel_mcp.schemas import load_schema
from yt_intel_mcp.similarity.text import build_search_query

__all__ = [
    "DRAFT_MAX_LIST_CALLS",
    "DRAFT_MAX_SEARCH_CALLS",
    "DRAFT_TOOL_DESCRIPTION",
    "estimate_draft_workflow_cost",
    "execute_draft_curated_playlist",
    "register_draft_curated_playlist",
    "validate_draft_arguments",
]

DRAFT_MAX_SEARCH_CALLS = 3
DRAFT_MAX_LIST_CALLS = 5
_SEARCH_PAGE_SIZE = 50
_VIDEO_BATCH_SIZE = 50

DRAFT_TOOL_DESCRIPTION = (
    "Discover candidate YouTube videos from objective metadata and build an immutable, "
    "10-minute expiring playlist draft matching strict duration and spoken audio-language "
    "constraints (FR-5.1, FR-5.1a, FR-5.2, FR-5.3, FR-6.2). Preflights worst-case playlist "
    "workflow budget before API calls. Side effects: none (read only, creates no playlist). "
    "Typical read cost: <= 3 search.list calls and <= 5 videos.list units."
)

_ALLOWED_DRAFT_FIELDS: frozenset[str] = frozenset(
    load_schema("draft_curated_playlist")["properties"]
)
_REQUIRED_DRAFT_FIELDS: tuple[str, ...] = tuple(load_schema("draft_curated_playlist")["required"])


def validate_draft_arguments(
    arguments: Mapping[str, Any],
    *,
    config: PlaylistConfig | None = None,
) -> PlaylistConstraints:
    """Strictly validate draft_curated_playlist arguments before spending quota (INV-02, NFR-5)."""
    if not isinstance(arguments, Mapping):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "Tool arguments must be a JSON object.",
            details={"field": "arguments"},
        )

    for raw_key in arguments:
        if raw_key not in _ALLOWED_DRAFT_FIELDS:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                (
                    f"Unexpected parameter {raw_key!r} is not allowed by "
                    "draft_curated_playlist schema."
                ),
                details={"field": str(raw_key)},
            )

    for req_key in _REQUIRED_DRAFT_FIELDS:
        if req_key not in arguments or arguments[req_key] is None:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Missing required parameter {req_key!r}.",
                details={"field": req_key},
            )

    constraints = build_playlist_constraints(
        topic=arguments["topic"],
        target_total_minutes=arguments["target_total_minutes"],
        tolerance_percent=arguments.get("tolerance_percent"),
        max_video_minutes=arguments.get("max_video_minutes"),
        max_videos=arguments.get("max_videos"),
        language=arguments.get("language"),
        allow_unknown_language=arguments.get("allow_unknown_language"),
        title=arguments.get("title"),
        privacy_status=arguments.get("privacy_status"),
        config=config,
    )
    if not sanitize_single_line(constraints.topic, max_length=300):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            (
                "Parameter 'topic' must contain searchable text after stripping links "
                "and control characters."
            ),
            details={"field": "topic"},
        )
    return constraints


def estimate_draft_workflow_cost(
    constraints: PlaylistConstraints,
    quota_guard: QuotaGuard,
    *,
    max_search_calls: int = DRAFT_MAX_SEARCH_CALLS,
    max_list_calls: int = DRAFT_MAX_LIST_CALLS,
) -> CostEstimate:
    """Estimate combined read budget plus worst-case write cost per ADR-0005 G-03 (FR-6.2)."""
    search_est = quota_guard.estimate("search.list", count=max_search_calls)
    list_est = quota_guard.estimate("videos.list", count=max_list_calls)
    write_create_est = quota_guard.estimate("playlists.insert", count=1)
    write_items_est = quota_guard.estimate("playlistItems.insert", count=constraints.max_videos)

    return CostEstimate(
        units=search_est.units + list_est.units + write_create_est.units + write_items_est.units,
        search_calls=search_est.search_calls,
        operation="draft_curated_playlist_workflow",
    )


def _provider_self_charges(provider: YouTubeProvider) -> bool:
    return isinstance(provider, CachedYouTubeProvider) or (
        getattr(provider, "quota_guard", None) is not None
    )


async def _fetch_search_page(
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    *,
    self_charges: bool,
    query: str,
    page_token: str | None = None,
) -> list[SearchHit]:
    cost = quota_guard.estimate("search.list", count=1)
    try:
        hits = await provider.search_videos(
            query,
            max_results=_SEARCH_PAGE_SIZE,
            page_token=page_token,
        )
    except ToolError as exc:
        if not self_charges:
            quota_guard.charge(cost)
            if exc.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM:
                quota_guard.mark_upstream_exhausted()
        raise
    if not self_charges:
        quota_guard.charge(cost)
    return hits


async def _fetch_video_batch(
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    *,
    self_charges: bool,
    video_ids: list[str],
) -> list[VideoMeta]:
    cost = quota_guard.estimate("videos.list", count=1)
    try:
        videos = await provider.get_videos(video_ids)
    except ToolError as exc:
        if not self_charges:
            quota_guard.charge(cost)
            if exc.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM:
                quota_guard.mark_upstream_exhausted()
        raise
    if not self_charges:
        quota_guard.charge(cost)
    return videos


async def execute_draft_curated_playlist(
    arguments: Mapping[str, Any],
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    draft_store: DraftStore,
    app_config: AppConfig | None = None,
) -> dict[str, Any]:
    """Run G-03 workflow preflight, candidate reads (<= 3s + 5u), solve, and freeze draft."""
    playlist_cfg = app_config.playlist if app_config is not None else None
    constraints = validate_draft_arguments(arguments, config=playlist_cfg)

    workflow_cost = estimate_draft_workflow_cost(constraints, quota_guard)
    quota_guard.preflight(workflow_cost)

    status_before = quota_guard.status()
    self_charges = _provider_self_charges(provider)

    primary_query = sanitize_single_line(constraints.topic, max_length=300) or constraints.topic
    compact_query = build_search_query(primary_query, max_terms=4)

    pending_queries: list[tuple[str, str | None]] = [(primary_query, None)]
    seen_queries: set[tuple[str, str | None]] = set()

    collected_by_id: dict[str, VideoMeta] = {}
    fetched_ids: set[str] = set()
    searches_used = 0
    list_calls_used = 0
    compact_queued = False

    solution: PlaylistSolution | None = None
    last_unsatisfiable: ToolError | None = None

    try:
        while (
            pending_queries
            and searches_used < DRAFT_MAX_SEARCH_CALLS
            and list_calls_used < DRAFT_MAX_LIST_CALLS
        ):
            query, page_token = pending_queries.pop(0)
            query_key = (query.strip().lower(), page_token)
            if query_key in seen_queries or not query.strip():
                continue
            seen_queries.add(query_key)

            searches_used += 1
            hits = await _fetch_search_page(
                provider,
                quota_guard,
                self_charges=self_charges,
                query=query,
                page_token=page_token,
            )

            new_ids: list[str] = []
            for hit in hits:
                if hit.kind != "video" or hit.item_id in fetched_ids or hit.item_id in new_ids:
                    continue
                new_ids.append(hit.item_id)

            for idx in range(0, len(new_ids), _VIDEO_BATCH_SIZE):
                if list_calls_used >= DRAFT_MAX_LIST_CALLS:
                    break
                batch = new_ids[idx : idx + _VIDEO_BATCH_SIZE]
                list_calls_used += 1
                fetched_ids.update(batch)
                fetched_videos = await _fetch_video_batch(
                    provider,
                    quota_guard,
                    self_charges=self_charges,
                    video_ids=batch,
                )
                for video in fetched_videos:
                    collected_by_id.setdefault(video.video_id, video)

            if collected_by_id:
                try:
                    solution = solve_playlist_selection(
                        list(collected_by_id.values()),
                        constraints,
                        similarity_config=app_config.similarity if app_config else None,
                    )
                    break
                except ToolError as exc:
                    if exc.code is not ErrorCode.CONSTRAINTS_UNSATISFIABLE:  # pragma: no cover
                        raise
                    last_unsatisfiable = exc

            if len(hits) == _SEARCH_PAGE_SIZE:
                next_offset = str((int(page_token) if page_token else 0) + _SEARCH_PAGE_SIZE)
                pending_queries.append((query, next_offset))
            elif (
                not compact_queued
                and compact_query
                and compact_query.lower() != primary_query.lower()
            ):
                compact_queued = True
                pending_queries.append((compact_query, None))

        if solution is None:
            if not collected_by_id or last_unsatisfiable is None:
                # Raise diagnostic CONSTRAINTS_UNSATISFIABLE directly from solver.
                solve_playlist_selection(list(collected_by_id.values()), constraints)
            else:
                raise last_unsatisfiable
    except ToolError as exc:
        status_after = quota_guard.status()
        actual_used = QuotaUsed(
            units=max(0, status_after.units_used - status_before.units_used),
            search_calls=max(0, status_after.search_calls_used - status_before.search_calls_used),
        )
        exc.quota_used = actual_used
        raise

    assert solution is not None
    status_after = quota_guard.status()
    actual_used = QuotaUsed(
        units=max(0, status_after.units_used - status_before.units_used),
        search_calls=max(0, status_after.search_calls_used - status_before.search_calls_used),
    )

    draft = draft_store.create_from_solution(constraints, solution)
    view = draft.to_view(now_utc=draft.created_at_utc)
    summary = (
        f"Drafted '{draft.title}' ({draft.privacy_status}, {len(draft.videos)} videos, "
        f"{draft.total_duration_human} within {view['target_window']['min_human']}-"
        f"{view['target_window']['max_human']} target window; draft_id={draft.draft_id}, "
        f"expires in {draft_store.ttl_seconds // 60}m, no playlist created yet)."
    )
    return success_response(summary, view, quota_used=actual_used)


def register_draft_curated_playlist(
    server: MCPServer,
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    draft_store: DraftStore,
    app_config: AppConfig | None = None,
) -> None:
    """Register the read-only draft_curated_playlist tool on an MCPServer."""

    @server.tool(
        name="draft_curated_playlist",
        title="Draft Curated YouTube Playlist",
        description=DRAFT_TOOL_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Draft Curated YouTube Playlist",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    async def draft_curated_playlist(
        ctx: Context[Any, Any],
        topic: object = None,
        target_total_minutes: object = None,
        tolerance_percent: object | None = None,
        max_video_minutes: object | None = None,
        max_videos: object | None = None,
        language: object | None = None,
        allow_unknown_language: object | None = None,
        title: object | None = None,
        privacy_status: object | None = None,
    ) -> types.CallToolResult:
        arguments: dict[str, Any] = {
            "topic": topic,
            "target_total_minutes": target_total_minutes,
        }
        optional_fields: dict[str, object | None] = {
            "tolerance_percent": tolerance_percent,
            "max_video_minutes": max_video_minutes,
            "max_videos": max_videos,
            "language": language,
            "allow_unknown_language": allow_unknown_language,
            "title": title,
            "privacy_status": privacy_status,
        }
        for key, value in optional_fields.items():
            if value is not None:
                arguments[key] = value

        raw_params = getattr(ctx, "input_params", None) or getattr(ctx, "_input_params", None)
        raw_args = getattr(raw_params, "arguments", None)
        if isinstance(raw_args, Mapping):
            arguments = dict(raw_args)

        try:
            payload = await execute_draft_curated_playlist(
                arguments,
                provider=provider,
                quota_guard=quota_guard,
                draft_store=draft_store,
                app_config=app_config,
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

    registered_tool = server._tool_manager.get_tool("draft_curated_playlist")
    if registered_tool is not None:  # pragma: no branch
        registered_tool.parameters = load_schema("draft_curated_playlist")
