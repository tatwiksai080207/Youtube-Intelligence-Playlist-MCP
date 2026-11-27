"""MCP tool and resource handlers for yt-intel-mcp."""

from __future__ import annotations

from yt_intel_mcp.tools.draft_curated_playlist import (
    DRAFT_MAX_LIST_CALLS,
    DRAFT_MAX_SEARCH_CALLS,
    DRAFT_TOOL_DESCRIPTION,
    estimate_draft_workflow_cost,
    execute_draft_curated_playlist,
    register_draft_curated_playlist,
    validate_draft_arguments,
)
from yt_intel_mcp.tools.get_auth_status import (
    AUTH_TOOL_DESCRIPTION,
    build_auth_status_payload,
    execute_get_auth_status,
    register_auth_status,
)
from yt_intel_mcp.tools.get_quota_status import (
    QUOTA_RESOURCE_URI,
    QUOTA_TOOL_DESCRIPTION,
    build_quota_metrics_payload,
    execute_get_quota_status,
    read_quota_metrics_resource,
    register_quota_status,
)
from yt_intel_mcp.tools.get_similar_videos import (
    GET_SIMILAR_VIDEOS_DESCRIPTION,
    SimilarVideosRequest,
    estimate_similar_videos_cost,
    execute_get_similar_videos,
    register_get_similar_videos,
    validate_get_similar_videos_arguments,
)

__all__ = [
    "AUTH_TOOL_DESCRIPTION",
    "DRAFT_MAX_LIST_CALLS",
    "DRAFT_MAX_SEARCH_CALLS",
    "DRAFT_TOOL_DESCRIPTION",
    "GET_SIMILAR_VIDEOS_DESCRIPTION",
    "QUOTA_RESOURCE_URI",
    "QUOTA_TOOL_DESCRIPTION",
    "SimilarVideosRequest",
    "build_auth_status_payload",
    "build_quota_metrics_payload",
    "estimate_draft_workflow_cost",
    "estimate_similar_videos_cost",
    "execute_draft_curated_playlist",
    "execute_get_auth_status",
    "execute_get_quota_status",
    "execute_get_similar_videos",
    "read_quota_metrics_resource",
    "register_auth_status",
    "register_draft_curated_playlist",
    "register_get_similar_videos",
    "register_quota_status",
    "validate_draft_arguments",
    "validate_get_similar_videos_arguments",
]
