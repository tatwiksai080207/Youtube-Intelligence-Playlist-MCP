"""User signal event-time extraction and temporal interest profiling (TS-12, FR-3, FR-4)."""

from __future__ import annotations

from yt_intel_mcp.analysis.engagement import (
    TIMEFRAME_DAYS,
    VALID_TIMEFRAMES,
    WATCH_HISTORY_DISCLAIMER,
    DurationBucketStats,
    EngagementAnalysis,
    PeriodComparison,
    Timeframe,
    analyze_engagement_events,
    classify_duration_bucket,
)
from yt_intel_mcp.analysis.events import (
    TimestampCoverage,
    events_from_liked_videos,
    extract_event_time_from_record,
    normalize_user_event,
    normalize_user_events,
    summarize_timestamp_coverage,
)
from yt_intel_mcp.analysis.profile import (
    InterestProfile,
    WeightedUserEvent,
    build_interest_profile,
    compute_event_weight,
    deduplicate_events,
)
from yt_intel_mcp.analysis.recommend import (
    RecommendationResult,
    RecommendedVideo,
    score_recommendations,
)

__all__ = [
    "TIMEFRAME_DAYS",
    "VALID_TIMEFRAMES",
    "WATCH_HISTORY_DISCLAIMER",
    "DurationBucketStats",
    "EngagementAnalysis",
    "InterestProfile",
    "PeriodComparison",
    "RecommendationResult",
    "RecommendedVideo",
    "Timeframe",
    "TimestampCoverage",
    "WeightedUserEvent",
    "analyze_engagement_events",
    "build_interest_profile",
    "classify_duration_bucket",
    "compute_event_weight",
    "deduplicate_events",
    "events_from_liked_videos",
    "extract_event_time_from_record",
    "normalize_user_event",
    "normalize_user_events",
    "score_recommendations",
    "summarize_timestamp_coverage",
]
