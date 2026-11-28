"""MCP server runtime construction and tool registration (SR-15, SRS §3.1, SE-6, FR-8.1).

Wires application configuration, persistence stores, quota ledgers, authentication,
caching layers, and all registered MCP tools and resources into an operational server.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.server.mcpserver import MCPServer

from yt_intel_mcp import SERVER_NAME, __version__
from yt_intel_mcp.auth.token_store import TokenStore
from yt_intel_mcp.cache import CachedYouTubeProvider, MetadataCache
from yt_intel_mcp.config import AppConfig, load_config
from yt_intel_mcp.confirmation.tokens import ConfirmationTokenStore
from yt_intel_mcp.playlist.drafts import DraftStore
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.provider.fixture import FixtureYouTubeProvider
from yt_intel_mcp.provider.live import LiveYouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.quota.ledger import PersistentQuotaLedger
from yt_intel_mcp.store import SQLiteStore
from yt_intel_mcp.tools.analyze_engagement import register_analyze_engagement
from yt_intel_mcp.tools.create_curated_playlist import register_create_curated_playlist
from yt_intel_mcp.tools.draft_curated_playlist import register_draft_curated_playlist
from yt_intel_mcp.tools.get_auth_status import register_auth_status
from yt_intel_mcp.tools.get_quota_status import register_quota_status
from yt_intel_mcp.tools.get_recommendations import register_get_recommendations
from yt_intel_mcp.tools.get_similar_videos import register_get_similar_videos
from yt_intel_mcp.tools.get_video_details import register_get_video_details

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

INSTRUCTIONS = (
    "YouTube Video Intelligence server. Ranks videos and channels by objective "
    "metadata only and never creates a playlist without trusted user confirmation."
)

__all__ = [
    "INSTRUCTIONS",
    "ServerRuntime",
    "build_server_runtime",
    "create_base_server",
    "create_server",
]


@dataclass(slots=True)
class ServerRuntime:
    """Subsystem runtime container maintaining server components (SR-15, SRS §3.1)."""

    server: MCPServer
    config: AppConfig
    store: SQLiteStore
    quota_ledger: PersistentQuotaLedger | QuotaGuard
    token_store: TokenStore
    draft_store: DraftStore
    confirmation_store: ConfirmationTokenStore
    base_provider: YouTubeProvider
    provider: YouTubeProvider
    cache: MetadataCache | None = None


def create_base_server(
    name: str = SERVER_NAME,
    version: str = __version__,
    instructions: str = INSTRUCTIONS,
) -> MCPServer:
    """Build a bare MCPServer without registered tools or resources."""
    return MCPServer(
        name=name,
        version=version,
        instructions=instructions,
    )


def build_server_runtime(
    config: AppConfig | None = None,
    *,
    provider: YouTubeProvider | None = None,
    store: SQLiteStore | None = None,
    quota_ledger: PersistentQuotaLedger | QuotaGuard | None = None,
    token_store: TokenStore | None = None,
    draft_store: DraftStore | None = None,
    confirmation_store: ConfirmationTokenStore | None = None,
    cache: MetadataCache | None = None,
    enable_cache: bool = True,
    register_tools: bool = True,
    browser_opener: Callable[[str], None] | None = None,
    confirmation_timeout_seconds: float = 120.0,
) -> ServerRuntime:
    """Wire subsystem dependencies and return an initialized ServerRuntime (SRS §3.1)."""
    cfg = config or load_config()

    effective_store = store or SQLiteStore.from_config(cfg)
    effective_quota = quota_ledger or PersistentQuotaLedger(effective_store, cfg.quota)
    effective_token_store = token_store or TokenStore.from_config(cfg)
    effective_draft_store = draft_store or DraftStore(config=cfg.draft)
    effective_confirm_store = confirmation_store or ConfirmationTokenStore()

    if provider is not None:
        base_provider = provider
    elif cfg.provider_mode == "live":
        base_provider = LiveYouTubeProvider.from_config(
            cfg,
            quota_guard=effective_quota,
            token_store=effective_token_store,
        )
    else:
        base_provider = FixtureYouTubeProvider.from_config(
            cfg,
            quota_guard=effective_quota,
        )

    effective_cache: MetadataCache | None = None
    effective_provider: YouTubeProvider
    if enable_cache:
        effective_cache = cache or MetadataCache(effective_store, cfg.cache)
        effective_provider = CachedYouTubeProvider(
            upstream=base_provider,
            cache=effective_cache,
            quota_guard=effective_quota,
        )
    else:
        effective_provider = base_provider

    server = create_base_server()

    if register_tools:
        register_get_video_details(
            server,
            provider=effective_provider,
            quota_guard=effective_quota,
        )
        register_get_similar_videos(
            server,
            provider=effective_provider,
            quota_guard=effective_quota,
            similarity_config=cfg.similarity,
        )
        register_get_recommendations(
            server,
            provider=effective_provider,
            quota_guard=effective_quota,
            store=effective_store,
            profile_config=cfg.profile,
        )
        register_analyze_engagement(
            server,
            provider=effective_provider,
            quota_guard=effective_quota,
            store=effective_store,
            engagement_config=cfg.engagement,
        )
        register_draft_curated_playlist(
            server,
            provider=effective_provider,
            quota_guard=effective_quota,
            draft_store=effective_draft_store,
            app_config=cfg,
        )
        register_create_curated_playlist(
            server,
            provider=effective_provider,
            quota_guard=effective_quota,
            draft_store=effective_draft_store,
            confirmation_store=effective_confirm_store,
            token_store=effective_token_store,
            browser_opener=browser_opener,
            timeout_seconds=confirmation_timeout_seconds,
        )
        register_quota_status(
            server,
            guard=effective_quota,
            reset_timezone=cfg.quota.reset_timezone,
        )
        register_auth_status(
            server,
            token_store=effective_token_store,
        )

    return ServerRuntime(
        server=server,
        config=cfg,
        store=effective_store,
        quota_ledger=effective_quota,
        token_store=effective_token_store,
        draft_store=effective_draft_store,
        confirmation_store=effective_confirm_store,
        base_provider=base_provider,
        provider=effective_provider,
        cache=effective_cache,
    )


def create_server(
    config: AppConfig | None = None,
    *,
    register_tools: bool = True,
    provider: YouTubeProvider | None = None,
    store: SQLiteStore | None = None,
    quota_ledger: PersistentQuotaLedger | QuotaGuard | None = None,
    token_store: TokenStore | None = None,
    draft_store: DraftStore | None = None,
    confirmation_store: ConfirmationTokenStore | None = None,
    cache: MetadataCache | None = None,
    enable_cache: bool = True,
    browser_opener: Callable[[str], None] | None = None,
    confirmation_timeout_seconds: float = 120.0,
) -> MCPServer:
    """Build the yt-intel-mcp MCP server wired with provider, cache, quota, and tools."""
    runtime = build_server_runtime(
        config=config,
        provider=provider,
        store=store,
        quota_ledger=quota_ledger,
        token_store=token_store,
        draft_store=draft_store,
        confirmation_store=confirmation_store,
        cache=cache,
        enable_cache=enable_cache,
        register_tools=register_tools,
        browser_opener=browser_opener,
        confirmation_timeout_seconds=confirmation_timeout_seconds,
    )
    return runtime.server
