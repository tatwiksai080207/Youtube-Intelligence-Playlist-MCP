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
from yt_intel_mcp.tools.get_quota_status import (
    QUOTA_RESOURCE_URI,
    QUOTA_TOOL_DESCRIPTION,
    build_quota_metrics_payload,
    execute_get_quota_status,
    read_quota_metrics_resource,
    register_quota_status,
)

__all__ = [
    "DRAFT_MAX_LIST_CALLS",
    "DRAFT_MAX_SEARCH_CALLS",
    "DRAFT_TOOL_DESCRIPTION",
    "QUOTA_RESOURCE_URI",
    "QUOTA_TOOL_DESCRIPTION",
    "build_quota_metrics_payload",
    "estimate_draft_workflow_cost",
    "execute_draft_curated_playlist",
    "execute_get_quota_status",
    "read_quota_metrics_resource",
    "register_draft_curated_playlist",
    "register_quota_status",
    "validate_draft_arguments",
]
