"""Integration tests for LiveYouTubeProvider protocol, retries, and quota (IT_PROV)."""

# ruff: noqa: N802
from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from yt_intel_mcp.config import AppConfig, QuotaConfig, ReliabilityConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import CostEstimate, EventSource
from yt_intel_mcp.provider import (
    LiveYouTubeProvider,
    UrllibLiveHttpTransport,
    YouTubeProvider,
)
from yt_intel_mcp.quota.guard import QuotaStatus


class _RecordingQuotaGuard:
    def __init__(self, quota_cfg: QuotaConfig | None = None) -> None:
        self.cfg = quota_cfg or QuotaConfig()
        self.preflighted: list[CostEstimate] = []
        self.charged: list[CostEstimate] = []
        self.units_used = 0
        self.search_calls_used = 0
        self.upstream_exhausted = False

    def estimate(self, operation: str, *, count: int = 1) -> CostEstimate:
        if operation == "search.list":
            return CostEstimate(
                units=self.cfg.search_unit_cost,
                search_calls=self.cfg.search_call_cost,
                operation=operation,
            )
        if operation in ("playlists.insert", "playlistItems.insert"):
            return CostEstimate(
                units=self.cfg.playlist_insert_unit_cost, search_calls=0, operation=operation
            )
        return CostEstimate(
            units=self.cfg.list_unit_cost * count, search_calls=0, operation=operation
        )

    def preflight(self, cost: CostEstimate) -> QuotaStatus:
        self.preflighted.append(cost)
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
            reset_at=datetime(2026, 11, 28, 8, 0, tzinfo=UTC),
            upstream_exhausted=self.upstream_exhausted,
        )


class _MockLiveTransport:
    """Mock live transport for injecting responses, latency simulation, and retry tracking."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.responses_queue: list[tuple[int, dict[str, str], dict[str, Any]]] = []
        self.default_response: tuple[int, dict[str, str], dict[str, Any]] = (200, {}, {"items": []})

    def queue_response(
        self,
        status_code: int,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        self.responses_queue.append((status_code, headers or {}, body))

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, Mapping[str, str], dict[str, Any]]:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "params": dict(params or {}),
                "json_body": dict(json_body or {}),
            }
        )
        if self.responses_queue:
            return self.responses_queue.pop(0)
        return self.default_response


def test_IT_PROV_live_implements_protocol_without_edit_delete() -> None:
    """LiveYouTubeProvider implements YouTubeProvider without edit or delete methods (SRS §1.2)."""
    provider = LiveYouTubeProvider(access_token="test_tok")
    assert isinstance(provider, YouTubeProvider)

    members = set(dir(provider))
    assert not any(name.startswith(("update_playlist", "delete_playlist")) for name in members)


@pytest.mark.anyio
async def test_IT_PROV_live_provider_never_requests_statistics() -> None:
    """Live provider strictly rejects statistics part requests (INV-01, FR-1.3, FR-2.2)."""
    transport = _MockLiveTransport()
    provider = LiveYouTubeProvider(http_transport=transport)

    with pytest.raises(ValueError, match="Forbidden part 'statistics' requested"):
        await provider._execute_with_retry(
            "GET",
            "videos",
            operation="videos.list",
            cost=CostEstimate(units=1, search_calls=0, operation="videos.list"),
            part="snippet,statistics",
        )

    # Calling get_videos requests objective parts only, NEVER statistics
    transport.queue_response(200, {"items": []})
    await provider.get_videos(["test_vid_1"])
    assert len(transport.requests) == 1
    requested_part = transport.requests[0]["params"]["part"]
    assert "statistics" not in requested_part
    assert "snippet" in requested_part
    assert "contentDetails" in requested_part


@pytest.mark.anyio
async def test_IT_PROV_live_provider_read_retries_on_429_and_5xx_with_backoff() -> None:
    """Reads retry up to 3 times on 429 and 5xx with exponential backoff (NFR-8, INV-24)."""
    delays: list[float] = []

    async def _mock_sleep(duration: float) -> None:
        delays.append(duration)

    transport = _MockLiveTransport()
    # 2 transient failures (429, 503) followed by a 200 success
    transport.queue_response(429, {"error": {"message": "Rate limit exceeded"}})
    transport.queue_response(503, {"error": {"message": "Backend unavailable"}})
    transport.queue_response(
        200,
        {
            "items": [
                {
                    "id": "vid_async_01",
                    "snippet": {"title": "Async Python", "channelId": "UC_01"},
                    "contentDetails": {"duration": "PT5M"},
                    "status": {"privacyStatus": "public", "uploadStatus": "processed"},
                }
            ]
        },
    )

    guard = _RecordingQuotaGuard()
    provider = LiveYouTubeProvider(
        http_transport=transport,
        quota_guard=guard,
        sleep_fn=_mock_sleep,
    )

    videos = await provider.get_videos(["vid_async_01"])
    assert len(videos) == 1
    assert videos[0].video_id == "vid_async_01"
    assert len(transport.requests) == 3
    assert delays == [0.5, 1.0]  # Exponential backoff: 0.5s, 1.0s
    assert guard.units_used == 1  # Charged only on final success


@pytest.mark.anyio
async def test_IT_PROV_live_provider_read_retries_exhausted_raises_mapped_error() -> None:
    """Reads exhausting all 3 retries charge quota and raise mapped ToolError."""
    delays: list[float] = []

    async def _mock_sleep(duration: float) -> None:
        delays.append(duration)

    transport = _MockLiveTransport()
    for _ in range(4):  # Initial + 3 retries = 4 attempts
        transport.queue_response(500, {"error": {"message": "Internal error"}})

    guard = _RecordingQuotaGuard()
    provider = LiveYouTubeProvider(
        http_transport=transport,
        quota_guard=guard,
        sleep_fn=_mock_sleep,
    )

    with pytest.raises(ToolError) as exc_info:
        await provider.get_videos(["vid_fail"])

    assert exc_info.value.code is ErrorCode.PERMISSION_DENIED  # 500 maps to permission/server error
    assert len(transport.requests) == 4
    assert delays == [0.5, 1.0, 2.0]  # 3 backoff sleeps
    assert guard.units_used == 1  # Quota charged


@pytest.mark.anyio
async def test_IT_PROV_live_provider_zero_write_retries() -> None:
    """Writes (insert_playlist, insert_playlist_item) NEVER retry on error (NFR-8, INV-24)."""
    transport = _MockLiveTransport()
    transport.queue_response(503, {"error": {"message": "Write failed"}})

    guard = _RecordingQuotaGuard()
    provider = LiveYouTubeProvider(
        http_transport=transport,
        quota_guard=guard,
        access_token="valid_write_token",
    )

    with pytest.raises(ToolError):
        await provider.insert_playlist(title="My Playlist")

    assert len(transport.requests) == 1  # EXACTLY 1 attempt, ZERO retries
    assert guard.units_used == 50  # 50 units charged for write attempt


@pytest.mark.anyio
async def test_IT_PROV_live_provider_upstream_error_table_mapping() -> None:
    """Verifies upstream Google API error reasons map to SRS Section 4.2 ErrorCodes."""
    test_cases = [
        ("quotaExceeded", 403, ErrorCode.QUOTA_EXHAUSTED_UPSTREAM),
        ("rateLimitExceeded", 403, ErrorCode.RATE_LIMITED),
        ("userRateLimitExceeded", 403, ErrorCode.RATE_LIMITED),
        ("videoNotFound", 404, ErrorCode.VIDEO_UNAVAILABLE),
        ("videoPrivate", 403, ErrorCode.VIDEO_UNAVAILABLE),
        ("youtubeSignupRequired", 403, ErrorCode.CHANNEL_REQUIRED),
        ("insufficientPermissions", 403, ErrorCode.SCOPE_INSUFFICIENT),
        ("forbidden", 403, ErrorCode.PERMISSION_DENIED),
    ]

    for reason, status, expected_code in test_cases:
        transport = _MockLiveTransport()
        transport.queue_response(
            status,
            {
                "error": {
                    "errors": [{"reason": reason}],
                    "message": f"Upstream error {reason}",
                }
            },
        )
        guard = _RecordingQuotaGuard()
        provider = LiveYouTubeProvider(
            http_transport=transport,
            quota_guard=guard,
            access_token="tok",
            config=AppConfig(reliability=ReliabilityConfig(read_max_retries=0)),
        )

        with pytest.raises(ToolError) as exc_info:
            await provider.get_videos(["vid_test"])

        assert exc_info.value.code is expected_code, f"Failed mapping for {reason}"
        if reason == "quotaExceeded":
            assert guard.upstream_exhausted is True


@pytest.mark.anyio
async def test_IT_PROV_all_operations_charge_correct_quota_costs() -> None:
    """Each YouTubeProvider operation estimates and charges the correct quota."""
    transport = _MockLiveTransport()
    guard = _RecordingQuotaGuard()
    provider = LiveYouTubeProvider(
        http_transport=transport,
        quota_guard=guard,
        access_token="mock_tok",
    )

    # 1. get_videos (1 unit per call)
    transport.queue_response(200, {"items": [{"id": "v1", "snippet": {"title": "V1"}}]})
    await provider.get_videos(["v1"])
    assert guard.units_used == 1

    # 2. search_videos (1 search call)
    transport.queue_response(
        200, {"items": [{"id": {"videoId": "v1"}, "snippet": {"title": "Hit"}}]}
    )
    await provider.search_videos("python")
    assert guard.search_calls_used == 1

    # 3. search_channels (1 search call)
    transport.queue_response(
        200, {"items": [{"id": {"channelId": "c1"}, "snippet": {"title": "Chan"}}]}
    )
    await provider.search_channels("python")
    assert guard.search_calls_used == 2

    # 4. get_channels (1 unit)
    transport.queue_response(200, {"items": [{"id": "c1", "snippet": {"title": "Chan"}}]})
    await provider.get_channels(["c1"])
    assert guard.units_used == 2

    # 5. get_channel_by_handle (2 calls: forHandle + get_channels = 2 units)
    transport.queue_response(200, {"items": [{"id": "c1"}]})
    transport.queue_response(200, {"items": [{"id": "c1", "snippet": {"title": "Chan"}}]})
    await provider.get_channel_by_handle("@Chan")
    assert guard.units_used == 4

    # 6. get_my_channel (2 units: mine + get_channels)
    transport.queue_response(200, {"items": [{"id": "c_mine"}]})
    transport.queue_response(200, {"items": [{"id": "c_mine", "snippet": {"title": "Mine"}}]})
    my_chan = await provider.get_my_channel()
    assert my_chan.channel_id == "c_mine"
    assert guard.units_used == 6

    # 7. list_subscriptions_mine (1 unit)
    transport.queue_response(
        200, {"items": [{"snippet": {"title": "Sub", "publishedAt": "2026-11-20T10:00:00Z"}}]}
    )
    subs = await provider.list_subscriptions_mine()
    assert len(subs) == 1
    assert subs[0].source is EventSource.SUBSCRIPTION
    assert guard.units_used == 7

    # 8. list_playlists_mine (1 unit)
    transport.queue_response(200, {"items": [{"id": "pl1", "snippet": {"title": "PL1"}}]})
    pls = await provider.list_playlists_mine()
    assert len(pls) == 1
    assert guard.units_used == 8

    # 9. list_playlist_items (1 unit)
    transport.queue_response(
        200, {"items": [{"snippet": {"title": "Item 1", "publishedAt": "2026-11-20T10:00:00Z"}}]}
    )
    items = await provider.list_playlist_items("pl1")
    assert len(items) == 1
    assert items[0].source is EventSource.PLAYLIST_ITEM
    assert guard.units_used == 9

    # 10. list_liked_videos_rated (1 unit)
    transport.queue_response(200, {"items": [{"id": "v_liked", "snippet": {"title": "Liked"}}]})
    liked = await provider.list_liked_videos_rated()
    assert len(liked) == 1
    assert guard.units_used == 10

    # 11. get_video_categories (1 unit)
    transport.queue_response(200, {"items": [{"id": "28", "snippet": {"title": "Science & Tech"}}]})
    cats = await provider.get_video_categories()
    assert cats["28"] == "Science & Tech"
    assert guard.units_used == 11

    # 12. insert_playlist (50 units)
    transport.queue_response(
        201,
        {
            "id": "pl_created",
            "snippet": {"title": "New PL"},
            "status": {"privacyStatus": "private"},
        },
    )
    created = await provider.insert_playlist(title="New PL")
    assert created.playlist_id == "pl_created"
    assert guard.units_used == 61

    # 13. insert_playlist_item (50 units)
    transport.queue_response(201, {"id": "item_created"})
    item_id = await provider.insert_playlist_item(playlist_id="pl_created", video_id="v1")
    assert item_id == "item_created"
    assert guard.units_used == 111


@pytest.mark.anyio
async def test_IT_PROV_urllib_transport_success() -> None:
    from unittest.mock import MagicMock, patch

    transport = UrllibLiveHttpTransport()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.read.return_value = b'{"status": "ok"}'
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        code, _headers, body = await transport.request(
            "GET",
            "https://www.googleapis.com/youtube/v3/videos",
            params={"id": "v1"},
            headers={"User-Agent": "test"},
        )
        assert code == 200
        assert body == {"status": "ok"}


@pytest.mark.anyio
async def test_IT_PROV_urllib_transport_http_error() -> None:
    import io
    import urllib.error
    from unittest.mock import patch

    transport = UrllibLiveHttpTransport()
    err = urllib.error.HTTPError(
        url="https://example.com",
        code=403,
        msg="Forbidden",
        hdrs={},  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"error": {"message": "Forbidden"}}'),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        code, _headers, body = await transport.request(
            "POST",
            "https://www.googleapis.com/youtube/v3/playlists",
            json_body={"snippet": {"title": "test"}},
        )
        assert code == 403
        assert "error" in body


@pytest.mark.anyio
async def test_IT_PROV_urllib_transport_network_failure() -> None:
    from unittest.mock import patch

    transport = UrllibLiveHttpTransport()
    with patch("urllib.request.urlopen", side_effect=OSError("Network down")):
        with pytest.raises(ToolError) as exc_info:
            await transport.request("GET", "https://example.com")
        assert exc_info.value.code == ErrorCode.RATE_LIMITED


def test_IT_PROV_parse_datetime_helpers() -> None:
    from yt_intel_mcp.provider.live import _ensure_utc, _parse_datetime

    now = datetime(2026, 11, 27, 12, 0, 0)
    assert _ensure_utc(now).tzinfo == UTC
    assert _parse_datetime("") is None
    assert _parse_datetime(None) is None
    assert _parse_datetime(12345) is None
    assert _parse_datetime("invalid-date") is None
    dt = _parse_datetime(now)
    assert dt is not None and dt.tzinfo == UTC


@pytest.mark.anyio
async def test_IT_PROV_token_store_and_oauth_required() -> None:
    from unittest.mock import MagicMock

    from yt_intel_mcp.auth.token_store import TokenBundle

    # 1. Require OAuth when no token or store is configured
    provider = LiveYouTubeProvider()
    with pytest.raises(ToolError) as exc_info:
        await provider.list_playlists_mine()
    assert exc_info.value.code == ErrorCode.AUTH_REAUTHORIZATION_REQUIRED

    # 2. TokenStore integration
    mock_store = MagicMock()
    stored = TokenBundle(
        access_token="ya29.store_token",
        refresh_token="1//refresh",
        scopes=("https://www.googleapis.com/auth/youtube",),
        expires_at_utc=datetime.now(UTC),
        issued_at_utc=datetime.now(UTC),
    )
    mock_store.load_bundle.return_value = (stored, None)

    transport = _MockLiveTransport()
    transport.queue_response(200, {"items": []})
    provider_with_store = LiveYouTubeProvider(token_store=mock_store, http_transport=transport)
    pls = await provider_with_store.list_playlists_mine()
    assert pls == []


@pytest.mark.anyio
async def test_IT_PROV_search_videos_channel_parameters() -> None:
    transport = _MockLiveTransport()
    provider = LiveYouTubeProvider(api_key="AIzaSyTest", http_transport=transport)

    transport.queue_response(200, {"items": []})
    await provider.search_videos(
        "python",
        relevance_language="en",
        region_code="US",
        page_token="next_page",
        video_duration="medium",
    )
    assert transport.requests[0]["params"]["relevanceLanguage"] == "en"
    assert transport.requests[0]["params"]["regionCode"] == "US"
    assert transport.requests[0]["params"]["pageToken"] == "next_page"
    assert transport.requests[0]["params"]["videoDuration"] == "medium"

    transport.queue_response(200, {"items": []})
    await provider.search_channels("python", relevance_language="en", page_token="pg1")
    assert transport.requests[1]["params"]["relevanceLanguage"] == "en"
    assert transport.requests[1]["params"]["pageToken"] == "pg1"


@pytest.mark.live
@pytest.mark.skipif(
    not os.environ.get("YT_INTEL_TEST_LIVE"),
    reason="Live YouTube API tests require YT_INTEL_TEST_LIVE=1 (TQ-5)",
)
@pytest.mark.anyio
async def test_IT_PROV_opt_in_live_api_call() -> None:
    """Opt-in live YouTube Data API call for scheduled live CI workflow (SR-16)."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    provider = LiveYouTubeProvider(api_key=api_key)
    categories = await provider.get_video_categories(region_code="US")
    assert "28" in categories
