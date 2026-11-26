"""Integration tests for FixtureYouTubeProvider protocol, quota charging, and fault injection."""

# ruff: noqa: N802
from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from yt_intel_mcp.config import AppConfig, QuotaConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import CostEstimate, EventSource, EventTimeKind, QuotaUsed
from yt_intel_mcp.provider import (
    FixtureErrorRule,
    FixtureYouTubeProvider,
    YouTubeProvider,
)
from yt_intel_mcp.quota.guard import QuotaStatus

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


class _RecordingQuotaGuard:
    def __init__(self, quota_cfg: QuotaConfig | None = None) -> None:
        self.cfg = quota_cfg or QuotaConfig()
        self.charged: list[CostEstimate] = []
        self.units_used = 0
        self.search_calls_used = 0
        self.upstream_exhausted = False

    def estimate(self, operation: str, *, count: int = 1) -> CostEstimate:
        return CostEstimate(units=count, search_calls=0, operation=operation)

    def preflight(self, cost: CostEstimate) -> QuotaStatus:
        return self.status()

    def charge(self, cost: CostEstimate) -> QuotaStatus:
        self.charged.append(cost)
        self.units_used += cost.units
        self.search_calls_used += cost.search_calls
        return self.status()

    def mark_upstream_exhausted(self, reset_at: datetime | None = None) -> QuotaStatus:
        del reset_at
        self.upstream_exhausted = True
        return self.status()

    def status(self) -> QuotaStatus:
        return QuotaStatus(
            units_used=self.units_used,
            units_limit=self.cfg.daily_units_limit,
            units_remaining=self.cfg.daily_units_limit - self.units_used,
            search_calls_used=self.search_calls_used,
            search_calls_limit=self.cfg.daily_search_limit,
            search_calls_remaining=self.cfg.daily_search_limit - self.search_calls_used,
            reset_at=datetime(2026, 11, 27, 8, 0, tzinfo=UTC),
            upstream_exhausted=self.upstream_exhausted,
        )


def test_IT_PROV_fixture_implements_protocol_without_http_or_edit_delete() -> None:
    cfg = AppConfig(fixture_dir=FIXTURES_DIR)
    provider = FixtureYouTubeProvider.from_config(cfg)
    assert isinstance(provider, YouTubeProvider)

    members = set(dir(provider))
    assert not any(name.startswith(("update_playlist", "delete_playlist")) for name in members)

    fixture_path = ROOT / "src" / "yt_intel_mcp" / "provider" / "fixture.py"
    tree = ast.parse(fixture_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(FORBIDDEN_HTTP_IMPORTS)


@pytest.mark.anyio
async def test_IT_PROV_public_reads_cover_tags_unavail_live_handles_search_and_categories() -> None:
    provider = FixtureYouTubeProvider(FIXTURES_DIR)

    videos = await provider.get_videos(
        ["vid_seed_py01", "vid_notags02", "vid_priv0003", "vid_del00004", "vid_live0005", "missing"]
    )
    assert [v.video_id for v in videos] == [
        "vid_seed_py01",
        "vid_notags02",
        "vid_priv0003",
        "vid_del00004",
        "vid_live0005",
    ]
    assert videos[0].tags == ("python", "asyncio", "concurrency", "systems")
    assert videos[1].tags == ()
    assert videos[2].is_available is False and videos[2].privacy_status == "private"
    assert videos[3].is_available is False and videos[3].privacy_status == "deleted"
    assert videos[4].live_broadcast_content == "live" and videos[4].duration_seconds == 0

    ch = await provider.get_channel_by_handle("@SystemsCraft")
    assert ch is not None and ch.channel_id == "UC_PUB_TECH_001"
    assert await provider.get_channel_by_handle("nonexistent_handle") is None
    assert await provider.get_channel_by_handle("") is None

    channels = await provider.get_channels(["UC_PUB_TECH_001", "UC_PUB_TECH_002", "UC_MISSING"])
    assert [c.channel_id for c in channels] == ["UC_PUB_TECH_001", "UC_PUB_TECH_002"]

    short_hits = await provider.search_videos("python asyncio", video_duration="short")
    assert [h.item_id for h in short_hits] == ["vid_short006"]

    es_hits = await provider.search_videos("python asyncio", relevance_language="es")
    assert [h.item_id for h in es_hits] == ["vid_es_lang9"]

    fallback_hits = await provider.search_videos("raft consensus", video_duration="long")
    assert [h.item_id for h in fallback_hits] == ["vid_long1208"]

    paged_hits = await provider.search_videos("python asyncio", max_results=2, page_token="1")
    assert [h.item_id for h in paged_hits] == ["vid_notags02", "vid_med_2407"]

    ch_hits = await provider.search_channels("systems python", max_results=2)
    assert [h.item_id for h in ch_hits] == ["UC_PUB_TECH_001", "UC_PUB_TECH_002"]

    ch_fallback = await provider.search_channels("fermentation", relevance_language="en")
    assert [h.item_id for h in ch_fallback] == ["UC_PUB_COOK_005"]

    us_cats = await provider.get_video_categories(region_code="US")
    assert us_cats["28"] == "Science & Technology"
    fallback_cats = await provider.get_video_categories(region_code="DE")
    assert fallback_cats == us_cats


@pytest.mark.anyio
async def test_IT_PROV_synthetic_user_library_dated_and_undated_events() -> None:
    provider = FixtureYouTubeProvider(FIXTURES_DIR, persona="default_user")

    my_channel = await provider.get_my_channel()
    assert my_channel.channel_id == "UC_SYNTH_USER_001"

    subs = await provider.list_subscriptions_mine()
    assert len(subs) == 3
    assert all(ev.source is EventSource.SUBSCRIPTION for ev in subs)
    assert all(ev.time_kind is EventTimeKind.DATED and ev.event_time is not None for ev in subs)

    playlists = await provider.list_playlists_mine()
    assert [p.playlist_id for p in playlists] == ["LL_SYNTH_USER_001", "PL_SYNTH_STUDY_001"]

    likes_items = await provider.list_playlist_items("LL_SYNTH_USER_001")
    assert len(likes_items) == 3
    assert all(
        ev.source is EventSource.LIKED_VIDEO and ev.event_time is not None for ev in likes_items
    )

    study_items = await provider.list_playlist_items("PL_SYNTH_STUDY_001")
    assert len(study_items) == 3
    assert all(ev.source is EventSource.PLAYLIST_ITEM for ev in study_items)

    uploads = await provider.list_playlist_items("UU_PUB_TECH_002")
    assert [ev.video_id for ev in uploads] == ["vid_notags02", "vid_med_2407", "vid_inj_0011"]

    rated_likes = await provider.list_liked_videos_rated()
    assert [v.video_id for v in rated_likes] == ["vid_unk_au10", "vid_bake_012"]


@pytest.mark.anyio
async def test_IT_PROV_charges_quota_guard_on_reads_writes_and_injected_failures() -> None:
    guard = _RecordingQuotaGuard()
    provider = FixtureYouTubeProvider(
        FIXTURES_DIR,
        quota_guard=guard,
        error_rules={
            "get_channel_by_handle": FixtureErrorRule(reason="rateLimitExceeded", http_status=429),
            "search_channels": FixtureErrorRule(reason="quotaExceeded", http_status=403),
        },
    )

    await provider.get_videos(["vid_seed_py01"])
    await provider.search_videos("python asyncio", max_results=3)
    created = await provider.insert_playlist(title="Async Focus", privacy_status="private")
    item_id = await provider.insert_playlist_item(
        playlist_id=created.playlist_id, video_id="vid_seed_py01", position=0
    )
    assert item_id == "PLI_FIXTURE_0001"
    assert guard.units_used == 101
    assert guard.search_calls_used == 1

    with pytest.raises(ToolError) as rate_err:
        await provider.get_channel_by_handle("@systemscraft")
    assert rate_err.value.code is ErrorCode.RATE_LIMITED
    assert guard.units_used == 102

    with pytest.raises(ToolError) as quota_err:
        await provider.search_channels("systems")
    assert quota_err.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    assert guard.upstream_exhausted is True
    assert guard.search_calls_used == 2
    assert provider.total_quota_used == QuotaUsed(units=102, search_calls=2)


@pytest.mark.anyio
async def test_IT_PROV_error_injection_no_channel_and_simulated_insert_failures() -> None:
    no_channel = FixtureYouTubeProvider(FIXTURES_DIR, persona="no_channel_user")
    with pytest.raises(ToolError) as ch_err:
        await no_channel.get_my_channel()
    assert ch_err.value.code is ErrorCode.CHANNEL_REQUIRED

    with pytest.raises(ToolError) as write_ch_err:
        await no_channel.insert_playlist(title="Blocked")
    assert write_ch_err.value.code is ErrorCode.CHANNEL_REQUIRED

    # Read tools continue working for no-channel persona (FR-7.3).
    assert len(await no_channel.list_liked_videos_rated()) == 1

    # Simulated transient error followed by recovery, plus partial insert failure sequence.
    provider = FixtureYouTubeProvider(
        FIXTURES_DIR,
        error_rules={
            "get_videos": FixtureErrorRule(
                reason="rateLimitExceeded", http_status=429, remaining_triggers=1
            )
        },
        insert_failures={
            "vid_priv0003": FixtureErrorRule(reason="videoPrivate", http_status=403),
            "pos:1": FixtureErrorRule(reason="insufficientPermissions", http_status=403),
        },
    )
    with pytest.raises(ToolError) as transient_err:
        await provider.get_videos(["vid_seed_py01"])
    assert transient_err.value.code is ErrorCode.RATE_LIMITED
    recovered = await provider.get_videos(["vid_seed_py01"])
    assert len(recovered) == 1

    created = await provider.insert_playlist(title="Partial Demo")
    await provider.insert_playlist_item(
        playlist_id=created.playlist_id, video_id="vid_seed_py01", position=0
    )
    with pytest.raises(ToolError) as priv_err:
        await provider.insert_playlist_item(
            playlist_id=created.playlist_id, video_id="vid_priv0003", position=1
        )
    assert priv_err.value.code is ErrorCode.VIDEO_UNAVAILABLE

    with pytest.raises(ToolError) as scope_err:
        await provider.insert_playlist_item(
            playlist_id=created.playlist_id, video_id="vid_notags02", position=1
        )
    assert scope_err.value.code is ErrorCode.SCOPE_INSUFFICIENT

    provider.clear_errors()
    provider.set_video_availability("vid_seed_py01", is_available=False, privacy_status="private")
    stale = await provider.get_videos(["vid_seed_py01"])
    assert stale[0].is_available is False and stale[0].privacy_status == "private"


@pytest.mark.anyio
async def test_IT_PROV_validation_and_missing_fixture_errors(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        FixtureYouTubeProvider(tmp_path / "does_not_exist")

    provider = FixtureYouTubeProvider(FIXTURES_DIR)
    with pytest.raises(ToolError) as batch_err:
        await provider.get_videos([f"vid_{i:04d}" for i in range(51)])
    assert batch_err.value.code is ErrorCode.INVALID_ARGUMENT

    with pytest.raises(ToolError) as ch_batch_err:
        await provider.get_channels([f"UC_{i:04d}" for i in range(51)])
    assert ch_batch_err.value.code is ErrorCode.INVALID_ARGUMENT

    with pytest.raises(ToolError) as page_err:
        await provider.search_videos("python", page_token="not_an_int")
    assert page_err.value.code is ErrorCode.INVALID_ARGUMENT
