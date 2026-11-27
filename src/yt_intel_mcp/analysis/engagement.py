"""Privacy-preserving engagement aggregates from explicit user signals (TS-14, FR-4.1..4.3)."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from yt_intel_mcp.analysis.events import (
    TimestampCoverage,
    normalize_user_events,
    summarize_timestamp_coverage,
)
from yt_intel_mcp.config import EngagementConfig
from yt_intel_mcp.models import EventTimeKind, UserEvent
from yt_intel_mcp.similarity.text import tokenize_tags, tokenize_text

__all__ = [
    "TIMEFRAME_DAYS",
    "VALID_TIMEFRAMES",
    "WATCH_HISTORY_DISCLAIMER",
    "DurationBucketStats",
    "EngagementAnalysis",
    "PeriodComparison",
    "Timeframe",
    "analyze_engagement_events",
    "classify_duration_bucket",
]

Timeframe = Literal["7d", "30d", "90d", "180d", "365d", "all"]
VALID_TIMEFRAMES: tuple[Timeframe, ...] = ("7d", "30d", "90d", "180d", "365d", "all")
TIMEFRAME_DAYS: dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "180d": 180,
    "365d": 365,
}
WATCH_HISTORY_DISCLAIMER = (
    "Aggregates reflect explicit YouTube library actions (likes, playlists, subscriptions) only; "
    "YouTube Data API v3 does not expose watch history."
)


@dataclass(frozen=True, slots=True)
class DurationBucketStats:
    """Duration distribution over non-live positive-duration videos (FR-4.1)."""

    short_count: int
    medium_count: int
    long_count: int
    excluded_live_or_zero_count: int
    median_seconds: float | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize duration bucket counts and median."""
        return {
            "short_under_4m": self.short_count,
            "medium_4m_to_20m": self.medium_count,
            "long_over_20m": self.long_count,
            "excluded_live_or_zero": self.excluded_live_or_zero_count,
            "median_seconds": self.median_seconds,
        }


@dataclass(frozen=True, slots=True)
class PeriodComparison:
    """Comparison against equal-length preceding UTC window (FR-4.2, INV-07, INV-08)."""

    status: str
    current_count: int
    previous_count: int | None
    percent_delta: float | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize period comparison result."""
        return {
            "status": self.status,
            "current_dated_events": self.current_count,
            "previous_dated_events": self.previous_count,
            "percent_delta": self.percent_delta,
        }


@dataclass(frozen=True, slots=True)
class EngagementAnalysis:
    """Aggregate-only engagement analytics payload without raw personal IDs (FR-4.3, NFR-7)."""

    timeframe: Timeframe
    cadence_status: str
    total_signals: int
    source_counts: dict[str, int]
    timestamp_coverage: TimestampCoverage
    duration_buckets: DurationBucketStats
    top_topics: tuple[dict[str, Any], ...]
    top_categories: tuple[dict[str, Any], ...]
    monthly_trends: tuple[dict[str, Any], ...]
    period_comparison: PeriodComparison
    watch_history_disclaimer: str = WATCH_HISTORY_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        """Serialize engagement aggregates without any raw personal identifiers."""
        return {
            "timeframe": self.timeframe,
            "cadence_status": self.cadence_status,
            "total_signals": self.total_signals,
            "source_counts": dict(self.source_counts),
            "timestamp_coverage": self.timestamp_coverage.to_dict(),
            "duration_buckets": self.duration_buckets.to_dict(),
            "top_topics": list(self.top_topics),
            "top_categories": list(self.top_categories),
            "monthly_trends": list(self.monthly_trends),
            "period_comparison": self.period_comparison.to_dict(),
            "watch_history_disclaimer": self.watch_history_disclaimer,
        }


def classify_duration_bucket(
    duration_seconds: int | None,
    *,
    config: EngagementConfig | None = None,
) -> Literal["short", "medium", "long", "excluded"]:
    """Classify duration into <240s, 240-1200s, >1200s, or excluded for live/0s/None."""
    if duration_seconds is None or duration_seconds <= 0:
        return "excluded"
    cfg = config or EngagementConfig()
    if duration_seconds < cfg.short_max_seconds:
        return "short"
    if duration_seconds <= cfg.medium_max_seconds:
        return "medium"
    return "long"


def _compute_duration_stats(
    events: Sequence[UserEvent],
    *,
    config: EngagementConfig,
) -> DurationBucketStats:
    short_count = 0
    medium_count = 0
    long_count = 0
    excluded_count = 0
    valid_durations: list[int] = []

    for ev in events:
        if ev.duration_seconds is None and ev.video_id is None:
            continue
        bucket = classify_duration_bucket(ev.duration_seconds, config=config)
        if bucket == "short":
            short_count += 1
            assert ev.duration_seconds is not None
            valid_durations.append(ev.duration_seconds)
        elif bucket == "medium":
            medium_count += 1
            assert ev.duration_seconds is not None
            valid_durations.append(ev.duration_seconds)
        elif bucket == "long":
            long_count += 1
            assert ev.duration_seconds is not None
            valid_durations.append(ev.duration_seconds)
        else:
            excluded_count += 1

    median_sec = float(statistics.median(valid_durations)) if valid_durations else None
    return DurationBucketStats(
        short_count=short_count,
        medium_count=medium_count,
        long_count=long_count,
        excluded_live_or_zero_count=excluded_count,
        median_seconds=median_sec,
    )


def _compute_period_comparison(
    dated_events: Sequence[UserEvent],
    *,
    timeframe: Timeframe,
    compare_with_previous_period: bool,
    now_utc: datetime,
    config: EngagementConfig,
) -> tuple[list[UserEvent], PeriodComparison]:
    if timeframe == "all":
        comp = PeriodComparison(
            status="not_applicable_for_all_timeframe",
            current_count=len(dated_events),
            previous_count=None,
            percent_delta=None,
        )
        return list(dated_events), comp

    window_days = TIMEFRAME_DAYS[timeframe]
    curr_start = now_utc - timedelta(days=window_days)
    prev_start = curr_start - timedelta(days=window_days)

    curr_events = [
        ev
        for ev in dated_events
        if ev.event_time is not None and curr_start < ev.event_time <= now_utc
    ]
    prev_events = [
        ev
        for ev in dated_events
        if ev.event_time is not None and prev_start < ev.event_time <= curr_start
    ]

    if not compare_with_previous_period:
        return curr_events, PeriodComparison(
            status="comparison_disabled",
            current_count=len(curr_events),
            previous_count=None,
            percent_delta=None,
        )

    curr_n = len(curr_events)
    prev_n = len(prev_events)
    if curr_n == 0 and prev_n == 0:
        status = "no_activity"
        delta: float | None = None
    elif prev_n == 0:
        status = "new_activity"
        delta = None
    elif curr_n < config.min_dated_events:
        status = "insufficient_dated_data"
        delta = None
    else:
        status = "compared"
        delta = round(((curr_n - prev_n) / prev_n) * 100.0, 2)

    return curr_events, PeriodComparison(
        status=status,
        current_count=curr_n,
        previous_count=prev_n,
        percent_delta=delta,
    )


def analyze_engagement_events(
    events: Sequence[UserEvent],
    *,
    timeframe: Timeframe = "90d",
    compare_with_previous_period: bool = True,
    category_names: Mapping[str, str] | None = None,
    now_utc: datetime | None = None,
    config: EngagementConfig | None = None,
) -> EngagementAnalysis:
    """Compute aggregate-only engagement statistics without raw personal IDs (FR-4.1..4.3)."""
    cfg = config or EngagementConfig()
    reference_now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    normalized = normalize_user_events(events, now_utc=reference_now)
    coverage = summarize_timestamp_coverage(normalized)

    dated_events = [
        ev
        for ev in normalized
        if ev.time_kind is EventTimeKind.DATED and ev.event_time is not None
    ]

    active_dated, comparison = _compute_period_comparison(
        dated_events,
        timeframe=timeframe,
        compare_with_previous_period=compare_with_previous_period,
        now_utc=reference_now,
        config=cfg,
    )

    cadence_status = (
        "sufficient_data"
        if len(active_dated) >= cfg.min_dated_events
        else "insufficient_dated_data"
    )

    # Monthly trends over active dated events ONLY (INV-08).
    monthly_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for ev in active_dated:
        assert ev.event_time is not None
        month_key = ev.event_time.astimezone(UTC).strftime("%Y-%m")
        monthly_counts[month_key][ev.source.value] += 1

    monthly_trends = tuple(
        {
            "month": month_key,
            "event_count": sum(counts.values()),
            "by_source": dict(sorted(counts.items())),
        }
        for month_key, counts in sorted(monthly_counts.items())
    )

    source_counter = Counter(ev.source.value for ev in normalized)
    duration_stats = _compute_duration_stats(normalized, config=cfg)

    topic_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    cat_map = category_names or {}

    for ev in normalized:
        tokens = set(tokenize_text(ev.title)) | set(tokenize_tags(ev.tags))
        for tok in tokens:
            topic_counter[tok] += 1
        if ev.category_id:
            label = cat_map.get(ev.category_id, f"Category {ev.category_id}")
            category_counter[label] += 1

    total_topic_mentions = max(1, sum(topic_counter.values()))
    top_topics = tuple(
        {
            "topic": topic,
            "count": count,
            "share": round(count / total_topic_mentions, 4),
        }
        for topic, count in sorted(topic_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    )

    total_cat_mentions = max(1, sum(category_counter.values()))
    top_categories = tuple(
        {
            "category": cat_label,
            "count": count,
            "share": round(count / total_cat_mentions, 4),
        }
        for cat_label, count in sorted(category_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    )

    return EngagementAnalysis(
        timeframe=timeframe,
        cadence_status=cadence_status,
        total_signals=len(normalized),
        source_counts=dict(sorted(source_counter.items())),
        timestamp_coverage=coverage,
        duration_buckets=duration_stats,
        top_topics=top_topics,
        top_categories=top_categories,
        monthly_trends=monthly_trends,
        period_comparison=comparison,
    )
