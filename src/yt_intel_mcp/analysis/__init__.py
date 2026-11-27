"""User signal event-time extraction and temporal interest profiling (TS-12, FR-3, FR-4)."""

from __future__ import annotations

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

__all__ = [
    "InterestProfile",
    "TimestampCoverage",
    "WeightedUserEvent",
    "build_interest_profile",
    "compute_event_weight",
    "deduplicate_events",
    "events_from_liked_videos",
    "extract_event_time_from_record",
    "normalize_user_event",
    "normalize_user_events",
    "summarize_timestamp_coverage",
]
