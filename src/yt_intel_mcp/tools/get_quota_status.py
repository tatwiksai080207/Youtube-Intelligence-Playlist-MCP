"""Zero-cost quota status tool and youtube://metrics/quota MCP resource (FR-6.1, NFR-9)."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from yt_intel_mcp.errors import success_response
from yt_intel_mcp.models import QuotaUsed
from yt_intel_mcp.quota.guard import QuotaGuard

__all__ = [
    "QUOTA_RESOURCE_URI",
    "QUOTA_TOOL_DESCRIPTION",
    "build_quota_metrics_payload",
    "execute_get_quota_status",
    "read_quota_metrics_resource",
    "register_quota_status",
]

QUOTA_RESOURCE_URI = "youtube://metrics/quota"
QUOTA_TOOL_DESCRIPTION = (
    "Inspect local dual daily YouTube API quota usage, remaining units and search.list calls, "
    "and next 00:00 Pacific Time reset without modifying state or spending API quota. "
    "Side effects: none. Cost: 0 quota units, 0 search calls."
)


def build_quota_metrics_payload(
    guard: QuotaGuard,
    *,
    reset_timezone: str = "America/Los_Angeles",
) -> dict[str, Any]:
    """Serialize current dual budget status for tools and the quota metrics resource."""
    snapshot = guard.status()
    return {
        "units": {
            "used": snapshot.units_used,
            "limit": snapshot.units_limit,
            "remaining": snapshot.units_remaining,
        },
        "search_calls": {
            "used": snapshot.search_calls_used,
            "limit": snapshot.search_calls_limit,
            "remaining": snapshot.search_calls_remaining,
        },
        "reset_at": snapshot.reset_at.isoformat(),
        "reset_timezone": reset_timezone,
        "upstream_exhausted": snapshot.upstream_exhausted,
    }


def execute_get_quota_status(
    guard: QuotaGuard,
    *,
    reset_timezone: str = "America/Los_Angeles",
) -> dict[str, Any]:
    """Build the canonical SRS Section 4.1 success envelope for get_quota_status (0 quota)."""
    data = build_quota_metrics_payload(guard, reset_timezone=reset_timezone)
    units = data["units"]
    searches = data["search_calls"]
    exhausted_note = (
        " Upstream quota marked exhausted until reset." if data["upstream_exhausted"] else ""
    )
    summary = (
        f"Quota status: {units['used']}/{units['limit']} units used "
        f"({units['remaining']} remaining); "
        f"{searches['used']}/{searches['limit']} search calls used "
        f"({searches['remaining']} remaining). "
        f"Resets at {data['reset_at']} ({reset_timezone}).{exhausted_note}"
    )
    return success_response(summary, data, quota_used=QuotaUsed())


def read_quota_metrics_resource(
    guard: QuotaGuard,
    *,
    reset_timezone: str = "America/Los_Angeles",
) -> str:
    """Serialize the youtube://metrics/quota JSON document without consuming quota."""
    payload = build_quota_metrics_payload(guard, reset_timezone=reset_timezone)
    return json.dumps(payload, indent=2)


def register_quota_status(
    server: MCPServer,
    guard: QuotaGuard,
    *,
    reset_timezone: str = "America/Los_Angeles",
) -> None:
    """Register the zero-cost get_quota_status tool and youtube://metrics/quota resource."""

    @server.tool(
        name="get_quota_status",
        title="Get Daily YouTube API Quota Status",
        description=QUOTA_TOOL_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Get Daily YouTube API Quota Status",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    async def get_quota_status() -> dict[str, Any]:
        return execute_get_quota_status(guard, reset_timezone=reset_timezone)

    @server.resource(
        QUOTA_RESOURCE_URI,
        name="youtube-quota-metrics",
        title="Daily YouTube API Quota Metrics",
        description=(
            "Read-only snapshot of daily quota units, search.list call bucket, "
            "and next Pacific Time reset (0 quota cost)."
        ),
        mime_type="application/json",
    )
    async def quota_metrics() -> str:
        return read_quota_metrics_resource(guard, reset_timezone=reset_timezone)
