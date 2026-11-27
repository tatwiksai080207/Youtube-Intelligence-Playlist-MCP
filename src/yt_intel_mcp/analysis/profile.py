"""90-day half-life interest profile builder from explicit user signals (TS-12, FR-3.2, INV-05)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from yt_intel_mcp.analysis.events import (
    TimestampCoverage,
    normalize_user_events,
    summarize_timestamp_coverage,
)
from yt_intel_mcp.config import ProfileConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import EventSource, EventTimeKind, UserEvent
from yt_intel_mcp.similarity.text import tokenize_tags, tokenize_text

__all__ = [
    "InterestProfile",
    "WeightedUserEvent",
    "build_interest_profile",
    "compute_event_weight",
    "deduplicate_events",
]

_SECONDS_PER_DAY = 86_400.0


@dataclass(frozen=True, slots=True)
class WeightedUserEvent:
    """Deduplicated user event paired with its temporal decay weight and provenance."""

    event: UserEvent
    weight: float
    sources: tuple[EventSource, ...]


@dataclass(frozen=True, slots=True)
class InterestProfile:
    """Deterministic weighted user interest profile built from explicit signals (FR-3.2)."""

    weighted_events: tuple[WeightedUserEvent, ...]
    term_weights: dict[str, float]
    category_weights: dict[str, float]
    channel_weights: dict[str, float]
    top_terms: tuple[str, ...]
    search_queries: tuple[str, ...]
    excluded_video_ids: frozenset[str]
    coverage: TimestampCoverage


def compute_event_weight(
    event: UserEvent,
    *,
    now_utc: datetime,
    config: ProfileConfig | None = None,
) -> float:
    """Compute temporal weight using 90-day half-life for dated and 0.5 for undated (ADR-0007)."""
    cfg = config or ProfileConfig()
    if event.time_kind is EventTimeKind.DATED and event.event_time is not None:
        event_dt = (
            event.event_time.astimezone(UTC)
            if event.event_time.tzinfo is not None
            else event.event_time.replace(tzinfo=UTC)
        )
        now_dt = now_utc.astimezone(UTC) if now_utc.tzinfo is not None else now_utc.replace(tzinfo=UTC)
        age_days = max(0.0, (now_dt - event_dt).total_seconds() / _SECONDS_PER_DAY)
        return float(0.5 ** (age_days / cfg.half_life_days))

    return float(cfg.undated_weight)


def _dedup_key(event: UserEvent, index: int) -> tuple[str, str]:
    if event.video_id:
        return ("video", event.video_id)
    if event.channel_id:
        return ("channel", event.channel_id)
    return ("anon", str(index))


def deduplicate_events(
    events: Sequence[UserEvent],
    *,
    now_utc: datetime,
    config: ProfileConfig | None = None,
) -> list[WeightedUserEvent]:
    """Deduplicate overlapping items across sources using max recency weight (ADR-0007)."""
    grouped: dict[tuple[str, str], list[tuple[UserEvent, float]]] = defaultdict(list)
    for idx, ev in enumerate(events):
        weight = compute_event_weight(ev, now_utc=now_utc, config=config)
        grouped[_dedup_key(ev, idx)].append((ev, weight))

    deduped: list[WeightedUserEvent] = []
    for entries in grouped.values():
        best_event, best_weight = max(
            entries,
            key=lambda pair: (
                pair[1],
                1 if pair[0].time_kind is EventTimeKind.DATED else 0,
                pair[0].title,
            ),
        )
        sources: list[EventSource] = []
        for ev, _ in entries:
            if ev.source not in sources:
                sources.append(ev.source)
        deduped.append(
            WeightedUserEvent(
                event=best_event,
                weight=best_weight,
                sources=tuple(sources),
            )
        )

    deduped.sort(
        key=lambda item: (
            -item.weight,
            item.event.video_id or item.event.channel_id or "",
        )
    )
    return deduped


def _build_queries_from_terms(
    ranked_terms: Sequence[str],
    *,
    max_queries: int,
    terms_per_query: int = 3,
) -> tuple[str, ...]:
    if not ranked_terms or max_queries <= 0:
        return ()
    queries: list[str] = []
    for idx in range(0, len(ranked_terms), terms_per_query):
        chunk = ranked_terms[idx : idx + terms_per_query]
        if not chunk:
            break
        queries.append(" ".join(chunk))
        if len(queries) >= max_queries:
            break
    return tuple(queries)


def build_interest_profile(
    events: Sequence[UserEvent],
    *,
    now_utc: datetime | None = None,
    config: ProfileConfig | None = None,
    max_queries: int = 3,
    top_terms_limit: int = 15,
) -> InterestProfile:
    """Build a deterministic weighted interest profile from explicit user signals (FR-3.2)."""
    if not events:
        raise ToolError(
            ErrorCode.INSUFFICIENT_USER_SIGNAL,
            "No explicit YouTube library signals (likes, playlists, or subscriptions) were found.",
            details={"reason": "empty_user_signals"},
        )

    reference_now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    normalized = normalize_user_events(events, now_utc=reference_now)
    coverage = summarize_timestamp_coverage(normalized)
    weighted_events = deduplicate_events(normalized, now_utc=reference_now, config=config)

    term_scores: dict[str, float] = defaultdict(float)
    category_scores: dict[str, float] = defaultdict(float)
    channel_scores: dict[str, float] = defaultdict(float)
    excluded_videos: set[str] = set()

    for item in weighted_events:
        ev = item.event
        weight = item.weight

        if ev.video_id and any(
            src in (EventSource.LIKED_VIDEO, EventSource.PLAYLIST_ITEM) for src in item.sources
        ):
            excluded_videos.add(ev.video_id)

        if ev.category_id:
            category_scores[ev.category_id] += weight
        if ev.channel_id:
            channel_scores[ev.channel_id] += weight

        unique_tokens = set(tokenize_text(ev.title)) | set(tokenize_tags(ev.tags))
        for token in unique_tokens:
            term_scores[token] += weight

    sorted_terms = dict(sorted(term_scores.items(), key=lambda kv: (-kv[1], kv[0])))
    sorted_cats = dict(sorted(category_scores.items(), key=lambda kv: (-kv[1], kv[0])))
    sorted_channels = dict(sorted(channel_scores.items(), key=lambda kv: (-kv[1], kv[0])))

    top_terms = tuple(list(sorted_terms.keys())[:top_terms_limit])
    search_queries = _build_queries_from_terms(top_terms, max_queries=max_queries)

    return InterestProfile(
        weighted_events=tuple(weighted_events),
        term_weights=sorted_terms,
        category_weights=sorted_cats,
        channel_weights=sorted_channels,
        top_terms=top_terms,
        search_queries=search_queries,
        excluded_video_ids=frozenset(excluded_videos),
        coverage=coverage,
    )
