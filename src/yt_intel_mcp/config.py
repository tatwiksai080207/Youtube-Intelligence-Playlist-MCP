"""Frozen application configuration dataclasses and loader matching SRS Section 5."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = [
    "AppConfig",
    "CacheConfig",
    "DraftConfig",
    "EngagementConfig",
    "LiveTestConfig",
    "PlaylistConfig",
    "ProfileConfig",
    "ProviderMode",
    "QuotaConfig",
    "ReliabilityConfig",
    "SimilarityConfig",
    "load_config",
]

ProviderMode = Literal["fixture", "live"]


@dataclass(frozen=True, slots=True)
class QuotaConfig:
    """Dual daily YouTube API budget and method cost settings (FR-6, C-2)."""

    daily_units_limit: int = 10_000
    daily_search_limit: int = 100
    reset_timezone: str = "America/Los_Angeles"
    list_unit_cost: int = 1
    search_call_cost: int = 1
    search_unit_cost: int = 0
    playlist_insert_unit_cost: int = 50
    playlist_item_insert_unit_cost: int = 50

    def __post_init__(self) -> None:
        if self.daily_units_limit <= 0:
            raise ValueError("daily_units_limit must be positive.")
        if self.daily_search_limit <= 0:
            raise ValueError("daily_search_limit must be positive.")
        if self.list_unit_cost < 0 or self.search_call_cost < 0:
            raise ValueError("Method costs must be non-negative.")
        if self.search_unit_cost not in (0, 100):
            raise ValueError("search_unit_cost must be 0 or 100.")
        try:
            ZoneInfo(self.reset_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown reset timezone: {self.reset_timezone}") from exc


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """SQLite metadata cache TTL settings in seconds (FR-6.3, SRS Section 5)."""

    videos_ttl_seconds: int = 86_400
    channels_ttl_seconds: int = 86_400
    searches_ttl_seconds: int = 21_600
    user_lists_ttl_seconds: int = 900
    categories_ttl_seconds: int = 86_400


@dataclass(frozen=True, slots=True)
class DraftConfig:
    """Playlist confirmation draft expiry settings (FR-5.4)."""

    ttl_seconds: int = 600


@dataclass(frozen=True, slots=True)
class PlaylistConfig:
    """Playlist constraint solver and write defaults (FR-5.1, FR-5.1a)."""

    duration_tolerance_fraction: float = 0.05
    default_max_videos: int = 25
    default_privacy_status: Literal["private", "unlisted", "public"] = "private"
    allow_unknown_language: bool = False

    def __post_init__(self) -> None:
        if not 0.0 < self.duration_tolerance_fraction < 1.0:
            raise ValueError("duration_tolerance_fraction must be between 0 and 1.")
        if self.default_max_videos <= 0:
            raise ValueError("default_max_videos must be positive.")


@dataclass(frozen=True, slots=True)
class ProfileConfig:
    """Temporal decay and undated item settings for user profiling (FR-3.1, FR-3.2)."""

    half_life_days: float = 90.0
    undated_weight: float = 0.5


@dataclass(frozen=True, slots=True)
class EngagementConfig:
    """Duration bucket boundaries and minimum dated sample thresholds (FR-4.1, FR-4.2)."""

    min_dated_events: int = 5
    short_max_seconds: int = 240
    medium_max_seconds: int = 1200


@dataclass(frozen=True, slots=True)
class SimilarityConfig:
    """Configurable objective metadata weights pending ADR-0003 freeze (FR-1.2, FR-2.2, INV-01)."""

    title_weight: float = 0.35
    tags_weight: float = 0.25
    description_weight: float = 0.20
    category_weight: float = 0.10
    duration_weight: float = 0.10
    topics_weight: float = 0.25
    keywords_weight: float = 0.20


@dataclass(frozen=True, slots=True)
class ReliabilityConfig:
    """Retry bounds preserving non-idempotent write safety (NFR-8, INV-21)."""

    read_max_retries: int = 3
    write_max_retries: int = 0


@dataclass(frozen=True, slots=True)
class LiveTestConfig:
    """Hard per-run quota cap for opt-in live YouTube API tests (NFR-2)."""

    max_units: int = 300
    max_search_calls: int = 10


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Top-level configuration container for the yt-intel-mcp server."""

    provider_mode: ProviderMode = "fixture"
    data_dir: Path = field(default_factory=lambda: Path.home() / ".yt-intel-mcp")
    fixture_dir: Path = field(default_factory=lambda: Path("tests/fixtures"))
    quota: QuotaConfig = field(default_factory=QuotaConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    draft: DraftConfig = field(default_factory=DraftConfig)
    playlist: PlaylistConfig = field(default_factory=PlaylistConfig)
    profile: ProfileConfig = field(default_factory=ProfileConfig)
    engagement: EngagementConfig = field(default_factory=EngagementConfig)
    similarity: SimilarityConfig = field(default_factory=SimilarityConfig)
    reliability: ReliabilityConfig = field(default_factory=ReliabilityConfig)
    live_tests: LiveTestConfig = field(default_factory=LiveTestConfig)


def _parse_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {key} must be an integer, got {raw!r}.") from exc


def load_config(environ: Mapping[str, str] | None = None) -> AppConfig:
    """Load validated AppConfig from environment variables or process environment."""
    env = os.environ if environ is None else environ
    raw_mode = env.get("YT_INTEL_PROVIDER", "fixture").strip().lower()
    if raw_mode not in ("fixture", "live"):
        raise ValueError(f"YT_INTEL_PROVIDER must be 'fixture' or 'live', got {raw_mode!r}.")
    provider_mode: ProviderMode = "live" if raw_mode == "live" else "fixture"

    data_dir = (
        Path(env["YT_INTEL_DATA_DIR"])
        if env.get("YT_INTEL_DATA_DIR")
        else (Path.home() / ".yt-intel-mcp")
    )
    fixture_dir = (
        Path(env["YT_INTEL_FIXTURE_DIR"])
        if env.get("YT_INTEL_FIXTURE_DIR")
        else (Path("tests/fixtures"))
    )

    quota = QuotaConfig(
        daily_units_limit=_parse_int(env, "YT_INTEL_QUOTA_DAILY_UNITS", 10_000),
        daily_search_limit=_parse_int(env, "YT_INTEL_QUOTA_DAILY_SEARCHES", 100),
        search_unit_cost=_parse_int(env, "YT_INTEL_SEARCH_UNIT_COST", 0),
    )

    return AppConfig(
        provider_mode=provider_mode,
        data_dir=data_dir,
        fixture_dir=fixture_dir,
        quota=quota,
    )
