"""Read-only get_similar_videos MCP tool handler (TS-10, FR-1.1..1.4, INV-01..03)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import mcp.types as types
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from yt_intel_mcp.cache import CachedYouTubeProvider
from yt_intel_mcp.config import SimilarityConfig
from yt_intel_mcp.durations import format_duration
from yt_intel_mcp.errors import ErrorCode, ToolError, success_response
from yt_intel_mcp.models import CostEstimate, QuotaUsed, VideoMeta
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.sanitize import (
    DEFAULT_MAX_TITLE_LENGTH,
    sanitize_single_line,
    sanitize_video_meta,
)
from yt_intel_mcp.schemas import load_schema
from yt_intel_mcp.similarity.text import build_search_query
from yt_intel_mcp.similarity.videos import (
    rank_similar_videos,
    resolve_video_similarity_weights,
)
from yt_intel_mcp.validation import extract_video_id

__all__ = [
    "GET_SIMILAR_VIDEOS_DESCRIPTION",
    "SimilarVideosRequest",
    "estimate_similar_videos_cost",
    "execute_get_similar_videos",
    "register_get_similar_videos",
    "validate_get_similar_videos_arguments",
]

GET_SIMILAR_VIDEOS_DESCRIPTION = (
    "Find and rank YouTube videos similar to a seed video using objective metadata only "
    "(FR-1.1..1.4, INV-01). Ranks candidates by TF-IDF title, tags, description, category, "
    "and duration similarity with dynamic missing-field weight redistribution and zero "
    "popularity signals. Side effects: none (read only). "
    "Typical cost: 1 search call + 2 quota units."
)

_ALLOWED_FIELDS: frozenset[str] = frozenset(load_schema("get_similar_videos")["properties"])
_REQUIRED_FIELDS: tuple[str, ...] = tuple(load_schema("get_similar_videos")["required"])
_MAX_CANDIDATE_DETAILS = 50


@dataclass(frozen=True, slots=True)
class SimilarVideosRequest:
    """Validated input arguments for get_similar_videos."""

    video_id: str
    max_results: int
    weights: dict[str, float]


def validate_get_similar_videos_arguments(
    arguments: Mapping[str, Any],
    *,
    similarity_config: SimilarityConfig | None = None,
) -> SimilarVideosRequest:
    """Strictly validate get_similar_videos arguments pre-quota (INV-02, NFR-5)."""
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
                f"Unexpected parameter {raw_key!r} is not allowed by get_similar_videos schema.",
                details={"field": str(raw_key)},
            )

    for req_key in _REQUIRED_FIELDS:
        if req_key not in arguments or arguments[req_key] is None:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Missing required parameter {req_key!r}.",
                details={"field": req_key},
            )

    video_id = extract_video_id(arguments["video_id"])

    raw_max = arguments.get("max_results", 10)
    if isinstance(raw_max, bool) or not isinstance(raw_max, int) or not (1 <= raw_max <= 50):
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "max_results must be an integer between 1 and 50.",
            details={"field": "max_results"},
        )

    weights = resolve_video_similarity_weights(
        arguments.get("scoring_weights"),
        config=similarity_config,
    )
    return SimilarVideosRequest(video_id=video_id, max_results=raw_max, weights=weights)


def estimate_similar_videos_cost(quota_guard: QuotaGuard) -> CostEstimate:
    """Estimate worst-case read cost for get_similar_videos (<= 1 search + 2 units)."""
    seed_cost = quota_guard.estimate("videos.list", count=1)
    search_cost = quota_guard.estimate("search.list", count=1)
    cand_cost = quota_guard.estimate("videos.list", count=1)
    return CostEstimate(
        units=seed_cost.units + search_cost.units + cand_cost.units,
        search_calls=search_cost.search_calls,
        operation="get_similar_videos",
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


def _ensure_seed_available(
    videos: list[VideoMeta],
    *,
    video_id: str,
    quota_used: QuotaUsed,
) -> VideoMeta:
    if not videos:
        raise ToolError(
            ErrorCode.VIDEO_UNAVAILABLE,
            f"Video {video_id!r} was not found or is unavailable.",
            details={"video_id": video_id, "reason": "not_found"},
            quota_used=quota_used,
        )
    seed = videos[0]
    privacy = seed.privacy_status.strip().lower()
    if not seed.is_available or privacy in {"private", "deleted"}:
        raise ToolError(
            ErrorCode.VIDEO_UNAVAILABLE,
            f"Video {video_id!r} is unavailable ({seed.privacy_status}).",
            details={"video_id": video_id, "privacy_status": seed.privacy_status},
            quota_used=quota_used,
        )
    return seed


async def execute_get_similar_videos(
    arguments: Mapping[str, Any],
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    similarity_config: SimilarityConfig | None = None,
) -> dict[str, Any]:
    """Validate input, preflight <= 1s + 2u, fetch seed & candidates, and rank."""
    req = validate_get_similar_videos_arguments(
        arguments, similarity_config=similarity_config
    )
    workflow_cost = estimate_similar_videos_cost(quota_guard)
    quota_guard.preflight(workflow_cost)

    status_before = quota_guard.status()
    self_charges = _provider_self_charges(provider)

    async def _charge_on_call(op: str) -> CostEstimate:
        return quota_guard.estimate(op, count=1)

    # 1. Fetch seed video metadata (1 u).
    seed_cost = await _charge_on_call("videos.list")
    try:
        seed_list = await provider.get_videos([req.video_id])
    except ToolError as exc:
        if not self_charges:
            quota_guard.charge(seed_cost)
            if exc.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM:
                quota_guard.mark_upstream_exhausted()
        used = _compute_delta_quota(
            units_before=status_before.units_used,
            searches_before=status_before.search_calls_used,
            guard=quota_guard,
        )
        raise ToolError(exc.code, exc.message, details=exc.details, quota_used=used) from exc

    if not self_charges:
        quota_guard.charge(seed_cost)

    used_after_seed = _compute_delta_quota(
        units_before=status_before.units_used,
        searches_before=status_before.search_calls_used,
        guard=quota_guard,
    )
    seed_video = _ensure_seed_available(
        seed_list, video_id=req.video_id, quota_used=used_after_seed
    )
    clean_seed = sanitize_video_meta(seed_video)

    # 2. Build deterministic search query from objective title + tags.
    query = build_search_query(clean_seed.title, clean_seed.tags, max_terms=5)
    if not query and clean_seed.category_name:
        query = sanitize_single_line(clean_seed.category_name, max_length=100)
    if not query:
        query = clean_seed.video_id

    # 3. Search candidate videos (1 s).
    search_cost = await _charge_on_call("search.list")
    try:
        hits = await provider.search_videos(query, max_results=_MAX_CANDIDATE_DETAILS)
    except ToolError as exc:
        if not self_charges:
            quota_guard.charge(search_cost)
            if exc.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM:
                quota_guard.mark_upstream_exhausted()
        used = _compute_delta_quota(
            units_before=status_before.units_used,
            searches_before=status_before.search_calls_used,
            guard=quota_guard,
        )
        raise ToolError(exc.code, exc.message, details=exc.details, quota_used=used) from exc

    if not self_charges:
        quota_guard.charge(search_cost)

    candidate_ids: list[str] = []
    seen_ids: set[str] = {req.video_id}
    for hit in hits:
        if hit.kind != "video" or hit.item_id in seen_ids:
            continue
        seen_ids.add(hit.item_id)
        candidate_ids.append(hit.item_id)
        if len(candidate_ids) >= _MAX_CANDIDATE_DETAILS:
            break

    # 4. Fetch candidate video details (<= 1 u) if any candidates found.
    candidates: list[VideoMeta] = []
    if candidate_ids:
        cand_cost = await _charge_on_call("videos.list")
        try:
            candidates = await provider.get_videos(candidate_ids)
        except ToolError as exc:
            if not self_charges:
                quota_guard.charge(cand_cost)
                if exc.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM:
                    quota_guard.mark_upstream_exhausted()
            used = _compute_delta_quota(
                units_before=status_before.units_used,
                searches_before=status_before.search_calls_used,
                guard=quota_guard,
            )
            raise ToolError(exc.code, exc.message, details=exc.details, quota_used=used) from exc
        if not self_charges:
            quota_guard.charge(cand_cost)

    actual_used = _compute_delta_quota(
        units_before=status_before.units_used,
        searches_before=status_before.search_calls_used,
        guard=quota_guard,
    )

    ranking = rank_similar_videos(
        clean_seed,
        candidates,
        weights=req.weights,
        max_results=req.max_results,
        similarity_config=similarity_config,
    )
    clean_channel_title = sanitize_single_line(
        clean_seed.channel_title, max_length=DEFAULT_MAX_TITLE_LENGTH
    )

    data: dict[str, Any] = {
        "seed_video": {
            "video_id": clean_seed.video_id,
            "title": clean_seed.title,
            "channel_id": clean_seed.channel_id,
            "channel_title": clean_channel_title,
            "category_id": clean_seed.category_id,
            "duration_seconds": clean_seed.duration_seconds,
            "duration_human": format_duration(
                clean_seed.duration_seconds,
                live=clean_seed.live_broadcast_content.strip().lower() not in {"", "none"},
            ),
            "tags": list(clean_seed.tags),
        },
        "query_used": query,
        "active_weights": {
            key: round(val, 6) for key, val in ranking.active_weights.items()
        },
        "results": [item.to_dict() for item in ranking.ranked_videos],
        "total_candidates_evaluated": ranking.total_candidates_evaluated,
        "excluded_count": ranking.excluded_count,
        "metadata_only_notice": (
            "Similarity ranked by objective video metadata only (no popularity signals)."
        ),
    }
    summary = (
        f"Found {len(ranking.ranked_videos)} similar videos for {clean_seed.title!r} "
        f"using objective metadata only ({ranking.total_candidates_evaluated} candidates)."
    )
    return success_response(summary, data, quota_used=actual_used)


def register_get_similar_videos(
    server: MCPServer,
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
    similarity_config: SimilarityConfig | None = None,
) -> None:
    """Register the read-only get_similar_videos tool on an MCPServer."""

    @server.tool(
        name="get_similar_videos",
        title="Get Similar YouTube Videos",
        description=GET_SIMILAR_VIDEOS_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Get Similar YouTube Videos",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    async def get_similar_videos(
        ctx: Context[Any, Any],
        video_id: object = None,
        max_results: object = 10,
        scoring_weights: object = None,
    ) -> types.CallToolResult:
        arguments: dict[str, Any] = {
            "video_id": video_id,
            "max_results": max_results,
        }
        if scoring_weights is not None:
            arguments["scoring_weights"] = scoring_weights

        raw_params = getattr(ctx, "input_params", None) or getattr(ctx, "_input_params", None)
        raw_args = getattr(raw_params, "arguments", None)
        if isinstance(raw_args, Mapping):
            arguments = dict(raw_args)

        try:
            payload = await execute_get_similar_videos(
                arguments,
                provider=provider,
                quota_guard=quota_guard,
                similarity_config=similarity_config,
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

    registered_tool = server._tool_manager.get_tool("get_similar_videos")
    if registered_tool is not None:  # pragma: no branch
        registered_tool.parameters = load_schema("get_similar_videos")
