"""Zero-cost authentication status tool returning scopes and channel presence only (FR-7.2)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from yt_intel_mcp.auth.token_store import YOUTUBE_FORCE_SSL_SCOPE, TokenStore
from yt_intel_mcp.errors import success_response
from yt_intel_mcp.models import QuotaUsed

__all__ = [
    "AUTH_TOOL_DESCRIPTION",
    "build_auth_status_payload",
    "execute_get_auth_status",
    "register_auth_status",
]

AUTH_TOOL_DESCRIPTION = (
    "Inspect local Google OAuth authentication state, granted YouTube scopes, token expiry, "
    "storage backend, and YouTube channel availability without returning any credentials. "
    "Side effects: none. Cost: 0 quota units, 0 search calls."
)

_YOUTUBE_FULL_SCOPE = "https://www.googleapis.com/auth/youtube"


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def build_auth_status_payload(
    token_store: TokenStore,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Build non-secret authentication status payload (never exposes access or refresh tokens)."""
    meta = token_store.read_metadata()
    if not meta.authenticated:
        return {
            "authenticated": False,
            "scopes": [],
            "has_channel": None,
            "storage_backend": "none",
            "expires_at": None,
            "issued_at": None,
            "access_token_expired": None,
            "write_scope_granted": False,
        }

    effective_now = _ensure_utc(now_utc) if now_utc is not None else datetime.now(UTC)
    expired = meta.expires_at_utc is not None and effective_now >= meta.expires_at_utc
    write_granted = YOUTUBE_FORCE_SSL_SCOPE in meta.scopes or _YOUTUBE_FULL_SCOPE in meta.scopes
    return {
        "authenticated": True,
        "scopes": list(meta.scopes),
        "has_channel": meta.has_channel,
        "storage_backend": meta.storage_backend,
        "expires_at": meta.expires_at_utc.isoformat() if meta.expires_at_utc else None,
        "issued_at": meta.issued_at_utc.isoformat() if meta.issued_at_utc else None,
        "access_token_expired": expired,
        "write_scope_granted": write_granted,
    }


def execute_get_auth_status(
    token_store: TokenStore,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Return canonical SRS Section 4.1 envelope for get_auth_status (0 quota, 0 secrets)."""
    data = build_auth_status_payload(token_store, now_utc=now_utc)
    if not data["authenticated"]:
        summary = "Not authenticated. No local OAuth credentials are stored."
    else:
        channel_text = (
            "channel present"
            if data["has_channel"] is True
            else (
                "no YouTube channel (read-only allowed)"
                if data["has_channel"] is False
                else "unknown"
            )
        )
        write_text = "write scope granted" if data["write_scope_granted"] else "read-only scope"
        summary = (
            f"Authenticated via {data['storage_backend']} backend ({write_text}; {channel_text})."
        )
    return success_response(summary, data, quota_used=QuotaUsed())


def register_auth_status(
    server: MCPServer,
    token_store: TokenStore,
    *,
    clock: Callable[[], datetime] | None = None,
) -> None:
    """Register the zero-cost get_auth_status MCP tool."""

    @server.tool(
        name="get_auth_status",
        title="Get YouTube OAuth Authentication Status",
        description=AUTH_TOOL_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Get YouTube OAuth Authentication Status",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    async def get_auth_status() -> dict[str, Any]:
        now = clock() if clock is not None else None
        return execute_get_auth_status(token_store, now_utc=now)
