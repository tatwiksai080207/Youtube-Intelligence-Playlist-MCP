"""Persistent TTL metadata cache and caching YouTubeProvider decorator (SR-11, FR-6.3)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, TypeVar

from yt_intel_mcp.config import AppConfig, CacheConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import (
    ChannelMeta,
    CreatedPlaylist,
    EventSource,
    EventTimeKind,
    PlaylistSummary,
    SearchHit,
    UserEvent,
    VideoMeta,
)
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.store import CacheEntryKind, SQLiteStore

__all__ = [
    "CacheStats",
    "CachedYouTubeProvider",
    "MetadataCache",
    "make_cache_key",
]

_VALID_KINDS: frozenset[str] = frozenset(
    {"videos", "channels", "searches", "user_lists", "categories"}
)
_FORBIDDEN_CACHE_KEYS: frozenset[str] = frozenset(
    {
        "statistics",
        "viewcount",
        "view_count",
        "likecount",
        "like_count",
        "dislikecount",
        "dislike_count",
        "commentcount",
        "comment_count",
        "favoritecount",
        "favorite_count",
        "subscribercount",
        "subscriber_count",
        "videocount",
        "video_count",
        "access_token",
        "refresh_token",
        "client_secret",
        "id_token",
    }
)

_T = TypeVar("_T")


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_optional_dt(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        raise ValueError(f"Expected ISO timestamp string, got {raw!r}.")
    return _ensure_utc(datetime.fromisoformat(raw))


def _validate_cache_payload(value: Any) -> None:
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key_lower = str(raw_key).lower()
            if key_lower in _FORBIDDEN_CACHE_KEYS:
                raise ValueError(f"Refusing to cache forbidden key {raw_key!r}.")
            _validate_cache_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _validate_cache_payload(item)


def make_cache_key(namespace: str, identifier: Mapping[str, Any] | Sequence[Any] | str) -> str:
    """Build a deterministic normalized cache key for a namespace and request payload."""
    if isinstance(identifier, str):
        return f"{namespace}:{identifier.strip()}"
    encoded = json.dumps(identifier, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]
    return f"{namespace}:{digest}"


def _encode_video(video: VideoMeta) -> dict[str, Any]:
    return {
        "video_id": video.video_id,
        "title": video.title,
        "description": video.description,
        "channel_id": video.channel_id,
        "channel_title": video.channel_title,
        "published_at": video.published_at.isoformat() if video.published_at is not None else None,
        "tags": list(video.tags),
        "category_id": video.category_id,
        "category_name": video.category_name,
        "duration_seconds": video.duration_seconds,
        "default_audio_language": video.default_audio_language,
        "default_language": video.default_language,
        "live_broadcast_content": video.live_broadcast_content,
        "is_embeddable": video.is_embeddable,
        "privacy_status": video.privacy_status,
        "is_age_restricted": video.is_age_restricted,
        "is_available": video.is_available,
    }


def _decode_video(raw: Mapping[str, Any]) -> VideoMeta:
    dur = raw.get("duration_seconds")
    return VideoMeta(
        video_id=str(raw["video_id"]),
        title=str(raw["title"]),
        description=str(raw.get("description", "")),
        channel_id=str(raw.get("channel_id", "")),
        channel_title=str(raw.get("channel_title", "")),
        published_at=_parse_optional_dt(raw.get("published_at")),
        tags=tuple(str(t) for t in raw.get("tags", ())),
        category_id=str(raw["category_id"]) if raw.get("category_id") is not None else None,
        category_name=str(raw["category_name"]) if raw.get("category_name") is not None else None,
        duration_seconds=int(dur) if dur is not None else None,
        default_audio_language=(
            str(raw["default_audio_language"])
            if raw.get("default_audio_language") is not None
            else None
        ),
        default_language=(
            str(raw["default_language"]) if raw.get("default_language") is not None else None
        ),
        live_broadcast_content=str(raw.get("live_broadcast_content", "none")),
        is_embeddable=bool(raw.get("is_embeddable", True)),
        privacy_status=str(raw.get("privacy_status", "public")),
        is_age_restricted=bool(raw.get("is_age_restricted", False)),
        is_available=bool(raw.get("is_available", True)),
    )


def _encode_channel(channel: ChannelMeta) -> dict[str, Any]:
    return {
        "channel_id": channel.channel_id,
        "title": channel.title,
        "description": channel.description,
        "custom_url": channel.custom_url,
        "published_at": (
            channel.published_at.isoformat() if channel.published_at is not None else None
        ),
        "country": channel.country,
        "default_language": channel.default_language,
        "topic_categories": list(channel.topic_categories),
        "keywords": list(channel.keywords),
        "uploads_playlist_id": channel.uploads_playlist_id,
        "likes_playlist_id": channel.likes_playlist_id,
    }


def _decode_channel(raw: Mapping[str, Any]) -> ChannelMeta:
    return ChannelMeta(
        channel_id=str(raw["channel_id"]),
        title=str(raw["title"]),
        description=str(raw.get("description", "")),
        custom_url=str(raw["custom_url"]) if raw.get("custom_url") is not None else None,
        published_at=_parse_optional_dt(raw.get("published_at")),
        country=str(raw["country"]) if raw.get("country") is not None else None,
        default_language=(
            str(raw["default_language"]) if raw.get("default_language") is not None else None
        ),
        topic_categories=tuple(str(item) for item in raw.get("topic_categories", ())),
        keywords=tuple(str(item) for item in raw.get("keywords", ())),
        uploads_playlist_id=(
            str(raw["uploads_playlist_id"]) if raw.get("uploads_playlist_id") is not None else None
        ),
        likes_playlist_id=(
            str(raw["likes_playlist_id"]) if raw.get("likes_playlist_id") is not None else None
        ),
    )


def _encode_search_hit(hit: SearchHit) -> dict[str, Any]:
    return {
        "kind": hit.kind,
        "item_id": hit.item_id,
        "title": hit.title,
        "description": hit.description,
        "channel_id": hit.channel_id,
        "channel_title": hit.channel_title,
        "published_at": hit.published_at.isoformat() if hit.published_at is not None else None,
        "live_broadcast_content": hit.live_broadcast_content,
    }


def _decode_search_hit(raw: Mapping[str, Any]) -> SearchHit:
    raw_kind = str(raw["kind"])
    kind: Literal["video", "channel"] = "channel" if raw_kind == "channel" else "video"
    return SearchHit(
        kind=kind,
        item_id=str(raw["item_id"]),
        title=str(raw["title"]),
        description=str(raw.get("description", "")),
        channel_id=str(raw.get("channel_id", "")),
        channel_title=str(raw.get("channel_title", "")),
        published_at=_parse_optional_dt(raw.get("published_at")),
        live_broadcast_content=str(raw.get("live_broadcast_content", "none")),
    )


def _encode_playlist_summary(summary: PlaylistSummary) -> dict[str, Any]:
    return {
        "playlist_id": summary.playlist_id,
        "title": summary.title,
        "description": summary.description,
        "channel_id": summary.channel_id,
        "channel_title": summary.channel_title,
        "published_at": (
            summary.published_at.isoformat() if summary.published_at is not None else None
        ),
        "item_count": summary.item_count,
        "privacy_status": summary.privacy_status,
    }


def _decode_playlist_summary(raw: Mapping[str, Any]) -> PlaylistSummary:
    return PlaylistSummary(
        playlist_id=str(raw["playlist_id"]),
        title=str(raw["title"]),
        description=str(raw.get("description", "")),
        channel_id=str(raw.get("channel_id", "")),
        channel_title=str(raw.get("channel_title", "")),
        published_at=_parse_optional_dt(raw.get("published_at")),
        item_count=int(raw.get("item_count", 0)),
        privacy_status=str(raw.get("privacy_status", "private")),
    )


def _encode_user_event(event: UserEvent) -> dict[str, Any]:
    return {
        "source": event.source.value,
        "time_kind": event.time_kind.value,
        "event_time": event.event_time.isoformat() if event.event_time is not None else None,
        "video_id": event.video_id,
        "channel_id": event.channel_id,
        "playlist_id": event.playlist_id,
        "title": event.title,
        "category_id": event.category_id,
        "duration_seconds": event.duration_seconds,
        "tags": list(event.tags),
    }


def _decode_user_event(raw: Mapping[str, Any]) -> UserEvent:
    dur = raw.get("duration_seconds")
    return UserEvent(
        source=EventSource(str(raw["source"])),
        time_kind=EventTimeKind(str(raw.get("time_kind", EventTimeKind.UNDATED.value))),
        event_time=_parse_optional_dt(raw.get("event_time")),
        video_id=str(raw["video_id"]) if raw.get("video_id") is not None else None,
        channel_id=str(raw["channel_id"]) if raw.get("channel_id") is not None else None,
        playlist_id=str(raw["playlist_id"]) if raw.get("playlist_id") is not None else None,
        title=str(raw.get("title", "")),
        category_id=str(raw["category_id"]) if raw.get("category_id") is not None else None,
        duration_seconds=int(dur) if dur is not None else None,
        tags=tuple(str(t) for t in raw.get("tags", ())),
    )


@dataclass(slots=True)
class CacheStats:
    """Cumulative read through cache hit and miss counts for diagnostics and tests."""

    hits: int = 0
    misses: int = 0


class MetadataCache:
    """SQLite-backed TTL cache for objective YouTube metadata and scoped user lists."""

    def __init__(
        self,
        store: SQLiteStore,
        config: CacheConfig | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.config = config or CacheConfig()
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> MetadataCache:
        """Instantiate MetadataCache backed by ``config.data_dir / 'yt_intel.db'``."""
        return cls(SQLiteStore.from_config(config), config.cache, clock=clock)

    def _now_utc(self) -> datetime:
        return _ensure_utc(self._clock())

    def ttl_for(self, entry_kind: CacheEntryKind) -> int:
        """Return configured TTL in seconds for an entry category."""
        mapping: dict[CacheEntryKind, int] = {
            "videos": self.config.videos_ttl_seconds,
            "channels": self.config.channels_ttl_seconds,
            "searches": self.config.searches_ttl_seconds,
            "user_lists": self.config.user_lists_ttl_seconds,
            "categories": self.config.categories_ttl_seconds,
        }
        if entry_kind not in mapping:
            raise ValueError(f"Unsupported cache entry_kind: {entry_kind!r}")
        return mapping[entry_kind]

    def get(self, cache_key: str) -> Any | None:
        """Return fresh cached JSON payload or None (evicting expired rows lazily)."""
        now_utc = self._now_utc()
        row = self.store.get_cache_entry(cache_key)
        if row is None:
            return None
        expires_at = _ensure_utc(datetime.fromisoformat(row.expires_at_utc))
        if now_utc >= expires_at:
            with self.store.transaction(immediate=True) as conn:
                self.store.delete_cache_entry(conn, cache_key)
            return None
        return json.loads(row.payload_json)

    def get_many(self, cache_keys: Sequence[str]) -> dict[str, Any]:
        """Batch read fresh cached payloads by key, cleaning up expired entries found."""
        if not cache_keys:
            return {}
        now_utc = self._now_utc()
        expired_keys: list[str] = []
        fresh: dict[str, Any] = {}
        with self.store.transaction(immediate=False) as conn:
            rows = self.store.read_cache_entries(conn, list(cache_keys))
        for key, row in rows.items():
            expires_at = _ensure_utc(datetime.fromisoformat(row.expires_at_utc))
            if now_utc >= expires_at:
                expired_keys.append(key)
            else:
                fresh[key] = json.loads(row.payload_json)
        if expired_keys:
            with self.store.transaction(immediate=True) as conn:
                for key in expired_keys:
                    self.store.delete_cache_entry(conn, key)
        return fresh

    def put(
        self,
        cache_key: str,
        entry_kind: CacheEntryKind,
        payload: Any,
        *,
        ttl_seconds: int | None = None,
        is_personal: bool | None = None,
    ) -> None:
        """Store a JSON-serializable objective payload with TTL and privacy classification."""
        self.put_many(
            [(cache_key, entry_kind, payload)],
            ttl_seconds=ttl_seconds,
            is_personal=is_personal,
        )

    def put_many(
        self,
        items: Sequence[tuple[str, CacheEntryKind, Any]],
        *,
        ttl_seconds: int | None = None,
        is_personal: bool | None = None,
    ) -> None:
        """Atomically store multiple cache items in a single SQLite transaction."""
        if not items:
            return
        now_utc = self._now_utc()
        now_iso = now_utc.isoformat()
        prepared: list[tuple[str, CacheEntryKind, bool, str, str]] = []
        for cache_key, entry_kind, payload in items:
            if entry_kind not in _VALID_KINDS:
                raise ValueError(f"Unsupported cache entry_kind: {entry_kind!r}")
            effective_ttl = ttl_seconds if ttl_seconds is not None else self.ttl_for(entry_kind)
            if effective_ttl <= 0:
                raise ValueError(f"Cache TTL must be positive, got {effective_ttl}.")
            _validate_cache_payload(payload)
            effective_personal = (
                is_personal if is_personal is not None else (entry_kind == "user_lists")
            )
            expires_iso = (now_utc + timedelta(seconds=effective_ttl)).isoformat()
            payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            prepared.append((cache_key, entry_kind, effective_personal, payload_json, expires_iso))

        with self.store.transaction(immediate=True) as conn:
            for cache_key, entry_kind, effective_personal, payload_json, expires_iso in prepared:
                self.store.upsert_cache_entry(
                    conn,
                    cache_key=cache_key,
                    entry_kind=entry_kind,
                    is_personal=effective_personal,
                    payload_json=payload_json,
                    created_at_utc=now_iso,
                    expires_at_utc=expires_iso,
                )

    def invalidate(self, cache_key: str) -> bool:
        """Delete a single cache entry if present."""
        with self.store.transaction(immediate=True) as conn:
            return self.store.delete_cache_entry(conn, cache_key)

    def invalidate_prefix(self, prefix: str) -> int:
        """Delete all cache entries whose keys start with ``prefix``."""
        with self.store.transaction(immediate=True) as conn:
            return self.store.delete_cache_entries_by_prefix(conn, prefix)

    def sweep_expired(self) -> int:
        """Remove all expired cache rows as of current clock time."""
        now_iso = self._now_utc().isoformat()
        with self.store.transaction(immediate=True) as conn:
            return self.store.delete_expired_cache_entries(conn, now_utc_iso=now_iso)

    def purge_personal(self) -> tuple[int, int]:
        """Immediately purge cached personal user lists and first_observed rows on auth revoke."""
        return self.store.purge_personal_data()


class CachedYouTubeProvider:
    """Read-through TTL caching decorator implementing YouTubeProvider (FR-6.3, NFR-1, NFR-7)."""

    def __init__(
        self,
        upstream: YouTubeProvider,
        cache: MetadataCache,
        *,
        quota_guard: QuotaGuard | None = None,
        charge_on_miss: bool = False,
    ) -> None:
        self._upstream = upstream
        self.cache = cache
        self.quota_guard = quota_guard
        self.charge_on_miss = charge_on_miss
        self.stats = CacheStats()

    async def _call_upstream(
        self,
        operation: str,
        fn: Callable[[], Awaitable[_T]],
        *,
        count: int = 1,
    ) -> _T:
        cost = self.quota_guard.estimate(operation, count=count) if self.quota_guard else None
        if self.quota_guard is not None and cost is not None:
            self.quota_guard.preflight(cost)
        try:
            result = await fn()
        except ToolError as exc:
            if self.charge_on_miss and self.quota_guard is not None and cost is not None:
                self.quota_guard.charge(cost)
            if exc.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM and self.quota_guard is not None:
                self.quota_guard.mark_upstream_exhausted()
            raise
        if self.charge_on_miss and self.quota_guard is not None and cost is not None:
            self.quota_guard.charge(cost)
        return result

    async def get_videos_uncached(self, video_ids: Sequence[str]) -> list[VideoMeta]:
        """Bypass read cache to fetch fresh video status (used for FR-5.5 stale draft checks)."""
        self.stats.misses += 1
        videos = await self._call_upstream(
            "videos.list",
            lambda: self._upstream.get_videos(video_ids),
        )
        self.cache.put_many(
            [
                (make_cache_key("videos:item", v.video_id), "videos", _encode_video(v))
                for v in videos
            ]
        )
        return videos

    async def get_videos(self, video_ids: Sequence[str]) -> list[VideoMeta]:
        if len(video_ids) > 50:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "videos.list accepts at most 50 video IDs per call.",
            )
        unique_ids = list(dict.fromkeys(video_ids))
        key_for_id = {vid: make_cache_key("videos:item", vid) for vid in unique_ids}
        cached_raw = self.cache.get_many(list(key_for_id.values()))

        resolved: dict[str, VideoMeta] = {}
        missing_ids: list[str] = []
        for vid in unique_ids:
            raw_entry = cached_raw.get(key_for_id[vid])
            if isinstance(raw_entry, Mapping):
                resolved[vid] = _decode_video(raw_entry)
            else:
                missing_ids.append(vid)

        if not missing_ids:
            self.stats.hits += 1
            return [resolved[vid] for vid in video_ids if vid in resolved]

        self.stats.misses += 1
        fetched = await self._call_upstream(
            "videos.list",
            lambda: self._upstream.get_videos(missing_ids),
        )
        self.cache.put_many(
            [
                (
                    key_for_id.get(v.video_id, make_cache_key("videos:item", v.video_id)),
                    "videos",
                    _encode_video(v),
                )
                for v in fetched
            ]
        )
        for video in fetched:
            resolved[video.video_id] = video
        return [resolved[vid] for vid in video_ids if vid in resolved]

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
        cache_key = make_cache_key(
            "searches:videos",
            {
                "query": " ".join(query.strip().lower().split()),
                "max_results": max_results,
                "video_duration": video_duration,
                "relevance_language": relevance_language.lower() if relevance_language else None,
                "region_code": region_code.upper() if region_code else None,
                "page_token": page_token,
            },
        )
        cached = self.cache.get(cache_key)
        if isinstance(cached, list):
            self.stats.hits += 1
            return [_decode_search_hit(item) for item in cached]

        self.stats.misses += 1
        hits = await self._call_upstream(
            "search.list:videos",
            lambda: self._upstream.search_videos(
                query,
                max_results=max_results,
                video_duration=video_duration,
                relevance_language=relevance_language,
                region_code=region_code,
                page_token=page_token,
            ),
        )
        self.cache.put(cache_key, "searches", [_encode_search_hit(item) for item in hits])
        return hits

    async def search_channels(
        self,
        query: str,
        *,
        max_results: int = 25,
        relevance_language: str | None = None,
        page_token: str | None = None,
    ) -> list[SearchHit]:
        cache_key = make_cache_key(
            "searches:channels",
            {
                "query": " ".join(query.strip().lower().split()),
                "max_results": max_results,
                "relevance_language": relevance_language.lower() if relevance_language else None,
                "page_token": page_token,
            },
        )
        cached = self.cache.get(cache_key)
        if isinstance(cached, list):
            self.stats.hits += 1
            return [_decode_search_hit(item) for item in cached]

        self.stats.misses += 1
        hits = await self._call_upstream(
            "search.list:channels",
            lambda: self._upstream.search_channels(
                query,
                max_results=max_results,
                relevance_language=relevance_language,
                page_token=page_token,
            ),
        )
        self.cache.put(cache_key, "searches", [_encode_search_hit(item) for item in hits])
        return hits

    async def get_channels(self, channel_ids: Sequence[str]) -> list[ChannelMeta]:
        if len(channel_ids) > 50:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "channels.list accepts at most 50 channel IDs per call.",
            )
        unique_ids = list(dict.fromkeys(channel_ids))
        key_for_id = {cid: make_cache_key("channels:item", cid) for cid in unique_ids}
        cached_raw = self.cache.get_many(list(key_for_id.values()))

        resolved: dict[str, ChannelMeta] = {}
        missing_ids: list[str] = []
        for cid in unique_ids:
            raw_entry = cached_raw.get(key_for_id[cid])
            if isinstance(raw_entry, Mapping):
                resolved[cid] = _decode_channel(raw_entry)
            else:
                missing_ids.append(cid)

        if not missing_ids:
            self.stats.hits += 1
            return [resolved[cid] for cid in channel_ids if cid in resolved]

        self.stats.misses += 1
        fetched = await self._call_upstream(
            "channels.list",
            lambda: self._upstream.get_channels(missing_ids),
        )
        self.cache.put_many(
            [
                (
                    key_for_id.get(ch.channel_id, make_cache_key("channels:item", ch.channel_id)),
                    "channels",
                    _encode_channel(ch),
                )
                for ch in fetched
            ]
        )
        for channel in fetched:
            resolved[channel.channel_id] = channel
        return [resolved[cid] for cid in channel_ids if cid in resolved]

    async def get_channel_by_handle(self, handle: str) -> ChannelMeta | None:
        normalized = handle.strip().lstrip("@").lower()
        cache_key = make_cache_key("channels:handle", normalized)
        cached = self.cache.get(cache_key)
        if isinstance(cached, Mapping) and "found" in cached:
            self.stats.hits += 1
            raw_channel = cached["channel"]
            return _decode_channel(raw_channel) if raw_channel is not None else None

        self.stats.misses += 1
        channel = await self._call_upstream(
            "channels.list",
            lambda: self._upstream.get_channel_by_handle(handle),
        )
        self.cache.put(
            cache_key,
            "channels",
            {
                "found": channel is not None,
                "channel": _encode_channel(channel) if channel else None,
            },
        )
        return channel

    async def get_my_channel(self) -> ChannelMeta:
        cache_key = make_cache_key("user_lists:my_channel", "mine")
        cached = self.cache.get(cache_key)
        if isinstance(cached, Mapping):
            self.stats.hits += 1
            return _decode_channel(cached)

        self.stats.misses += 1
        channel = await self._call_upstream("channels.list", self._upstream.get_my_channel)
        self.cache.put(cache_key, "user_lists", _encode_channel(channel), is_personal=True)
        return channel

    async def list_subscriptions_mine(self, *, max_results: int = 50) -> list[UserEvent]:
        cache_key = make_cache_key("user_lists:subscriptions_mine", {"max_results": max_results})
        cached = self.cache.get(cache_key)
        if isinstance(cached, list):
            self.stats.hits += 1
            return [_decode_user_event(item) for item in cached]

        self.stats.misses += 1
        events = await self._call_upstream(
            "subscriptions.list",
            lambda: self._upstream.list_subscriptions_mine(max_results=max_results),
        )
        self.cache.put(
            cache_key,
            "user_lists",
            [_encode_user_event(item) for item in events],
            is_personal=True,
        )
        return events

    async def list_playlists_mine(self, *, max_results: int = 50) -> list[PlaylistSummary]:
        cache_key = make_cache_key("user_lists:playlists_mine", {"max_results": max_results})
        cached = self.cache.get(cache_key)
        if isinstance(cached, list):
            self.stats.hits += 1
            return [_decode_playlist_summary(item) for item in cached]

        self.stats.misses += 1
        playlists = await self._call_upstream(
            "playlists.list",
            lambda: self._upstream.list_playlists_mine(max_results=max_results),
        )
        self.cache.put(
            cache_key,
            "user_lists",
            [_encode_playlist_summary(item) for item in playlists],
            is_personal=True,
        )
        return playlists

    async def list_playlist_items(
        self,
        playlist_id: str,
        *,
        max_results: int = 50,
    ) -> list[UserEvent]:
        cache_key = make_cache_key(
            "user_lists:playlist_items",
            {"playlist_id": playlist_id, "max_results": max_results},
        )
        cached = self.cache.get(cache_key)
        if isinstance(cached, list):
            self.stats.hits += 1
            return [_decode_user_event(item) for item in cached]

        self.stats.misses += 1
        events = await self._call_upstream(
            "playlistItems.list",
            lambda: self._upstream.list_playlist_items(playlist_id, max_results=max_results),
        )
        self.cache.put(
            cache_key,
            "user_lists",
            [_encode_user_event(item) for item in events],
            is_personal=True,
        )
        return events

    async def list_liked_videos_rated(self, *, max_results: int = 50) -> list[VideoMeta]:
        cache_key = make_cache_key("user_lists:liked_rated", {"max_results": max_results})
        cached = self.cache.get(cache_key)
        if isinstance(cached, list):
            self.stats.hits += 1
            return [_decode_video(item) for item in cached]

        self.stats.misses += 1
        videos = await self._call_upstream(
            "videos.list:myRating",
            lambda: self._upstream.list_liked_videos_rated(max_results=max_results),
        )
        self.cache.put(
            cache_key,
            "user_lists",
            [_encode_video(item) for item in videos],
            is_personal=True,
        )
        return videos

    async def get_video_categories(self, *, region_code: str = "US") -> dict[str, str]:
        normalized_region = region_code.strip().upper()
        cache_key = make_cache_key("categories:region", normalized_region)
        cached = self.cache.get(cache_key)
        if isinstance(cached, Mapping):
            self.stats.hits += 1
            return {str(k): str(v) for k, v in cached.items()}

        self.stats.misses += 1
        categories = await self._call_upstream(
            "videoCategories.list",
            lambda: self._upstream.get_video_categories(region_code=region_code),
        )
        self.cache.put(cache_key, "categories", categories)
        return categories

    async def insert_playlist(
        self,
        *,
        title: str,
        description: str = "",
        privacy_status: Literal["private", "unlisted", "public"] = "private",
    ) -> CreatedPlaylist:
        created = await self._call_upstream(
            "playlists.insert",
            lambda: self._upstream.insert_playlist(
                title=title,
                description=description,
                privacy_status=privacy_status,
            ),
        )
        self.cache.invalidate_prefix("user_lists:playlists_mine:")
        return created

    async def insert_playlist_item(
        self,
        *,
        playlist_id: str,
        video_id: str,
        position: int | None = None,
    ) -> str:
        return await self._call_upstream(
            "playlistItems.insert",
            lambda: self._upstream.insert_playlist_item(
                playlist_id=playlist_id,
                video_id=video_id,
                position=position,
            ),
        )
