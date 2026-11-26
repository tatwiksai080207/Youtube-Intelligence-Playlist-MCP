"""Offline deterministic fixture YouTubeProvider implementation (FR-8.1, FR-8.2, TQ-5)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar

from yt_intel_mcp.config import AppConfig, QuotaConfig
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
    "FixtureCallRecord",
    "FixtureErrorRule",
    "FixtureYouTubeProvider",
    "InsertedPlaylistItem",
]

_DEFAULT_NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


@dataclass(slots=True)
class FixtureErrorRule:
    """Configurable fault injection rule for deterministic negative/integration tests."""

    reason: str | None = None
    http_status: int | None = None
    message: str | None = None
    after_calls: int = 0
    remaining_triggers: int | None = None
    charge_quota: bool = True
    details: dict[str, Any] | None = None

    def should_trigger(self, call_index_zero_based: int) -> bool:
        """Return True when this rule should raise on the current invocation."""
        if call_index_zero_based < self.after_calls:
            return False
        if self.remaining_triggers is None:
            return True
        if self.remaining_triggers <= 0:
            return False
        self.remaining_triggers -= 1
        return True


@dataclass(frozen=True, slots=True)
class FixtureCallRecord:
    """Audit record for a single FixtureYouTubeProvider invocation."""

    operation: str
    cost: CostEstimate
    succeeded: bool
    error_code: ErrorCode | None = None


@dataclass(frozen=True, slots=True)
class InsertedPlaylistItem:
    """Record of a simulated playlist item insertion."""

    item_id: str
    playlist_id: str
    video_id: str
    position: int | None


def _parse_datetime(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    if not isinstance(raw, str):
        raise ValueError(f"Expected ISO timestamp string, got {raw!r}.")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _parse_video(raw: Mapping[str, Any]) -> VideoMeta:
    duration_raw = raw.get("duration_seconds")
    duration = int(duration_raw) if duration_raw is not None else None
    return VideoMeta(
        video_id=str(raw["video_id"]),
        title=str(raw["title"]),
        description=str(raw.get("description", "")),
        channel_id=str(raw.get("channel_id", "")),
        channel_title=str(raw.get("channel_title", "")),
        published_at=_parse_datetime(raw.get("published_at")),
        tags=tuple(str(tag) for tag in raw.get("tags", ())),
        category_id=str(raw["category_id"]) if raw.get("category_id") is not None else None,
        category_name=str(raw["category_name"]) if raw.get("category_name") is not None else None,
        duration_seconds=duration,
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


def _parse_channel(raw: Mapping[str, Any]) -> ChannelMeta:
    return ChannelMeta(
        channel_id=str(raw["channel_id"]),
        title=str(raw["title"]),
        description=str(raw.get("description", "")),
        custom_url=str(raw["custom_url"]) if raw.get("custom_url") is not None else None,
        published_at=_parse_datetime(raw.get("published_at")),
        country=str(raw["country"]) if raw.get("country") is not None else None,
        default_language=(
            str(raw["default_language"]) if raw.get("default_language") is not None else None
        ),
        topic_categories=tuple(str(topic) for topic in raw.get("topic_categories", ())),
        keywords=tuple(str(kw) for kw in raw.get("keywords", ())),
        uploads_playlist_id=(
            str(raw["uploads_playlist_id"]) if raw.get("uploads_playlist_id") is not None else None
        ),
        likes_playlist_id=(
            str(raw["likes_playlist_id"]) if raw.get("likes_playlist_id") is not None else None
        ),
    )


def _parse_playlist_summary(raw: Mapping[str, Any]) -> PlaylistSummary:
    return PlaylistSummary(
        playlist_id=str(raw["playlist_id"]),
        title=str(raw["title"]),
        description=str(raw.get("description", "")),
        channel_id=str(raw.get("channel_id", "")),
        channel_title=str(raw.get("channel_title", "")),
        published_at=_parse_datetime(raw.get("published_at")),
        item_count=int(raw.get("item_count", 0)),
        privacy_status=str(raw.get("privacy_status", "private")),
    )


def _parse_user_event(raw: Mapping[str, Any]) -> UserEvent:
    duration_raw = raw.get("duration_seconds")
    duration = int(duration_raw) if duration_raw is not None else None
    return UserEvent(
        source=EventSource(str(raw["source"])),
        time_kind=EventTimeKind(str(raw.get("time_kind", "undated"))),
        event_time=_parse_datetime(raw.get("event_time")),
        video_id=str(raw["video_id"]) if raw.get("video_id") is not None else None,
        channel_id=str(raw["channel_id"]) if raw.get("channel_id") is not None else None,
        playlist_id=str(raw["playlist_id"]) if raw.get("playlist_id") is not None else None,
        title=str(raw.get("title", "")),
        category_id=str(raw["category_id"]) if raw.get("category_id") is not None else None,
        duration_seconds=duration,
        tags=tuple(str(tag) for tag in raw.get("tags", ())),
    )


def _coerce_rule(rule: FixtureErrorRule | str) -> FixtureErrorRule:
    if isinstance(rule, FixtureErrorRule):
        return rule
    return FixtureErrorRule(reason=rule)


def _duration_matches(
    duration_seconds: int | None,
    target: Literal["any", "short", "medium", "long"] | None,
) -> bool:
    if target is None or target == "any":
        return True
    if duration_seconds is None or duration_seconds <= 0:
        return False
    if target == "short":
        return duration_seconds < 240
    if target == "medium":
        return 240 <= duration_seconds <= 1200
    return duration_seconds > 1200


_T = TypeVar("_T")


def _slice_page(items: Sequence[_T], max_results: int, page_token: str | None) -> list[_T]:
    if max_results <= 0:
        return []
    offset = 0
    if page_token is not None and page_token != "":
        try:
            offset = max(0, int(page_token))
        except ValueError as exc:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Invalid page_token {page_token!r}.",
            ) from exc
    return list(items[offset : offset + max_results])


class FixtureYouTubeProvider:
    """In memory deterministic provider backed by scrubbed public and synthetic JSON fixtures."""

    def __init__(
        self,
        fixture_dir: Path | str | None = None,
        *,
        quota_guard: QuotaGuard | None = None,
        config: AppConfig | None = None,
        persona: str = "default_user",
        error_rules: Mapping[str, FixtureErrorRule | str] | None = None,
        insert_failures: Mapping[str, FixtureErrorRule | str] | None = None,
    ) -> None:
        base_config = config or AppConfig()
        self.fixture_dir: Path = Path(
            fixture_dir if fixture_dir is not None else base_config.fixture_dir
        )
        if not self.fixture_dir.is_dir():
            raise FileNotFoundError(f"Fixture directory not found: {self.fixture_dir}")

        self.quota_guard = quota_guard
        self.quota_config: QuotaConfig = base_config.quota
        self.persona = persona
        self._error_rules: dict[str, FixtureErrorRule] = {
            key: _coerce_rule(rule) for key, rule in (error_rules or {}).items()
        }
        self._insert_failures: dict[str, FixtureErrorRule] = {
            key: _coerce_rule(rule) for key, rule in (insert_failures or {}).items()
        }
        self._rule_attempts: dict[str, int] = {}

        self.calls: list[FixtureCallRecord] = []
        self.total_quota_used = QuotaUsed()
        self.created_playlists: list[CreatedPlaylist] = []
        self.inserted_items: list[InsertedPlaylistItem] = []

        self._videos: dict[str, VideoMeta] = {}
        self._channels: dict[str, ChannelMeta] = {}
        self._uploads: dict[str, list[str]] = {}
        self._categories: dict[str, dict[str, str]] = {}
        self._video_queries: dict[str, list[str]] = {}
        self._channel_queries: dict[str, list[str]] = {}

        self._has_channel: bool = True
        self._my_channel: ChannelMeta | None = None
        self._subscriptions: list[UserEvent] = []
        self._playlists: list[PlaylistSummary] = []
        self._playlist_items: dict[str, list[UserEvent]] = {}
        self._liked_videos_rated: list[VideoMeta] = []

        self._load_fixtures()

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        quota_guard: QuotaGuard | None = None,
        persona: str = "default_user",
        error_rules: Mapping[str, FixtureErrorRule | str] | None = None,
        insert_failures: Mapping[str, FixtureErrorRule | str] | None = None,
    ) -> FixtureYouTubeProvider:
        """Instantiate a FixtureYouTubeProvider from a validated AppConfig."""
        return cls(
            config.fixture_dir,
            quota_guard=quota_guard,
            config=config,
            persona=persona,
            error_rules=error_rules,
            insert_failures=insert_failures,
        )

    def _read_json(self, relative_path: str) -> dict[str, Any]:
        target = self.fixture_dir / relative_path
        if not target.is_file():
            raise FileNotFoundError(f"Required fixture file missing: {target}")
        decoded = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError(f"Fixture {target} must contain a JSON object.")
        return decoded

    def _load_fixtures(self) -> None:
        videos_data = self._read_json("public/videos.json")
        for item in videos_data.get("videos", []):
            video = _parse_video(item)
            self._videos[video.video_id] = video

        channels_data = self._read_json("public/channels.json")
        for item in channels_data.get("channels", []):
            channel = _parse_channel(item)
            self._channels[channel.channel_id] = channel
        for playlist_id, video_ids in channels_data.get("uploads", {}).items():
            self._uploads[str(playlist_id)] = [str(vid) for vid in video_ids]

        categories_data = self._read_json("public/categories.json")
        for region, mapping in categories_data.items():
            self._categories[str(region).upper()] = {
                str(cat_id): str(cat_name) for cat_id, cat_name in mapping.items()
            }

        searches_data = self._read_json("public/searches.json")
        for query_key, ids in searches_data.get("video_queries", {}).items():
            self._video_queries[str(query_key).strip().lower()] = [str(vid) for vid in ids]
        for query_key, ids in searches_data.get("channel_queries", {}).items():
            self._channel_queries[str(query_key).strip().lower()] = [str(cid) for cid in ids]

        user_data = self._read_json(f"synthetic/{self.persona}.json")
        self._has_channel = bool(user_data.get("has_channel", True))
        raw_channel = user_data.get("channel")
        self._my_channel = _parse_channel(raw_channel) if raw_channel is not None else None
        self._subscriptions = [_parse_user_event(ev) for ev in user_data.get("subscriptions", [])]
        self._playlists = [_parse_playlist_summary(pl) for pl in user_data.get("playlists", [])]
        for pl_id, events in user_data.get("playlist_items", {}).items():
            self._playlist_items[str(pl_id)] = [_parse_user_event(ev) for ev in events]
        for vid in user_data.get("liked_videos_rated", []):
            liked_video = self._videos.get(str(vid))
            if liked_video is not None:
                self._liked_videos_rated.append(liked_video)

    def set_error(self, key: str, rule: FixtureErrorRule | str) -> None:
        """Configure or replace an injected error rule for an operation or target key."""
        self._error_rules[key] = _coerce_rule(rule)

    def set_insert_failure(self, target: str, rule: FixtureErrorRule | str) -> None:
        """Configure simulated insert_playlist_item failure by video_id or 'pos:<idx>'."""
        self._insert_failures[target] = _coerce_rule(rule)

    def clear_errors(self) -> None:
        """Remove all configured error injection rules and reset attempt counters."""
        self._error_rules.clear()
        self._insert_failures.clear()
        self._rule_attempts.clear()

    def set_video_availability(
        self,
        video_id: str,
        *,
        is_available: bool,
        privacy_status: str | None = None,
    ) -> None:
        """Mutate a fixture video's availability in memory (for stale draft / negative tests)."""
        existing = self._videos.get(video_id)
        if existing is None:
            raise KeyError(f"Unknown fixture video_id: {video_id}")
        effective_privacy = (
            privacy_status if privacy_status is not None else existing.privacy_status
        )
        self._videos[video_id] = replace(
            existing,
            is_available=is_available,
            privacy_status=effective_privacy,
        )

    def _cost_for(self, operation: str) -> CostEstimate:
        if operation in ("search.list:videos", "search.list:channels"):
            return CostEstimate(
                units=self.quota_config.search_unit_cost,
                search_calls=self.quota_config.search_call_cost,
                operation=operation,
            )
        if operation == "playlists.insert":
            return CostEstimate(
                units=self.quota_config.playlist_insert_unit_cost,
                search_calls=0,
                operation=operation,
            )
        if operation == "playlistItems.insert":
            return CostEstimate(
                units=self.quota_config.playlist_item_insert_unit_cost,
                search_calls=0,
                operation=operation,
            )
        return CostEstimate(
            units=self.quota_config.list_unit_cost,
            search_calls=0,
            operation=operation,
        )

    def _charge(self, cost: CostEstimate) -> None:
        self.total_quota_used = self.total_quota_used + cost.to_quota_used()
        if self.quota_guard is not None:
            self.quota_guard.charge(cost)

    def _maybe_raise_rule(
        self,
        rule_keys: Sequence[str],
        *,
        operation: str,
        cost: CostEstimate,
    ) -> None:
        for key in rule_keys:
            rule = self._error_rules.get(key)
            if rule is None and key in self._insert_failures:
                rule = self._insert_failures[key]
            if rule is None:
                continue
            attempt = self._rule_attempts.get(key, 0)
            self._rule_attempts[key] = attempt + 1
            if not rule.should_trigger(attempt):
                continue
            if rule.charge_quota:
                self._charge(cost)
            err = map_upstream_error(
                rule.reason,
                http_status=rule.http_status,
                message=rule.message,
                details={"endpoint": operation, "injected_key": key, **(rule.details or {})},
                quota_used=cost.to_quota_used() if rule.charge_quota else QuotaUsed(),
            )
            if err.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM and self.quota_guard is not None:
                self.quota_guard.mark_upstream_exhausted()
            self.calls.append(
                FixtureCallRecord(
                    operation=operation,
                    cost=cost if rule.charge_quota else CostEstimate(units=0),
                    succeeded=False,
                    error_code=err.code,
                )
            )
            raise err

    def _record_success(self, operation: str, cost: CostEstimate) -> None:
        self._charge(cost)
        self.calls.append(FixtureCallRecord(operation=operation, cost=cost, succeeded=True))

    async def get_videos(self, video_ids: Sequence[str]) -> list[VideoMeta]:
        operation = "videos.list"
        cost = self._cost_for(operation)
        if len(video_ids) > 50:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "videos.list accepts at most 50 video IDs per call.",
            )
        self._maybe_raise_rule(["get_videos", operation], operation=operation, cost=cost)
        self._record_success(operation, cost)
        return [self._videos[vid] for vid in video_ids if vid in self._videos]

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
        del region_code
        operation = "search.list:videos"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(
            ["search_videos", "search.list", operation],
            operation=operation,
            cost=cost,
        )
        normalized = " ".join(query.strip().lower().split())
        candidate_ids = self._video_queries.get(normalized)
        if candidate_ids is None:
            tokens = [tok for tok in normalized.split() if tok]
            scored_ids: list[tuple[int, str]] = []
            for vid, video in self._videos.items():
                haystack = " ".join(
                    [
                        video.title.lower(),
                        video.description.lower(),
                        *(t.lower() for t in video.tags),
                    ]
                )
                overlap = sum(1 for tok in tokens if tok in haystack)
                if overlap > 0 or not tokens:
                    scored_ids.append((-overlap, vid))
            scored_ids.sort()
            candidate_ids = [vid for _, vid in scored_ids]

        lang_prefix = relevance_language.split("-")[0].lower() if relevance_language else None
        hits: list[SearchHit] = []
        for vid in candidate_ids:
            matched_video = self._videos.get(vid)
            if matched_video is None:
                continue
            if not _duration_matches(matched_video.duration_seconds, video_duration):
                continue
            if lang_prefix is not None:
                audio_lang = (matched_video.default_audio_language or "").split("-")[0].lower()
                if audio_lang != lang_prefix:
                    continue
            hits.append(
                SearchHit(
                    kind="video",
                    item_id=matched_video.video_id,
                    title=matched_video.title,
                    description=matched_video.description,
                    channel_id=matched_video.channel_id,
                    channel_title=matched_video.channel_title,
                    published_at=matched_video.published_at,
                    live_broadcast_content=matched_video.live_broadcast_content,
                )
            )
        self._record_success(operation, cost)
        return _slice_page(hits, max_results, page_token)

    async def search_channels(
        self,
        query: str,
        *,
        max_results: int = 25,
        relevance_language: str | None = None,
        page_token: str | None = None,
    ) -> list[SearchHit]:
        operation = "search.list:channels"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(
            ["search_channels", "search.list", operation],
            operation=operation,
            cost=cost,
        )
        normalized = " ".join(query.strip().lower().split())
        candidate_ids = self._channel_queries.get(normalized)
        if candidate_ids is None:
            tokens = [tok for tok in normalized.split() if tok]
            scored_ids: list[tuple[int, str]] = []
            for cid, channel in self._channels.items():
                haystack = " ".join(
                    [
                        channel.title.lower(),
                        channel.description.lower(),
                        *(kw.lower() for kw in channel.keywords),
                    ]
                )
                overlap = sum(1 for tok in tokens if tok in haystack)
                if overlap > 0 or not tokens:
                    scored_ids.append((-overlap, cid))
            scored_ids.sort()
            candidate_ids = [cid for _, cid in scored_ids]

        lang_prefix = relevance_language.split("-")[0].lower() if relevance_language else None
        hits: list[SearchHit] = []
        for cid in candidate_ids:
            matched_channel = self._channels.get(cid)
            if matched_channel is None:
                continue
            if lang_prefix is not None:
                ch_lang = (matched_channel.default_language or "").split("-")[0].lower()
                if ch_lang != lang_prefix:
                    continue
            hits.append(
                SearchHit(
                    kind="channel",
                    item_id=matched_channel.channel_id,
                    title=matched_channel.title,
                    description=matched_channel.description,
                    channel_id=matched_channel.channel_id,
                    channel_title=matched_channel.title,
                    published_at=matched_channel.published_at,
                )
            )
        self._record_success(operation, cost)
        return _slice_page(hits, max_results, page_token)

    async def get_channels(self, channel_ids: Sequence[str]) -> list[ChannelMeta]:
        operation = "channels.list"
        cost = self._cost_for(operation)
        if len(channel_ids) > 50:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "channels.list accepts at most 50 channel IDs per call.",
            )
        self._maybe_raise_rule(["get_channels", operation], operation=operation, cost=cost)
        self._record_success(operation, cost)
        return [self._channels[cid] for cid in channel_ids if cid in self._channels]

    async def get_channel_by_handle(self, handle: str) -> ChannelMeta | None:
        operation = "channels.list:forHandle"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(
            ["get_channel_by_handle", "channels.list", operation],
            operation=operation,
            cost=cost,
        )
        normalized = handle.strip().lstrip("@").lower()
        self._record_success(operation, cost)
        if not normalized:
            return None
        for channel in self._channels.values():
            if channel.custom_url and channel.custom_url.strip().lstrip("@").lower() == normalized:
                return channel
        return None

    async def get_my_channel(self) -> ChannelMeta:
        operation = "channels.list:mine"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(
            ["get_my_channel", "channels.list", operation],
            operation=operation,
            cost=cost,
        )
        if not self._has_channel or self._my_channel is None:
            self._charge(cost)
            err = map_upstream_error(
                "youtubeSignupRequired",
                http_status=403,
                message="The authenticated Google account does not have an active YouTube channel.",
                details={"endpoint": operation},
                quota_used=cost.to_quota_used(),
            )
            self.calls.append(
                FixtureCallRecord(
                    operation=operation,
                    cost=cost,
                    succeeded=False,
                    error_code=err.code,
                )
            )
            raise err
        self._record_success(operation, cost)
        return self._my_channel

    async def list_subscriptions_mine(self, *, max_results: int = 50) -> list[UserEvent]:
        operation = "subscriptions.list"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(
            ["list_subscriptions_mine", operation],
            operation=operation,
            cost=cost,
        )
        self._record_success(operation, cost)
        return list(self._subscriptions[:max_results])

    async def list_playlists_mine(self, *, max_results: int = 50) -> list[PlaylistSummary]:
        operation = "playlists.list"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(
            ["list_playlists_mine", operation],
            operation=operation,
            cost=cost,
        )
        self._record_success(operation, cost)
        return list(self._playlists[:max_results])

    async def list_playlist_items(
        self,
        playlist_id: str,
        *,
        max_results: int = 50,
    ) -> list[UserEvent]:
        operation = "playlistItems.list"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(
            [f"list_playlist_items:{playlist_id}", "list_playlist_items", operation],
            operation=operation,
            cost=cost,
        )
        self._record_success(operation, cost)
        if playlist_id in self._playlist_items:
            return list(self._playlist_items[playlist_id][:max_results])
        upload_video_ids = self._uploads.get(playlist_id, [])
        upload_events: list[UserEvent] = []
        for vid in upload_video_ids[:max_results]:
            video = self._videos.get(vid)
            if video is None:
                continue
            upload_events.append(
                UserEvent(
                    source=EventSource.PLAYLIST_ITEM,
                    time_kind=(
                        EventTimeKind.DATED
                        if video.published_at is not None
                        else EventTimeKind.UNDATED
                    ),
                    event_time=video.published_at,
                    video_id=video.video_id,
                    channel_id=video.channel_id,
                    playlist_id=playlist_id,
                    title=video.title,
                    category_id=video.category_id,
                    duration_seconds=video.duration_seconds,
                    tags=video.tags,
                )
            )
        return upload_events

    async def list_liked_videos_rated(self, *, max_results: int = 50) -> list[VideoMeta]:
        operation = "videos.list:myRating"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(
            ["list_liked_videos_rated", operation],
            operation=operation,
            cost=cost,
        )
        self._record_success(operation, cost)
        return list(self._liked_videos_rated[:max_results])

    async def get_video_categories(self, *, region_code: str = "US") -> dict[str, str]:
        operation = "videoCategories.list"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(
            ["get_video_categories", operation],
            operation=operation,
            cost=cost,
        )
        self._record_success(operation, cost)
        normalized = region_code.strip().upper()
        if normalized in self._categories:
            return dict(self._categories[normalized])
        return dict(self._categories.get("US", {}))

    async def insert_playlist(
        self,
        *,
        title: str,
        description: str = "",
        privacy_status: Literal["private", "unlisted", "public"] = "private",
    ) -> CreatedPlaylist:
        operation = "playlists.insert"
        cost = self._cost_for(operation)
        self._maybe_raise_rule(["insert_playlist", operation], operation=operation, cost=cost)
        if not self._has_channel or self._my_channel is None:
            self._charge(cost)
            err = map_upstream_error(
                "youtubeSignupRequired",
                http_status=403,
                message="A YouTube channel is required before creating playlists.",
                details={"endpoint": operation},
                quota_used=cost.to_quota_used(),
            )
            self.calls.append(
                FixtureCallRecord(
                    operation=operation,
                    cost=cost,
                    succeeded=False,
                    error_code=err.code,
                )
            )
            raise err
        self._record_success(operation, cost)
        index = len(self.created_playlists) + 1
        playlist_id = f"PL_FIXTURE_{index:03d}"
        created = CreatedPlaylist(
            playlist_id=playlist_id,
            title=title,
            description=description,
            privacy_status=privacy_status,
            channel_id=self._my_channel.channel_id,
            published_at=_DEFAULT_NOW,
            url=f"https://www.youtube.com/playlist?list={playlist_id}",
        )
        self.created_playlists.append(created)
        return created

    async def insert_playlist_item(
        self,
        *,
        playlist_id: str,
        video_id: str,
        position: int | None = None,
    ) -> str:
        operation = "playlistItems.insert"
        cost = self._cost_for(operation)
        item_pos = len(self.inserted_items)
        self._maybe_raise_rule(
            [
                f"insert_playlist_item:{video_id}",
                video_id,
                f"insert_playlist_item:pos:{item_pos}",
                f"pos:{item_pos}",
                "insert_playlist_item",
                operation,
            ],
            operation=operation,
            cost=cost,
        )
        self._record_success(operation, cost)
        item_id = f"PLI_FIXTURE_{item_pos + 1:04d}"
        self.inserted_items.append(
            InsertedPlaylistItem(
                item_id=item_id,
                playlist_id=playlist_id,
                video_id=video_id,
                position=position,
            )
        )
        return item_id
