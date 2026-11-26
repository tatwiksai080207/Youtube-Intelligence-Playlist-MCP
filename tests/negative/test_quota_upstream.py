"""Negative tests for upstream quotaExceeded exhaustion and PT reset (NT_QUOTA, FR-6.3)."""

# ruff: noqa: N802
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest

from yt_intel_mcp.cache import CachedYouTubeProvider, MetadataCache
from yt_intel_mcp.config import CacheConfig, QuotaConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import (
    ChannelMeta,
    CreatedPlaylist,
    PlaylistSummary,
    SearchHit,
    UserEvent,
    VideoMeta,
)
from yt_intel_mcp.provider import FixtureErrorRule, FixtureYouTubeProvider
from yt_intel_mcp.quota import PersistentQuotaLedger
from yt_intel_mcp.store import SQLiteStore

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


class _StubQuotaExceededProvider:
    """Minimal provider stub simulating LiveYouTubeProvider throwing quotaExceeded."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_with_quota = True

    async def get_videos(self, video_ids: Sequence[str]) -> list[VideoMeta]:
        self.calls.append("videos.list")
        if self.fail_with_quota:
            raise ToolError(
                ErrorCode.QUOTA_EXHAUSTED_UPSTREAM,
                "The request cannot be completed because you have exceeded your quota.",
                details={"upstream_reason": "quotaExceeded", "http_status": 403},
            )
        return [VideoMeta(video_id=vid, title=f"Recovered {vid}") for vid in video_ids]

    async def search_videos(
        self,
        query: str,
        *,
        max_results: int = 25,
        video_duration: Literal["any", "short", "medium", "long"] | None = None,
        relevance_language: str | None = None,
        region_code: str | None = None,
        page_token: str | None = None,
    ) -> list[SearchHit]:
        self.calls.append("search.list:videos")
        return []

    async def search_channels(
        self,
        query: str,
        *,
        max_results: int = 25,
        relevance_language: str | None = None,
        page_token: str | None = None,
    ) -> list[SearchHit]:
        self.calls.append("search.list:channels")
        return []

    async def get_channels(self, channel_ids: Sequence[str]) -> list[ChannelMeta]:
        return []

    async def get_channel_by_handle(self, handle: str) -> ChannelMeta | None:
        return None

    async def get_my_channel(self) -> ChannelMeta:
        return ChannelMeta(channel_id="UC_SYNTH", title="Synth")

    async def list_subscriptions_mine(self, *, max_results: int = 50) -> list[UserEvent]:
        return []

    async def list_playlists_mine(self, *, max_results: int = 50) -> list[PlaylistSummary]:
        return []

    async def list_playlist_items(
        self, playlist_id: str, *, max_results: int = 50
    ) -> list[UserEvent]:
        return []

    async def list_liked_videos_rated(self, *, max_results: int = 50) -> list[VideoMeta]:
        return []

    async def get_video_categories(self, *, region_code: str = "US") -> dict[str, str]:
        return {}

    async def insert_playlist(
        self,
        *,
        title: str,
        description: str = "",
        privacy_status: Literal["private", "unlisted", "public"] = "private",
    ) -> CreatedPlaylist:
        self.calls.append("playlists.insert")
        raise AssertionError("insert_playlist must not be called when exhausted")

    async def insert_playlist_item(
        self,
        *,
        playlist_id: str,
        video_id: str,
        position: int | None = None,
    ) -> str:
        raise AssertionError("insert_playlist_item must not be called when exhausted")


@pytest.mark.anyio
async def test_NT_QUOTA_upstream_quota_exceeded_blocks_misses_until_pt_reset(
    tmp_path: Path,
) -> None:
    current = datetime(2026, 11, 26, 19, 0, tzinfo=UTC)  # 11:00 PT on 2026-11-26
    db_path = tmp_path / "quota_exhausted.db"
    store = SQLiteStore(db_path)
    ledger = PersistentQuotaLedger(store, QuotaConfig(), clock=lambda: current)
    cache = MetadataCache(store, CacheConfig(), clock=lambda: current)
    upstream = FixtureYouTubeProvider(
        FIXTURES_DIR,
        quota_guard=ledger,
        error_rules={"videos.list": FixtureErrorRule(reason="quotaExceeded", http_status=403)},
    )
    provider = CachedYouTubeProvider(upstream, cache, quota_guard=ledger)

    # First uncached call hits upstream and triggers quotaExceeded -> persists exhausted state.
    with pytest.raises(ToolError) as first_err:
        await provider.get_videos(["vid_seed_py01"])
    assert first_err.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    assert len(upstream.calls) == 1

    # Subsequent uncached reads and writes are rejected before ANY upstream call occurs.
    for coro in (
        provider.search_videos("python"),
        provider.get_channels(["UC_PUB_TECH_001"]),
        provider.list_playlists_mine(),
        provider.insert_playlist(title="Blocked Playlist", privacy_status="private"),
    ):
        with pytest.raises(ToolError) as blocked_err:
            await coro
        assert blocked_err.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    assert len(upstream.calls) == 1

    # Persisted across process restarts prior to 00:00 PT reset (2026-11-27T07:59:59Z).
    current = datetime(2026, 11, 27, 7, 59, 59, tzinfo=UTC)
    restarted_store = SQLiteStore(db_path)
    restarted_ledger = PersistentQuotaLedger(restarted_store, QuotaConfig(), clock=lambda: current)
    restarted_provider = CachedYouTubeProvider(
        FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=restarted_ledger),
        MetadataCache(restarted_store, CacheConfig(), clock=lambda: current),
        quota_guard=restarted_ledger,
    )
    with pytest.raises(ToolError) as still_blocked:
        await restarted_provider.get_videos(["vid_seed_py01"])
    assert still_blocked.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    assert restarted_ledger.status().upstream_exhausted is True

    # At 00:00 Pacific Time (2026-11-27T08:00:00Z), exhaustion clears automatically.
    current = datetime(2026, 11, 27, 8, 0, 0, tzinfo=UTC)
    recovered = await restarted_provider.get_videos(["vid_seed_py01"])
    assert len(recovered) == 1
    assert restarted_ledger.status().upstream_exhausted is False


@pytest.mark.anyio
async def test_NT_QUOTA_cached_reads_continue_while_uncached_calls_stay_blocked(
    tmp_path: Path,
) -> None:
    current = datetime(2026, 11, 26, 20, 0, tzinfo=UTC)
    store = SQLiteStore(tmp_path / "cached_hit_during_exhaustion.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig(), clock=lambda: current)
    cache = MetadataCache(store, CacheConfig(), clock=lambda: current)
    upstream = FixtureYouTubeProvider(
        FIXTURES_DIR,
        quota_guard=ledger,
        error_rules={"search.list": FixtureErrorRule(reason="quotaExceeded", http_status=403)},
    )
    provider = CachedYouTubeProvider(upstream, cache, quota_guard=ledger)

    seeded = await provider.get_videos(["vid_seed_py01"])
    assert len(seeded) == 1

    with pytest.raises(ToolError) as err:
        await provider.search_videos("python")
    assert err.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM

    calls_before = len(upstream.calls)
    # Already cached item is served locally without touching upstream API.
    cached_again = await provider.get_videos(["vid_seed_py01"])
    assert cached_again == seeded
    assert len(upstream.calls) == calls_before

    # Uncached miss remains blocked.
    with pytest.raises(ToolError) as miss_err:
        await provider.get_videos(["vid_notags02"])
    assert miss_err.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    assert len(upstream.calls) == calls_before


@pytest.mark.anyio
async def test_NT_QUOTA_wrapper_marks_exhaustion_and_charges_failure_for_raw_provider(
    tmp_path: Path,
) -> None:
    current = datetime(2026, 11, 26, 21, 0, tzinfo=UTC)
    store = SQLiteStore(tmp_path / "raw_stub.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig(), clock=lambda: current)
    cache = MetadataCache(store, CacheConfig(), clock=lambda: current)
    stub = _StubQuotaExceededProvider()
    provider = CachedYouTubeProvider(
        stub,
        cache,
        quota_guard=ledger,
        charge_on_miss=True,
    )

    with pytest.raises(ToolError) as err:
        await provider.get_videos(["vid_seed_py01"])
    assert err.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    assert ledger.status().units_used == 1
    assert ledger.status().upstream_exhausted is True
    assert stub.calls == ["videos.list"]

    # Second uncached miss is stopped in preflight -> zero calls to stub.
    with pytest.raises(ToolError) as err2:
        await provider.search_videos("python")
    assert err2.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    assert stub.calls == ["videos.list"]

    # After PT midnight reset, stub succeeds cleanly and charges 1 unit.
    current = datetime(2026, 11, 27, 8, 0, 0, tzinfo=UTC)
    stub.fail_with_quota = False
    recovered = await provider.get_videos(["vid_seed_py01"])
    assert recovered[0].title == "Recovered vid_seed_py01"
    assert ledger.status().units_used == 1
