"""MCP tool and resource handlers for yt-intel-mcp."""

from __future__ import annotations

from yt_intel_mcp.tools.analyze_engagement import (
    ANALYZE_ENGAGEMENT_DESCRIPTION,
    USER_CONTEXT_RESOURCE_URI,
    AnalyzeEngagementRequest,
    estimate_engagement_cost,
    execute_analyze_engagement,
    read_user_context_resource,
    register_analyze_engagement,
    validate_analyze_engagement_arguments,
)
from yt_intel_mcp.tools.create_curated_playlist import (
    CREATE_PLAYLIST_DESCRIPTION,
    execute_create_curated_playlist,
    register_create_curated_playlist,
    validate_create_curated_playlist_arguments,
)
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
from yt_intel_mcp.tools.get_recommendations import (
    GET_RECOMMENDATIONS_DESCRIPTION,
    RecommendationsRequest,
    estimate_recommendations_cost,
    execute_get_recommendations,
    register_get_recommendations,
    validate_get_recommendations_arguments,
)
from yt_intel_mcp.tools.get_similar_videos import (
    GET_SIMILAR_VIDEOS_DESCRIPTION,
    SimilarVideosRequest,
    estimate_similar_videos_cost,
    execute_get_similar_videos,
    register_get_similar_videos,
    validate_get_similar_videos_arguments,
)
from yt_intel_mcp.tools.get_video_details import (
    GET_VIDEO_DETAILS_DESCRIPTION,
    execute_get_video_details,
    register_get_video_details,
    validate_get_video_details_arguments,
)

__all__ = [
    "ANALYZE_ENGAGEMENT_DESCRIPTION",
    "AUTH_TOOL_DESCRIPTION",
    "CREATE_PLAYLIST_DESCRIPTION",
    "DRAFT_MAX_LIST_CALLS",
    "DRAFT_MAX_SEARCH_CALLS",
    "DRAFT_TOOL_DESCRIPTION",
    "GET_RECOMMENDATIONS_DESCRIPTION",
    "GET_SIMILAR_VIDEOS_DESCRIPTION",
    "GET_VIDEO_DETAILS_DESCRIPTION",
    "QUOTA_RESOURCE_URI",
    "QUOTA_TOOL_DESCRIPTION",
    "USER_CONTEXT_RESOURCE_URI",
    "AnalyzeEngagementRequest",
    "RecommendationsRequest",
    "SimilarVideosRequest",
    "build_auth_status_payload",
    "build_quota_metrics_payload",
    "estimate_draft_workflow_cost",
    "estimate_engagement_cost",
    "estimate_recommendations_cost",
    "estimate_similar_videos_cost",
    "execute_analyze_engagement",
    "execute_create_curated_playlist",
    "execute_draft_curated_playlist",
    "execute_get_auth_status",
    "execute_get_quota_status",
    "execute_get_recommendations",
    "execute_get_similar_videos",
    "execute_get_video_details",
    "read_quota_metrics_resource",
    "read_user_context_resource",
    "register_analyze_engagement",
    "register_auth_status",
    "register_create_curated_playlist",
    "register_draft_curated_playlist",
    "register_get_recommendations",
    "register_get_similar_videos",
    "register_get_video_details",
    "register_quota_status",
    "validate_analyze_engagement_arguments",
    "validate_create_curated_playlist_arguments",
    "validate_draft_arguments",
    "validate_get_recommendations_arguments",
    "validate_get_similar_videos_arguments",
    "validate_get_video_details_arguments",
]
