"""Integration tests for TTL MetadataCache and CachedYouTubeProvider (IT_CACHE, NFR-1, NFR-7)."""

# ruff: noqa: N802
from __future__ import annotations

import ast
import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from yt_intel_mcp.cache import CachedYouTubeProvider, MetadataCache, make_cache_key
from yt_intel_mcp.config import CacheConfig, QuotaConfig
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.provider import FixtureYouTubeProvider, YouTubeProvider
from yt_intel_mcp.quota import PersistentQuotaLedger
from yt_intel_mcp.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "tests" / "fixtures"
FORBIDDEN_HTTP_IMPORTS = {
    "httpx",
    "httpx2",
    "httpcore",
    "httpcore2",
    "requests",
    "aiohttp",
    "google",
}


def test_IT_CACHE_protocol_conformance_and_import_isolation(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "cache.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig())
    upstream = FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=ledger)
    cached = CachedYouTubeProvider(upstream, MetadataCache(store), quota_guard=ledger)
    assert isinstance(cached, YouTubeProvider)

    cache_path = ROOT / "src" / "yt_intel_mcp" / "cache.py"
    tree = ast.parse(cache_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(FORBIDDEN_HTTP_IMPORTS)


@pytest.mark.anyio
async def test_IT_CACHE_ttls_zero_quota_hits_and_partial_batch_resolution(tmp_path: Path) -> None:
    # Start right at 00:00 PST (2026-11-26T08:00:00Z) so 86,399s remains inside the same PT day.
    current = datetime(2026, 11, 26, 8, 0, tzinfo=UTC)
    store = SQLiteStore(tmp_path / "cache_ttl.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig(), clock=lambda: current)
    cache = MetadataCache(store, CacheConfig(), clock=lambda: current)
    upstream = FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=ledger)
    provider = CachedYouTubeProvider(upstream, cache, quota_guard=ledger)

    # 1. Videos (24h = 86400s): partial batch resolves cached subset + fetches only missing IDs.
    first_videos = await provider.get_videos(["vid_seed_py01"])
    assert len(first_videos) == 1
    assert ledger.status().units_used == 1
    assert upstream.total_quota_used.units == 1
    assert len(upstream.calls) == 1

    # Hit at 23h59m59s consumes zero units and makes zero upstream calls.
    current = datetime(2026, 11, 26, 8, 0, tzinfo=UTC) + timedelta(seconds=86_399)
    cached_hit = await provider.get_videos(["vid_seed_py01"])
    assert cached_hit == first_videos
    assert ledger.status().units_used == 1
    assert upstream.total_quota_used.units == 1
    assert len(upstream.calls) == 1
    assert provider.stats.hits == 1

    # Mixed batch fetches only uncached vid_notags02 and preserves requested order.
    both_videos = await provider.get_videos(["vid_notags02", "vid_seed_py01"])
    assert [v.video_id for v in both_videos] == ["vid_notags02", "vid_seed_py01"]
    assert ledger.status().units_used == 2
    assert len(upstream.calls) == 2

    # Expired exactly at 86400s: re-fetches from upstream.
    current = datetime(2026, 11, 26, 8, 0, tzinfo=UTC) + timedelta(seconds=86_400)
    refreshed = await provider.get_videos(["vid_seed_py01"])
    assert len(refreshed) == 1
    assert len(upstream.calls) == 3

    # Uncached read helper bypasses cache intentionally (for FR-5.5 stale checks).
    uncached = await provider.get_videos_uncached(["vid_seed_py01"])
    assert len(uncached) == 1
    assert len(upstream.calls) == 4

    # 2. Channels, handles, and categories (24h TTL).
    ch = await provider.get_channels(["UC_PUB_TECH_001"])
    assert len(ch) == 1
    units_before_hits = ledger.status().units_used
    assert await provider.get_channels(["UC_PUB_TECH_001"]) == ch
    by_handle = await provider.get_channel_by_handle("@SystemsCraft")
    assert by_handle is not None
    assert await provider.get_channel_by_handle("SystemsCraft") == by_handle
    cats = await provider.get_video_categories(region_code="US")
    assert "28" in cats
    assert await provider.get_video_categories(region_code="us") == cats
    # Only the handle miss + category miss charged (2 units total), cache hits charged 0.
    assert ledger.status().units_used == units_before_hits + 2

    # 3. Searches (6h = 21600s TTL): normalized whitespace hits cache cleanly, expires at 6h.
    search_t0 = current
    hits = await provider.search_videos("Python Asyncio")
    assert len(hits) >= 1
    assert ledger.status().search_calls_used == 1
    current = search_t0 + timedelta(seconds=21_599)
    assert await provider.search_videos("  python   asyncio ") == hits
    assert ledger.status().search_calls_used == 1
    current = search_t0 + timedelta(seconds=21_600)
    await provider.search_videos("python asyncio")
    assert ledger.status().search_calls_used == 2

    ch_hits = await provider.search_channels("systems")
    assert await provider.search_channels("  SYSTEMS ") == ch_hits
    assert ledger.status().search_calls_used == 3

    # 4. User lists (15m = 900s TTL) and playlist write invalidation.
    list_t0 = current
    my_ch = await provider.get_my_channel()
    subs = await provider.list_subscriptions_mine()
    playlists = await provider.list_playlists_mine()
    items = await provider.list_playlist_items("PL_SYNTH_STUDY_001")
    liked = await provider.list_liked_videos_rated()
    calls_after_user_reads = len(upstream.calls)

    current = list_t0 + timedelta(seconds=899)
    assert await provider.get_my_channel() == my_ch
    assert await provider.list_subscriptions_mine() == subs
    assert await provider.list_playlists_mine() == playlists
    assert await provider.list_playlist_items("PL_SYNTH_STUDY_001") == items
    assert await provider.list_liked_videos_rated() == liked
    assert len(upstream.calls) == calls_after_user_reads

    # insert_playlist invalidates playlists_mine cache; expired 900s re-fetches subscriptions.
    await provider.insert_playlist(title="Cached Test Playlist", privacy_status="private")
    current = list_t0 + timedelta(seconds=900)
    await provider.list_subscriptions_mine()
    await provider.list_playlists_mine()
    assert len(upstream.calls) == calls_after_user_reads + 3


@pytest.mark.anyio
async def test_IT_CACHE_revoke_purge_deletes_user_lists_and_retains_public_and_quota(
    tmp_path: Path,
) -> None:
    current = datetime(2026, 11, 26, 15, 0, tzinfo=UTC)
    store = SQLiteStore(tmp_path / "purge.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig(), clock=lambda: current)
    cache = MetadataCache(store, CacheConfig(), clock=lambda: current)
    upstream = FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=ledger)
    provider = CachedYouTubeProvider(upstream, cache, quota_guard=ledger)

    await provider.get_videos(["vid_seed_py01"])
    await provider.get_channels(["UC_PUB_TECH_001"])
    await provider.search_videos("python")
    await provider.get_video_categories(region_code="US")
    await provider.get_my_channel()
    await provider.list_subscriptions_mine()
    await provider.list_playlists_mine()
    await provider.list_playlist_items("PL_SYNTH_STUDY_001")
    await provider.list_liked_videos_rated()

    quota_before = ledger.status()
    calls_before = len(upstream.calls)

    cache_deleted, _ = cache.purge_personal()
    assert cache_deleted == 5

    # Public entries remain cached (0 upstream calls) while personal lists require fresh fetch.
    await provider.get_videos(["vid_seed_py01"])
    await provider.get_channels(["UC_PUB_TECH_001"])
    await provider.search_videos("python")
    await provider.get_video_categories(region_code="US")
    assert len(upstream.calls) == calls_before

    # Quota ledger history is preserved across auth revoke (INV-19, ADR-0006).
    assert ledger.status().units_used == quota_before.units_used
    assert ledger.status().search_calls_used == quota_before.search_calls_used

    await provider.list_subscriptions_mine()
    assert len(upstream.calls) == calls_before + 1


def test_IT_CACHE_blocks_forbidden_statistics_and_secret_keys(tmp_path: Path) -> None:
    cache = MetadataCache(SQLiteStore(tmp_path / "guard.db"))
    with pytest.raises(ValueError, match="forbidden key"):
        cache.put("videos:item:bad1", "videos", {"video_id": "bad1", "statistics": {"views": 1}})
    with pytest.raises(ValueError, match="forbidden key"):
        cache.put("channels:item:bad2", "channels", [{"access_token": "secret"}])


@pytest.mark.anyio
async def test_IT_CACHE_cached_response_latency_within_500ms_nfr1(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "perf_cache.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig())
    cache = MetadataCache(store, CacheConfig())
    upstream = FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=ledger)
    provider = CachedYouTubeProvider(upstream, cache, quota_guard=ledger)

    # Pre-populate 50 deterministic VideoMeta records in SQLite WAL cache.
    sample_videos = [
        VideoMeta(
            video_id=f"vid_perf_{idx:03d}",
            title=f"Cached Educational Video {idx}",
            description="Deterministic cached metadata payload",
            channel_id="UC_PUB_TECH_001",
            channel_title="Systems Craft",
            duration_seconds=300 + idx,
            tags=("python", "cache", f"topic-{idx}"),
            default_audio_language="en",
        )
        for idx in range(50)
    ]
    from yt_intel_mcp.cache import _encode_video

    cache.put_many(
        [
            (make_cache_key("videos:item", v.video_id), "videos", _encode_video(v))
            for v in sample_videos
        ]
    )
    requested_ids = [v.video_id for v in sample_videos]

    # Follow docs/testing/test-plan.md Section 4 timing protocol: 1 warmup + 5 measured runs.
    warm = await provider.get_videos(requested_ids)
    assert len(warm) == 50

    durations_ms: list[float] = []
    for _ in range(5):
        start = time.perf_counter()
        hit = await provider.get_videos(requested_ids)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert len(hit) == 50
        durations_ms.append(elapsed_ms)

    assert upstream.calls == []
    assert ledger.status().units_used == 0
    assert statistics.median(durations_ms) <= 500.0
    assert max(durations_ms) <= 500.0


@pytest.mark.anyio
async def test_IT_CACHE_invalidation_sweep_and_write_passthrough(tmp_path: Path) -> None:
    current = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
    store = SQLiteStore(tmp_path / "sweep.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig(), clock=lambda: current)
    cache = MetadataCache(store, CacheConfig(), clock=lambda: current)
    upstream = FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=ledger)
    provider = CachedYouTubeProvider(upstream, cache, quota_guard=ledger)

    cache.put("custom:a", "user_lists", {"ok": True})
    cache.put("custom:b", "videos", {"ok": True})
    assert cache.invalidate("custom:a") is True
    assert cache.invalidate("custom:a") is False
    assert cache.get("custom:a") is None

    current = datetime(2026, 11, 26, 12, 0, tzinfo=UTC) + timedelta(seconds=86_400)
    assert cache.sweep_expired() == 1
    assert cache.get("custom:b") is None

    created = await provider.insert_playlist(title="Direct Pass", privacy_status="private")
    item_id = await provider.insert_playlist_item(
        playlist_id=created.playlist_id,
        video_id="vid_seed_py01",
        position=0,
    )
    assert item_id
    assert len(upstream.inserted_items) == 1

    from yt_intel_mcp.errors import ErrorCode, ToolError

    with pytest.raises(ToolError) as too_many:
        await provider.get_videos([f"vid_{i:06d}" for i in range(51)])
    assert too_many.value.code is ErrorCode.INVALID_ARGUMENT
