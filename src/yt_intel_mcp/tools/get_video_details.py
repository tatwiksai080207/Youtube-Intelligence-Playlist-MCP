"""Read-only get_video_details MCP tool handler (TS-09, SK-1, SK-2, INV-03, INV-22)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

import mcp.types as types
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from yt_intel_mcp.cache import CachedYouTubeProvider
from yt_intel_mcp.durations import format_duration, format_duration_clock
from yt_intel_mcp.errors import ErrorCode, ToolError, success_response
from yt_intel_mcp.models import QuotaUsed, VideoMeta
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.sanitize import (
    DEFAULT_MAX_TITLE_LENGTH,
    sanitize_single_line,
    sanitize_text,
    sanitize_video_meta,
)
from yt_intel_mcp.schemas import load_schema
from yt_intel_mcp.validation import extract_video_id

__all__ = [
    "GET_VIDEO_DETAILS_DESCRIPTION",
    "execute_get_video_details",
    "parse_chapters_from_description",
    "register_get_video_details",
    "validate_get_video_details_arguments",
]

GET_VIDEO_DETAILS_DESCRIPTION = (
    "Fetch sanitized objective metadata for a single YouTube video by 11-character ID or URL "
    "(FR-1.4, SK-1, SK-2, NFR-6, NFR-9). Returns title, description, tags, category, parsed "
    "chapters, raw and human-readable duration, channel info, live status, and audio-language "
    "fields without popularity statistics. Side effects: none (read only). "
    "Typical cost: 1 quota unit, 0 search calls."
)

_ALLOWED_FIELDS: frozenset[str] = frozenset(load_schema("get_video_details")["properties"])
_REQUIRED_FIELDS: tuple[str, ...] = tuple(load_schema("get_video_details")["required"])

_CHAPTER_LINE_RE = re.compile(
    r"^\s*\[?(?:(?P<hours>\d{1,2}):)?(?P<minutes>\d{1,2}):(?P<seconds>[0-5]\d)\]?"
    r"\s*(?:[-\u2013\u2014|:]\s*)?(?P<title>.+?)\s*$"
)


def validate_get_video_details_arguments(arguments: Mapping[str, Any]) -> str:
    """Strictly validate get_video_details arguments before spending quota (INV-02, NFR-5)."""
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
                f"Unexpected parameter {raw_key!r} is not allowed by get_video_details schema.",
                details={"field": str(raw_key)},
            )

    for req_key in _REQUIRED_FIELDS:
        if req_key not in arguments or arguments[req_key] is None:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Missing required parameter {req_key!r}.",
                details={"field": req_key},
            )

    return extract_video_id(arguments["video_id"])


def parse_chapters_from_description(description: str) -> list[dict[str, Any]]:
    """Extract and sanitize timestamped video chapters from a video description (INV-22)."""
    if not description:
        return []

    chapters: list[dict[str, Any]] = []
    # Sanitize without truncating at 1000 chars so late chapters remain discoverable.
    cleaned_multiline = sanitize_text(description, max_length=max(len(description), 1))
    for line in cleaned_multiline.splitlines():
        match = _CHAPTER_LINE_RE.match(line)
        if match is None:
            continue
        hours_raw = match.group("hours")
        hours = int(hours_raw) if hours_raw is not None else 0
        minutes = int(match.group("minutes"))
        seconds = int(match.group("seconds"))
        if hours_raw is not None and minutes >= 60:
            continue
        total_seconds = hours * 3600 + minutes * 60 + seconds
        chapter_title = sanitize_single_line(match.group("title"), max_length=120)
        if not chapter_title:
            continue
        chapters.append(
            {
                "start_seconds": total_seconds,
                "start_timestamp": format_duration_clock(total_seconds),
                "title": chapter_title,
            }
        )
    return chapters


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


def _ensure_video_available(
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
    video = videos[0]
    privacy = video.privacy_status.strip().lower()
    if not video.is_available or privacy in {"private", "deleted"}:
        raise ToolError(
            ErrorCode.VIDEO_UNAVAILABLE,
            f"Video {video_id!r} is unavailable ({video.privacy_status}).",
            details={"video_id": video_id, "privacy_status": video.privacy_status},
            quota_used=quota_used,
        )
    return video


async def execute_get_video_details(
    arguments: Mapping[str, Any],
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
) -> dict[str, Any]:
    """Validate ID, preflight 1 u, fetch objective video details, and sanitize output."""
    video_id = validate_get_video_details_arguments(arguments)

    cost = quota_guard.estimate("videos.list", count=1)
    quota_guard.preflight(cost)

    status_before = quota_guard.status()
    self_charges = _provider_self_charges(provider)

    try:
        videos = await provider.get_videos([video_id])
    except ToolError as exc:
        if not self_charges:
            quota_guard.charge(cost)
            if exc.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM:
                quota_guard.mark_upstream_exhausted()
        used = _compute_delta_quota(
            units_before=status_before.units_used,
            searches_before=status_before.search_calls_used,
            guard=quota_guard,
        )
        raise ToolError(exc.code, exc.message, details=exc.details, quota_used=used) from exc

    if not self_charges:
        quota_guard.charge(cost)

    actual_used = _compute_delta_quota(
        units_before=status_before.units_used,
        searches_before=status_before.search_calls_used,
        guard=quota_guard,
    )
    video = _ensure_video_available(videos, video_id=video_id, quota_used=actual_used)

    clean_video = sanitize_video_meta(video)
    clean_channel_title = sanitize_single_line(
        video.channel_title, max_length=DEFAULT_MAX_TITLE_LENGTH
    )
    chapters = parse_chapters_from_description(video.description)
    is_live = clean_video.live_broadcast_content.strip().lower() not in {"", "none"}
    duration_human = format_duration(clean_video.duration_seconds, live=is_live)
    duration_clock = format_duration_clock(clean_video.duration_seconds)

    data: dict[str, Any] = {
        "video_id": clean_video.video_id,
        "title": clean_video.title,
        "description": clean_video.description,
        "tags": list(clean_video.tags),
        "category_id": clean_video.category_id,
        "category_name": clean_video.category_name,
        "channel": {
            "channel_id": clean_video.channel_id,
            "channel_title": clean_channel_title,
        },
        "published_at": (
            clean_video.published_at.isoformat() if clean_video.published_at is not None else None
        ),
        "duration_seconds": clean_video.duration_seconds,
        "duration_human": duration_human,
        "duration_clock": duration_clock,
        "live_broadcast_content": clean_video.live_broadcast_content,
        "is_live": is_live,
        "default_audio_language": clean_video.default_audio_language,
        "default_language": clean_video.default_language,
        "chapters": chapters,
        "metadata_only_notice": "Summary based on video metadata, not on the video's content",
    }
    summary = (
        f"Summary based on video metadata, not on the video's content: "
        f"{clean_video.title!r} by {clean_channel_title or 'Unknown channel'} "
        f"({duration_human}, {len(chapters)} chapters)."
    )
    return success_response(summary, data, quota_used=actual_used)


def register_get_video_details(
    server: MCPServer,
    *,
    provider: YouTubeProvider,
    quota_guard: QuotaGuard,
) -> None:
    """Register the read-only get_video_details tool on an MCPServer."""

    @server.tool(
        name="get_video_details",
        title="Get YouTube Video Details",
        description=GET_VIDEO_DETAILS_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Get YouTube Video Details",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
        structured_output=True,
    )
    async def get_video_details(
        ctx: Context[Any, Any],
        video_id: object = None,
    ) -> types.CallToolResult:
        arguments: dict[str, Any] = {"video_id": video_id}
        raw_params = getattr(ctx, "input_params", None) or getattr(ctx, "_input_params", None)
        raw_args = getattr(raw_params, "arguments", None)
        if isinstance(raw_args, Mapping):
            arguments = dict(raw_args)

        try:
            payload = await execute_get_video_details(
                arguments,
                provider=provider,
                quota_guard=quota_guard,
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

    registered_tool = server._tool_manager.get_tool("get_video_details")
    if registered_tool is not None:  # pragma: no branch
        registered_tool.parameters = load_schema("get_video_details")
