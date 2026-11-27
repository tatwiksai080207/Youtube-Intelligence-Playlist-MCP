"""Live YouTube Data API v3 provider implementation (FR-8.1, NFR-8, C-1, INV-18, INV-24).

Communicates with official Google YouTube Data API v3 endpoints over HTTPS.
Excludes statistics, retries reads on 429/5xx, never retries writes, and charges the quota ledger.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast, runtime_checkable

import anyio

from yt_intel_mcp.auth.token_store import TokenStore
from yt_intel_mcp.config import AppConfig, QuotaConfig, ReliabilityConfig
from yt_intel_mcp.durations import parse_optional_duration
from yt_intel_mcp.errors import ErrorCode, ToolError, map_upstream_error
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
from yt_intel_mcp.quota.guard import QuotaGuard

__all__ = [
    "FORBIDDEN_PARTS",
    "YOUTUBE_API_BASE_URL",
    "LiveHttpTransport",
    "LiveYouTubeProvider",
    "UrllibLiveHttpTransport",
]

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
FORBIDDEN_PARTS: frozenset[str] = frozenset({"statistics"})

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_datetime(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return _ensure_utc(raw)
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return _ensure_utc(parsed)
    except Exception:
        return None


@runtime_checkable
class LiveHttpTransport(Protocol):
    """Transport protocol for live YouTube Data API HTTP requests."""

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
        """Execute HTTP request returning status code, response headers, and parsed JSON."""
        ...


class UrllibLiveHttpTransport:
    """Standard library HTTP transport using urllib.request via worker thread."""

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
        def _execute() -> tuple[int, Mapping[str, str], dict[str, Any]]:
            target_url = url
            if params:
                query_str = urllib.parse.urlencode(
                    {k: str(v) for k, v in params.items() if v is not None}
                )
                delimiter = "&" if "?" in target_url else "?"
                target_url = f"{target_url}{delimiter}{query_str}"

            req_headers: dict[str, str] = {"Accept": "application/json"}
            if headers:
                req_headers.update(headers)

            data: bytes | None = None
            if json_body is not None:
                data = json.dumps(json_body).encode("utf-8")
                req_headers["Content-Type"] = "application/json; charset=utf-8"

            req = urllib.request.Request(
                target_url,
                data=data,
                headers=req_headers,
                method=method.upper(),
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status_code = response.status
                    resp_headers = dict(response.headers)
                    body_raw = response.read().decode("utf-8")
                    try:
                        parsed = json.loads(body_raw)
                    except Exception:
                        parsed = {}
                    return status_code, resp_headers, parsed
            except urllib.error.HTTPError as exc:
                resp_headers = dict(exc.headers) if exc.headers else {}
                body_raw = exc.read().decode("utf-8")
                try:
                    parsed = json.loads(body_raw)
                except Exception:
                    parsed = {"raw": body_raw}
                return exc.code, resp_headers, parsed
            except Exception as exc:
                raise ToolError(
                    ErrorCode.RATE_LIMITED,
                    f"Live YouTube API connection failed: {exc}",
                ) from exc

        return await anyio.to_thread.run_sync(_execute)


class LiveYouTubeProvider:
    """Live YouTube Data API v3 provider (FR-8.1, NFR-8, C-1, INV-18, INV-24)."""

    def __init__(
        self,
        *,
        quota_guard: QuotaGuard | None = None,
        token_store: TokenStore | None = None,
        access_token: str | None = None,
        api_key: str | None = None,
        config: AppConfig | None = None,
        http_transport: LiveHttpTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        base_config = config or AppConfig()
        self.quota_guard = quota_guard
        self.quota_config: QuotaConfig = base_config.quota
        self.reliability: ReliabilityConfig = base_config.reliability
        self.token_store = token_store
        self._explicit_access_token = access_token
        self.api_key = api_key
        self.transport: LiveHttpTransport = http_transport or UrllibLiveHttpTransport()
        self.clock = clock or (lambda: datetime.now(UTC))
        self._sleep_fn = sleep_fn or anyio.sleep
        self.total_quota_used = QuotaUsed()

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        quota_guard: QuotaGuard | None = None,
        token_store: TokenStore | None = None,
        api_key: str | None = None,
        http_transport: LiveHttpTransport | None = None,
    ) -> LiveYouTubeProvider:
        """Create a LiveYouTubeProvider using settings from AppConfig."""
        return cls(
            quota_guard=quota_guard,
            token_store=token_store,
            api_key=api_key,
            config=config,
            http_transport=http_transport,
        )

    def _cost_for(self, operation: str, count: int = 1) -> CostEstimate:
        if self.quota_guard is not None:
            return self.quota_guard.estimate(operation, count=count)
        if operation == "search.list":
            return CostEstimate(
                units=self.quota_config.search_unit_cost,
                search_calls=self.quota_config.search_call_cost,
                operation=operation,
            )
        if operation in ("playlists.insert", "playlistItems.insert"):
            return CostEstimate(
                units=self.quota_config.playlist_insert_unit_cost,
                search_calls=0,
                operation=operation,
            )
        return CostEstimate(
            units=self.quota_config.list_unit_cost * count,
            search_calls=0,
            operation=operation,
        )

    def _charge(self, cost: CostEstimate) -> None:
        self.total_quota_used = self.total_quota_used + cost.to_quota_used()
        if self.quota_guard is not None:
            self.quota_guard.charge(cost)

    def _preflight(self, cost: CostEstimate) -> None:
        if self.quota_guard is not None:
            self.quota_guard.preflight(cost)

    def _resolve_auth(
        self, *, require_oauth: bool = False
    ) -> tuple[dict[str, str], dict[str, str]]:
        headers: dict[str, str] = {}
        params: dict[str, str] = {}

        token = self._explicit_access_token
        if token is None and self.token_store is not None:
            loaded = self.token_store.load_bundle()
            if loaded is not None:
                token = loaded[0].access_token

        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif require_oauth:
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "Authentication required for private or mutating YouTube operation.",
            )
        elif self.api_key:
            params["key"] = self.api_key
        return headers, params

    async def _execute_with_retry(
        self,
        method: str,
        endpoint: str,
        *,
        operation: str,
        cost: CostEstimate,
        part: str,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        require_oauth: bool = False,
        is_write: bool = False,
    ) -> dict[str, Any]:
        """Execute live YouTube API call with read retries and zero write retries."""
        for part_name in part.split(","):
            if part_name.strip() in FORBIDDEN_PARTS:
                raise ValueError(f"Forbidden part {part_name!r} requested (INV-01).")

        self._preflight(cost)

        auth_headers, auth_params = self._resolve_auth(require_oauth=require_oauth)
        merged_params: dict[str, Any] = dict(auth_params)
        merged_params["part"] = part
        if params:
            merged_params.update(params)

        max_retries = 0 if is_write else self.reliability.read_max_retries
        attempt = 0
        last_error_data: dict[str, Any] = {}
        last_status = 200

        while True:
            try:
                status_code, _, body = await self.transport.request(
                    method,
                    f"{YOUTUBE_API_BASE_URL}/{endpoint}",
                    headers=auth_headers,
                    params=merged_params,
                    json_body=json_body,
                )
                last_status = status_code
                if status_code in (200, 201):
                    self._charge(cost)
                    return body

                last_error_data = body.get("error", {})
                if attempt < max_retries and status_code in _RETRYABLE_STATUS_CODES:
                    attempt += 1
                    backoff_delay = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "YouTube API read failed with %d; retrying (%d/%d) in %.2fs",
                        status_code,
                        attempt,
                        max_retries,
                        backoff_delay,
                    )
                    await self._sleep_fn(backoff_delay)
                    continue

                break
            except ToolError:
                raise
            except Exception as exc:
                if attempt < max_retries and not is_write:
                    attempt += 1
                    backoff_delay = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "YouTube API network error: %s; retrying (%d/%d) in %.2fs",
                        exc,
                        attempt,
                        max_retries,
                        backoff_delay,
                    )
                    await self._sleep_fn(backoff_delay)
                    continue
                self._charge(cost)
                raise ToolError(
                    ErrorCode.RATE_LIMITED if not is_write else ErrorCode.PERMISSION_DENIED,
                    f"Live YouTube API request failed: {exc}",
                    quota_used=cost.to_quota_used(),
                ) from exc

        # All retries exhausted or non-retryable error
        self._charge(cost)
        reason = ""
        message = ""
        if isinstance(last_error_data, dict):
            errors_list = last_error_data.get("errors", [])
            if errors_list and isinstance(errors_list, list) and isinstance(errors_list[0], dict):
                reason = str(errors_list[0].get("reason", ""))
            message = str(last_error_data.get("message", ""))

        if reason == "quotaExceeded" and self.quota_guard is not None:
            self.quota_guard.mark_upstream_exhausted()

        raise map_upstream_error(
            reason=reason or None,
            http_status=last_status,
            message=message or None,
            details={"endpoint": endpoint, "operation": operation},
            quota_used=cost.to_quota_used(),
        )

    async def get_videos(self, video_ids: Sequence[str]) -> list[VideoMeta]:
        """Fetch objective metadata for up to 50 video IDs per call (FR-8.1)."""
        if not video_ids:
            return []

        results: list[VideoMeta] = []
        chunk_size = 50
        for i in range(0, len(video_ids), chunk_size):
            chunk = list(video_ids[i : i + chunk_size])
            operation = "videos.list"
            cost = self._cost_for(operation, count=1)
            body = await self._execute_with_retry(
                "GET",
                "videos",
                operation=operation,
                cost=cost,
                part="snippet,contentDetails,status,topicDetails",
                params={"id": ",".join(chunk), "maxResults": len(chunk)},
            )
            for item in body.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                status = item.get("status", {})

                privacy = str(status.get("privacyStatus", "public"))
                upload_status = str(status.get("uploadStatus", "processed"))
                is_available = upload_status != "deleted" and privacy != "private"
                content_rating = content_details.get("contentRating", {})
                is_age_restricted = content_rating.get("ytRating") == "ytAgeRestricted"

                duration_str = content_details.get("duration")
                duration_secs = parse_optional_duration(duration_str)

                results.append(
                    VideoMeta(
                        video_id=str(item["id"]),
                        title=str(snippet.get("title", "")),
                        description=str(snippet.get("description", "")),
                        channel_id=str(snippet.get("channelId", "")),
                        channel_title=str(snippet.get("channelTitle", "")),
                        published_at=_parse_datetime(snippet.get("publishedAt")),
                        tags=tuple(str(t) for t in snippet.get("tags", ())),
                        category_id=str(snippet.get("categoryId"))
                        if snippet.get("categoryId")
                        else None,
                        duration_seconds=duration_secs,
                        default_audio_language=str(snippet.get("defaultAudioLanguage"))
                        if snippet.get("defaultAudioLanguage")
                        else None,
                        default_language=str(snippet.get("defaultLanguage"))
                        if snippet.get("defaultLanguage")
                        else None,
                        live_broadcast_content=str(snippet.get("liveBroadcastContent", "none")),
                        is_embeddable=bool(status.get("embeddable", True)),
                        privacy_status=privacy,
                        is_age_restricted=is_age_restricted,
                        is_available=is_available,
                    )
                )
        return results

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
        """Search YouTube for candidate videos matching query and filters."""
        operation = "search.list"
        cost = self._cost_for(operation, count=1)
        params: dict[str, Any] = {
            "q": query,
            "type": "video",
            "maxResults": max_results,
        }
        if video_duration and video_duration != "any":
            params["videoDuration"] = video_duration
        if relevance_language:
            params["relevanceLanguage"] = relevance_language
        if region_code:
            params["regionCode"] = region_code
        if page_token:
            params["pageToken"] = page_token

        body = await self._execute_with_retry(
            "GET",
            "search",
            operation=operation,
            cost=cost,
            part="snippet",
            params=params,
        )
        hits: list[SearchHit] = []
        for item in body.get("items", []):
            item_id = item.get("id", {}).get("videoId")
            if not item_id:
                continue
            snippet = item.get("snippet", {})
            hits.append(
                SearchHit(
                    item_id=str(item_id),
                    kind="video",
                    title=str(snippet.get("title", "")),
                    description=str(snippet.get("description", "")),
                    channel_id=str(snippet.get("channelId", "")),
                    channel_title=str(snippet.get("channelTitle", "")),
                    published_at=_parse_datetime(snippet.get("publishedAt")),
                )
            )
        return hits

    async def search_channels(
        self,
        query: str,
        *,
        max_results: int = 25,
        relevance_language: str | None = None,
        page_token: str | None = None,
    ) -> list[SearchHit]:
        """Search YouTube for candidate channels matching query."""
        operation = "search.list"
        cost = self._cost_for(operation, count=1)
        params: dict[str, Any] = {
            "q": query,
            "type": "channel",
            "maxResults": max_results,
        }
        if relevance_language:
            params["relevanceLanguage"] = relevance_language
        if page_token:
            params["pageToken"] = page_token

        body = await self._execute_with_retry(
            "GET",
            "search",
            operation=operation,
            cost=cost,
            part="snippet",
            params=params,
        )
        hits: list[SearchHit] = []
        for item in body.get("items", []):
            channel_id = item.get("id", {}).get("channelId")
            if not channel_id:
                continue
            snippet = item.get("snippet", {})
            hits.append(
                SearchHit(
                    item_id=str(channel_id),
                    kind="channel",
                    title=str(snippet.get("title", "")),
                    description=str(snippet.get("description", "")),
                    channel_id=str(channel_id),
                    channel_title=str(snippet.get("channelTitle", snippet.get("title", ""))),
                    published_at=_parse_datetime(snippet.get("publishedAt")),
                )
            )
        return hits

    async def get_channels(self, channel_ids: Sequence[str]) -> list[ChannelMeta]:
        """Fetch objective metadata for up to 50 channel IDs per call."""
        if not channel_ids:
            return []

        results: list[ChannelMeta] = []
        chunk_size = 50
        for i in range(0, len(channel_ids), chunk_size):
            chunk = list(channel_ids[i : i + chunk_size])
            operation = "channels.list"
            cost = self._cost_for(operation, count=1)
            body = await self._execute_with_retry(
                "GET",
                "channels",
                operation=operation,
                cost=cost,
                part="snippet,contentDetails,topicDetails",
                params={"id": ",".join(chunk), "maxResults": len(chunk)},
            )
            for item in body.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                related = content_details.get("relatedPlaylists", {})
                topic_details = item.get("topicDetails", {})

                results.append(
                    ChannelMeta(
                        channel_id=str(item["id"]),
                        title=str(snippet.get("title", "")),
                        description=str(snippet.get("description", "")),
                        custom_url=str(snippet.get("customUrl"))
                        if snippet.get("customUrl")
                        else None,
                        published_at=_parse_datetime(snippet.get("publishedAt")),
                        country=str(snippet.get("country")) if snippet.get("country") else None,
                        default_language=str(snippet.get("defaultLanguage"))
                        if snippet.get("defaultLanguage")
                        else None,
                        topic_categories=tuple(
                            str(t) for t in topic_details.get("topicCategories", ())
                        ),
                        uploads_playlist_id=str(related.get("uploads"))
                        if related.get("uploads")
                        else None,
                        likes_playlist_id=str(related.get("likes"))
                        if related.get("likes")
                        else None,
                    )
                )
        return results

    async def get_channel_by_handle(self, handle: str) -> ChannelMeta | None:
        """Resolve an @handle via channels.list?forHandle and return metadata if found."""
        cleaned = handle.strip()
        if not cleaned:
            return None
        operation = "channels.list"
        cost = self._cost_for(operation, count=1)
        body = await self._execute_with_retry(
            "GET",
            "channels",
            operation=operation,
            cost=cost,
            part="snippet,contentDetails,topicDetails",
            params={"forHandle": cleaned if cleaned.startswith("@") else f"@{cleaned}"},
        )
        items = body.get("items", [])
        if not items:
            return None
        channels = await self.get_channels([str(items[0]["id"])])
        return channels[0] if channels else None

    async def get_my_channel(self) -> ChannelMeta:
        """Fetch the authenticated user's primary YouTube channel metadata."""
        operation = "channels.list"
        cost = self._cost_for(operation, count=1)
        body = await self._execute_with_retry(
            "GET",
            "channels",
            operation=operation,
            cost=cost,
            part="snippet,contentDetails,topicDetails",
            params={"mine": "true"},
            require_oauth=True,
        )
        items = body.get("items", [])
        if not items:
            raise ToolError(
                ErrorCode.CHANNEL_REQUIRED,
                "The authenticated Google account does not have an active YouTube channel.",
                details={"endpoint": "channels.list:mine"},
                quota_used=cost.to_quota_used(),
            )
        channels = await self.get_channels([str(items[0]["id"])])
        if not channels:
            raise ToolError(
                ErrorCode.CHANNEL_REQUIRED,
                "The authenticated Google account does not have an active YouTube channel.",
                details={"endpoint": "channels.list:mine"},
                quota_used=cost.to_quota_used(),
            )
        return channels[0]

    async def list_subscriptions_mine(self, *, max_results: int = 50) -> list[UserEvent]:
        """List authenticated subscriptions with action timestamps."""
        operation = "subscriptions.list"
        cost = self._cost_for(operation, count=1)
        body = await self._execute_with_retry(
            "GET",
            "subscriptions",
            operation=operation,
            cost=cost,
            part="snippet",
            params={"mine": "true", "maxResults": max_results},
            require_oauth=True,
        )
        events: list[UserEvent] = []
        for item in body.get("items", []):
            snippet = item.get("snippet", {})
            channel_id = snippet.get("resourceId", {}).get("channelId")
            events.append(
                UserEvent(
                    source=EventSource.SUBSCRIPTION,
                    time_kind=EventTimeKind.DATED,
                    event_time=_parse_datetime(snippet.get("publishedAt")),
                    channel_id=str(channel_id) if channel_id else None,
                    title=str(snippet.get("title", "")),
                )
            )
        return events

    async def list_playlists_mine(self, *, max_results: int = 50) -> list[PlaylistSummary]:
        """List playlists owned by the authenticated user."""
        operation = "playlists.list"
        cost = self._cost_for(operation, count=1)
        body = await self._execute_with_retry(
            "GET",
            "playlists",
            operation=operation,
            cost=cost,
            part="snippet,contentDetails,status",
            params={"mine": "true", "maxResults": max_results},
            require_oauth=True,
        )
        summaries: list[PlaylistSummary] = []
        for item in body.get("items", []):
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            status = item.get("status", {})
            summaries.append(
                PlaylistSummary(
                    playlist_id=str(item["id"]),
                    title=str(snippet.get("title", "")),
                    description=str(snippet.get("description", "")),
                    channel_id=str(snippet.get("channelId", "")),
                    channel_title=str(snippet.get("channelTitle", "")),
                    published_at=_parse_datetime(snippet.get("publishedAt")),
                    item_count=int(content_details.get("itemCount", 0)),
                    privacy_status=str(status.get("privacyStatus", "private")),
                )
            )
        return summaries

    async def list_playlist_items(
        self,
        playlist_id: str,
        *,
        max_results: int = 50,
    ) -> list[UserEvent]:
        """List items in a playlist with playlist-item insertion timestamps."""
        operation = "playlistItems.list"
        cost = self._cost_for(operation, count=1)
        body = await self._execute_with_retry(
            "GET",
            "playlistItems",
            operation=operation,
            cost=cost,
            part="snippet,contentDetails",
            params={"playlistId": playlist_id, "maxResults": max_results},
        )
        events: list[UserEvent] = []
        source = (
            EventSource.LIKED_VIDEO if playlist_id.startswith("LL") else EventSource.PLAYLIST_ITEM
        )
        for item in body.get("items", []):
            snippet = item.get("snippet", {})
            video_id = snippet.get("resourceId", {}).get("videoId")
            events.append(
                UserEvent(
                    source=source,
                    time_kind=EventTimeKind.DATED,
                    event_time=_parse_datetime(snippet.get("publishedAt")),
                    video_id=str(video_id) if video_id else None,
                    channel_id=str(snippet.get("channelId")) if snippet.get("channelId") else None,
                    playlist_id=playlist_id,
                    title=str(snippet.get("title", "")),
                )
            )
        return events

    async def list_liked_videos_rated(self, *, max_results: int = 50) -> list[VideoMeta]:
        """List videos rated 'like' via videos.list."""
        operation = "videos.list"
        cost = self._cost_for(operation, count=1)
        body = await self._execute_with_retry(
            "GET",
            "videos",
            operation=operation,
            cost=cost,
            part="snippet,contentDetails,status,topicDetails",
            params={"myRating": "like", "maxResults": max_results},
            require_oauth=True,
        )
        results: list[VideoMeta] = []
        for item in body.get("items", []):
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            status = item.get("status", {})
            results.append(
                VideoMeta(
                    video_id=str(item["id"]),
                    title=str(snippet.get("title", "")),
                    description=str(snippet.get("description", "")),
                    channel_id=str(snippet.get("channelId", "")),
                    channel_title=str(snippet.get("channelTitle", "")),
                    published_at=_parse_datetime(snippet.get("publishedAt")),
                    tags=tuple(str(t) for t in snippet.get("tags", ())),
                    category_id=str(snippet.get("categoryId"))
                    if snippet.get("categoryId")
                    else None,
                    duration_seconds=parse_optional_duration(content_details.get("duration")),
                    privacy_status=str(status.get("privacyStatus", "public")),
                    is_available=status.get("uploadStatus") != "deleted",
                )
            )
        return results

    async def get_video_categories(self, *, region_code: str = "US") -> dict[str, str]:
        """Fetch video category ID to title mapping for a YouTube region code."""
        operation = "videoCategories.list"
        cost = self._cost_for(operation, count=1)
        body = await self._execute_with_retry(
            "GET",
            "videoCategories",
            operation=operation,
            cost=cost,
            part="snippet",
            params={"regionCode": region_code},
        )
        categories: dict[str, str] = {}
        for item in body.get("items", []):
            cat_id = str(item.get("id", ""))
            title = str(item.get("snippet", {}).get("title", ""))
            if cat_id and title:
                categories[cat_id] = title
        return categories

    async def insert_playlist(
        self,
        *,
        title: str,
        description: str = "",
        privacy_status: Literal["private", "unlisted", "public"] = "private",
    ) -> CreatedPlaylist:
        """Create a new YouTube playlist after trusted confirmation (FR-5.5, ZERO retries)."""
        operation = "playlists.insert"
        cost = self._cost_for(operation, count=1)
        json_body = {
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": privacy_status},
        }
        body = await self._execute_with_retry(
            "POST",
            "playlists",
            operation=operation,
            cost=cost,
            part="snippet,status",
            json_body=json_body,
            require_oauth=True,
            is_write=True,
        )
        playlist_id = str(body["id"])
        snippet = body.get("snippet", {})
        status = body.get("status", {})
        raw_status = status.get("privacyStatus", privacy_status)
        resolved_status: Literal["private", "unlisted", "public"]
        if raw_status in ("private", "unlisted", "public"):
            resolved_status = cast(Literal["private", "unlisted", "public"], raw_status)
        else:
            resolved_status = privacy_status

        return CreatedPlaylist(
            playlist_id=playlist_id,
            title=str(snippet.get("title", title)),
            description=str(snippet.get("description", description)),
            privacy_status=resolved_status,
            channel_id=str(snippet.get("channelId", "")),
            published_at=_parse_datetime(snippet.get("publishedAt")),
            url=f"https://www.youtube.com/playlist?list={playlist_id}",
        )

    async def insert_playlist_item(
        self,
        *,
        playlist_id: str,
        video_id: str,
        position: int | None = None,
    ) -> str:
        """Insert a video into a YouTube playlist (FR-5.5, ZERO retries)."""
        operation = "playlistItems.insert"
        cost = self._cost_for(operation, count=1)
        snippet: dict[str, Any] = {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
        if position is not None:
            snippet["position"] = position
        json_body = {"snippet": snippet}

        body = await self._execute_with_retry(
            "POST",
            "playlistItems",
            operation=operation,
            cost=cost,
            part="snippet",
            json_body=json_body,
            require_oauth=True,
            is_write=True,
        )
        return str(body["id"])
