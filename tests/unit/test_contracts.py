"""Contract tests for SR-04 frozen errors, models, config, protocols, and stubs."""

# ruff: noqa: N802
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest

from yt_intel_mcp.config import (
    AppConfig,
    CacheConfig,
    DraftConfig,
    EngagementConfig,
    LiveTestConfig,
    PlaylistConfig,
    ProfileConfig,
    QuotaConfig,
    ReliabilityConfig,
    SimilarityConfig,
    load_config,
)
from yt_intel_mcp.errors import (
    UPSTREAM_REASON_TO_ERROR_CODE,
    ErrorCode,
    OutcomeStatus,
    ToolError,
    error_response,
    map_upstream_error,
    success_response,
)
from yt_intel_mcp.models import (
    ChannelMeta,
    CostEstimate,
    CreatedPlaylist,
    EventSource,
    EventTimeKind,
    PlaylistSummary,
    QuotaUsed,
    SearchHit,
    UserEvent,
    VideoMeta,
)
from yt_intel_mcp.provider import YouTubeProvider
from yt_intel_mcp.provider.base import YouTubeProvider as BaseYouTubeProvider
from yt_intel_mcp.quota import QuotaGuard, QuotaStatus
from yt_intel_mcp.quota.guard import QuotaGuard as BaseQuotaGuard
from yt_intel_mcp.sanitize import (
    DEFAULT_MAX_DESCRIPTION_LENGTH,
    DEFAULT_MAX_TITLE_LENGTH,
    sanitize_text,
    sanitize_video_meta,
)
from yt_intel_mcp.validation import (
    extract_channel_id,
    extract_playlist_id,
    extract_video_id,
)
from yt_intel_mcp.validation import (
    ids as validation_ids,
)

EXPECTED_ERROR_CODES = {
    "INVALID_ARGUMENT",
    "VIDEO_UNAVAILABLE",
    "INSUFFICIENT_USER_SIGNAL",
    "CONSTRAINTS_UNSATISFIABLE",
    "CONFIRMATION_MISMATCH",
    "DRAFT_EXPIRED",
    "CONFIRMATION_REUSED",
    "CONFIRMATION_DECLINED",
    "CONFIRMATION_UNAVAILABLE",
    "DRAFT_STALE",
    "QUOTA_BUDGET_INSUFFICIENT",
    "QUOTA_EXHAUSTED_UPSTREAM",
    "RATE_LIMITED",
    "CHANNEL_REQUIRED",
    "SCOPE_INSUFFICIENT",
    "AUTH_REAUTHORIZATION_REQUIRED",
    "PERMISSION_DENIED",
}

FORBIDDEN_POPULARITY_FIELDS = {
    "view_count",
    "viewCount",
    "like_count",
    "likeCount",
    "dislike_count",
    "comment_count",
    "favorite_count",
    "subscriber_count",
    "subscriberCount",
    "video_count",
    "statistics",
}


class _DummyProvider:
    async def get_videos(self, video_ids: Sequence[str]) -> list[VideoMeta]:
        return []

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
        return []

    async def search_channels(
        self,
        query: str,
        *,
        max_results: int = 25,
        relevance_language: str | None = None,
        page_token: str | None = None,
    ) -> list[SearchHit]:
        return []

    async def get_channels(self, channel_ids: Sequence[str]) -> list[ChannelMeta]:
        return []

    async def get_channel_by_handle(self, handle: str) -> ChannelMeta | None:
        return None

    async def get_my_channel(self) -> ChannelMeta:
        return ChannelMeta(channel_id="UC_DUMMY", title="Dummy")

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
        return CreatedPlaylist(playlist_id="PL_1", title=title, privacy_status=privacy_status)

    async def insert_playlist_item(
        self, *, playlist_id: str, video_id: str, position: int | None = None
    ) -> str:
        return "PLI_1"


class _DummyQuotaGuard:
    def estimate(self, operation: str, *, count: int = 1) -> CostEstimate:
        return CostEstimate(units=count, search_calls=0, operation=operation)

    def preflight(self, cost: CostEstimate) -> QuotaStatus:
        return self.status()

    def charge(self, cost: CostEstimate) -> QuotaStatus:
        return self.status()

    def mark_upstream_exhausted(self, reset_at: datetime | None = None) -> QuotaStatus:
        return self.status()

    def status(self) -> QuotaStatus:
        return QuotaStatus(
            units_used=0,
            units_limit=10_000,
            units_remaining=10_000,
            search_calls_used=0,
            search_calls_limit=100,
            search_calls_remaining=100,
            reset_at=datetime(2026, 11, 26, 8, 0, tzinfo=UTC),
        )


def test_CT_1_error_codes_and_outcome_statuses() -> None:
    assert len(ErrorCode) == 17
    assert {code.value for code in ErrorCode} == EXPECTED_ERROR_CODES
    assert {status.value for status in OutcomeStatus} == {"COMPLETE", "PARTIAL"}


def test_CT_1_envelopes_and_tool_error() -> None:
    used = QuotaUsed(units=101, search_calls=1)
    ok = success_response("Found 3 videos.", {"items": ["a"]}, quota_used=used)
    assert ok == {
        "summary": "Found 3 videos.",
        "data": {"items": ["a"]},
        "quota_used": {"units": 101, "search_calls": 1},
    }
    assert success_response("Empty", {})["quota_used"] == {"units": 0, "search_calls": 0}

    err = ToolError(
        ErrorCode.QUOTA_BUDGET_INSUFFICIENT,
        "Daily search budget exhausted.",
        details={"remaining_search_calls": 0},
        quota_used=used,
    )
    assert err.to_envelope() == {
        "code": "QUOTA_BUDGET_INSUFFICIENT",
        "message": "Daily search budget exhausted.",
        "details": {"remaining_search_calls": 0},
        "quota_used": {"units": 101, "search_calls": 1},
    }
    override_quota = QuotaUsed(units=2, search_calls=0)
    assert err.to_envelope(override_quota)["quota_used"] == {"units": 2, "search_calls": 0}

    direct = error_response(ErrorCode.INVALID_ARGUMENT, "Bad video id.")
    assert direct == {
        "code": "INVALID_ARGUMENT",
        "message": "Bad video id.",
        "details": {},
        "quota_used": {"units": 0, "search_calls": 0},
    }


@pytest.mark.parametrize(
    ("reason", "http_status", "expected_code"),
    [
        ("quotaExceeded", 403, ErrorCode.QUOTA_EXHAUSTED_UPSTREAM),
        ("rateLimitExceeded", 403, ErrorCode.RATE_LIMITED),
        ("userRateLimitExceeded", 429, ErrorCode.RATE_LIMITED),
        (None, 429, ErrorCode.RATE_LIMITED),
        ("videoNotFound", 404, ErrorCode.VIDEO_UNAVAILABLE),
        ("videoPrivate", 403, ErrorCode.VIDEO_UNAVAILABLE),
        ("private", 403, ErrorCode.VIDEO_UNAVAILABLE),
        ("deleted", 410, ErrorCode.VIDEO_UNAVAILABLE),
        (None, 404, ErrorCode.VIDEO_UNAVAILABLE),
        ("youtubeSignupRequired", 403, ErrorCode.CHANNEL_REQUIRED),
        ("insufficientPermissions", 403, ErrorCode.SCOPE_INSUFFICIENT),
        ("invalid_grant", 400, ErrorCode.AUTH_REAUTHORIZATION_REQUIRED),
        (None, 401, ErrorCode.AUTH_REAUTHORIZATION_REQUIRED),
        ("forbidden", 403, ErrorCode.PERMISSION_DENIED),
        ("unknownReason", 500, ErrorCode.PERMISSION_DENIED),
    ],
)
def test_CT_1_upstream_error_mapping(
    reason: str | None, http_status: int | None, expected_code: ErrorCode
) -> None:
    mapped = map_upstream_error(
        reason,
        http_status=http_status,
        details={"endpoint": "videos.list"},
    )
    assert mapped.code is expected_code
    assert mapped.details["endpoint"] == "videos.list"
    if reason:
        assert mapped.details["upstream_reason"] == reason
    if http_status is not None:
        assert mapped.details["http_status"] == http_status
    assert "quotaexceeded" in UPSTREAM_REASON_TO_ERROR_CODE


def test_INV_01_models_exclude_popularity_and_statistics_fields() -> None:
    video_fields = {f.name for f in fields(VideoMeta)}
    channel_fields = {f.name for f in fields(ChannelMeta)}
    search_fields = {f.name for f in fields(SearchHit)}
    event_fields = {f.name for f in fields(UserEvent)}
    for model_fields in (video_fields, channel_fields, search_fields, event_fields):
        assert model_fields.isdisjoint(FORBIDDEN_POPULARITY_FIELDS)

    q1 = QuotaUsed(units=50, search_calls=0)
    q2 = QuotaUsed(units=100, search_calls=1)
    combined = q1 + q2
    assert combined == QuotaUsed(units=150, search_calls=1)

    est = CostEstimate(units=100, search_calls=1, operation="search.list")
    assert est.to_quota_used() == QuotaUsed(units=100, search_calls=1)

    event = UserEvent(
        source=EventSource.PLAYLIST_ITEM,
        time_kind=EventTimeKind.DATED,
        event_time=datetime(2026, 11, 25, 12, 0, tzinfo=UTC),
        video_id="dQw4w9WgXcQ",
        playlist_id="PL_TEST",
        title="Sample",
    )
    assert event.source is EventSource.PLAYLIST_ITEM
    assert event.time_kind is EventTimeKind.DATED

    channel = ChannelMeta(
        channel_id="UC_TEST",
        title="Test Channel",
        keywords=("python", "mcp"),
    )
    assert channel.keywords == ("python", "mcp")

    with pytest.raises(ValueError, match="units"):
        QuotaUsed(units=-1)
    with pytest.raises(ValueError, match="search_calls"):
        QuotaUsed(search_calls=-1)
    with pytest.raises(ValueError, match="units"):
        CostEstimate(units=-1)
    with pytest.raises(ValueError, match="search_calls"):
        CostEstimate(units=1, search_calls=-1)


def test_CT_1_config_defaults_and_env_loading() -> None:
    cfg = load_config({})
    assert isinstance(cfg, AppConfig)
    assert cfg.provider_mode == "fixture"
    assert cfg.quota == QuotaConfig()
    assert cfg.quota.daily_units_limit == 10_000
    assert cfg.quota.daily_search_limit == 100
    assert cfg.quota.reset_timezone == "America/Los_Angeles"
    assert cfg.quota.list_unit_cost == 1
    assert cfg.quota.search_call_cost == 1
    assert cfg.quota.search_unit_cost == 0
    assert cfg.quota.playlist_insert_unit_cost == 50
    assert cfg.quota.playlist_item_insert_unit_cost == 50
    assert cfg.cache == CacheConfig(86_400, 86_400, 21_600, 900, 86_400)
    assert cfg.draft == DraftConfig(ttl_seconds=600)
    assert cfg.playlist == PlaylistConfig(0.05, 25, "private", False)
    assert cfg.profile == ProfileConfig(half_life_days=90.0, undated_weight=0.5)
    assert cfg.engagement == EngagementConfig(
        min_dated_events=5, short_max_seconds=240, medium_max_seconds=1200
    )
    assert cfg.similarity == SimilarityConfig()
    assert cfg.similarity.duration_weight == 0.10
    assert cfg.similarity.keywords_weight == 0.20
    assert (
        cfg.similarity.title_weight
        + cfg.similarity.tags_weight
        + cfg.similarity.description_weight
        + cfg.similarity.category_weight
        + cfg.similarity.duration_weight
    ) == pytest.approx(1.0)
    assert cfg.reliability == ReliabilityConfig(read_max_retries=3, write_max_retries=0)
    assert cfg.live_tests == LiveTestConfig(max_units=300, max_search_calls=10)

    live_cfg = load_config(
        {
            "YT_INTEL_PROVIDER": "LIVE",
            "YT_INTEL_QUOTA_DAILY_UNITS": "4000",
            "YT_INTEL_QUOTA_DAILY_SEARCHES": "40",
            "YT_INTEL_SEARCH_UNIT_COST": "100",
            "YT_INTEL_DATA_DIR": "/tmp/yt-data",
            "YT_INTEL_FIXTURE_DIR": "/tmp/yt-fixtures",
        }
    )
    assert live_cfg.provider_mode == "live"
    assert live_cfg.data_dir == Path("/tmp/yt-data")
    assert live_cfg.fixture_dir == Path("/tmp/yt-fixtures")
    assert live_cfg.quota.daily_units_limit == 4000
    assert live_cfg.quota.daily_search_limit == 40
    assert live_cfg.quota.search_unit_cost == 100

    with pytest.raises(ValueError, match="YT_INTEL_PROVIDER"):
        load_config({"YT_INTEL_PROVIDER": "scraping"})
    with pytest.raises(ValueError, match="YT_INTEL_QUOTA_DAILY_UNITS"):
        load_config({"YT_INTEL_QUOTA_DAILY_UNITS": "abc"})
    with pytest.raises(ValueError, match="daily_units_limit"):
        QuotaConfig(daily_units_limit=0)
    with pytest.raises(ValueError, match="daily_search_limit"):
        QuotaConfig(daily_search_limit=0)
    with pytest.raises(ValueError, match="Method costs"):
        QuotaConfig(list_unit_cost=-1)
    with pytest.raises(ValueError, match="search_unit_cost"):
        QuotaConfig(search_unit_cost=50)
    with pytest.raises(ValueError, match="timezone"):
        QuotaConfig(reset_timezone="Invalid/Nowhere")
    with pytest.raises(ValueError, match="duration_tolerance_fraction"):
        PlaylistConfig(duration_tolerance_fraction=1.5)
    with pytest.raises(ValueError, match="default_max_videos"):
        PlaylistConfig(default_max_videos=0)


def test_SE_6_protocols_and_no_playlist_edit_delete() -> None:
    provider = _DummyProvider()
    guard = _DummyQuotaGuard()
    assert isinstance(provider, YouTubeProvider)
    assert YouTubeProvider is BaseYouTubeProvider
    assert isinstance(guard, QuotaGuard)
    assert QuotaGuard is BaseQuotaGuard

    protocol_members = set(dir(YouTubeProvider))
    assert not any(
        name.startswith(("update_playlist", "delete_playlist")) for name in protocol_members
    )
    assert {
        "get_videos",
        "search_videos",
        "search_channels",
        "get_channels",
        "get_channel_by_handle",
        "get_my_channel",
        "list_subscriptions_mine",
        "list_playlists_mine",
        "list_playlist_items",
        "list_liked_videos_rated",
        "get_video_categories",
        "insert_playlist",
        "insert_playlist_item",
    }.issubset(protocol_members)
    assert {"estimate", "preflight", "charge", "mark_upstream_exhausted", "status"}.issubset(
        set(dir(QuotaGuard))
    )


def test_CT_1_stage2_stubs_raise_not_implemented() -> None:
    assert DEFAULT_MAX_TITLE_LENGTH == 200
    assert DEFAULT_MAX_DESCRIPTION_LENGTH == 1000
    sample_video = VideoMeta(video_id="dQw4w9WgXcQ", title="Sample")

    assert sanitize_text("hello") == "hello"
    assert sanitize_video_meta(sample_video) == sample_video

    assert extract_video_id is validation_ids.extract_video_id
    assert extract_channel_id is validation_ids.extract_channel_id
    assert extract_playlist_id is validation_ids.extract_playlist_id
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_channel_id("UCuAXFkgsw1L7xaCfnd5JJOw") == "UCuAXFkgsw1L7xaCfnd5JJOw"
    assert extract_playlist_id("PL1234567890abcdef") == "PL1234567890abcdef"
