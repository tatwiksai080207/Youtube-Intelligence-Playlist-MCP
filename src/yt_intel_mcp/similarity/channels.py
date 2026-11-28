"""Deterministic objective metadata similarity ranking for YouTube channels (TS-11, FR-2.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from yt_intel_mcp.config import SimilarityConfig
from yt_intel_mcp.models import ChannelMeta, UserEvent
from yt_intel_mcp.sanitize import DEFAULT_MAX_TITLE_LENGTH, sanitize_single_line, sanitize_text
from yt_intel_mcp.similarity.text import (
    DEFAULT_DESCRIPTION_PREFIX_LENGTH,
    score_texts_cosine,
    shared_matched_terms,
    tokenize_tags,
    tokenize_text,
)

__all__ = [
    "CHANNEL_SIMILARITY_FEATURES",
    "ChannelProfile",
    "ChannelSimilarityResult",
    "RankedSimilarChannel",
    "build_channel_profile",
    "compute_topic_overlap",
    "rank_similar_channels",
    "resolve_channel_similarity_weights",
]

CHANNEL_SIMILARITY_FEATURES: tuple[str, ...] = (
    "topics",
    "keywords",
    "recent_uploads",
)
_MAX_RECENT_UPLOADS = 10


@dataclass(frozen=True, slots=True)
class ChannelProfile:
    """Objective channel metadata paired with up to 10 recent upload events (ADR-0003)."""

    channel: ChannelMeta
    recent_uploads: tuple[UserEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class RankedSimilarChannel:
    """Single ranked candidate channel with per-feature similarity breakdown."""

    channel: ChannelMeta
    score: float
    feature_scores: dict[str, float]
    matched_signals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize ranked channel match using objective sanitized metadata only."""
        clean_title = sanitize_single_line(
            self.channel.title, max_length=DEFAULT_MAX_TITLE_LENGTH
        )
        clean_desc = sanitize_text(
            self.channel.description, max_length=DEFAULT_DESCRIPTION_PREFIX_LENGTH
        )
        return {
            "channel_id": self.channel.channel_id,
            "title": clean_title,
            "custom_url": self.channel.custom_url,
            "description": clean_desc,
            "country": self.channel.country,
            "default_language": self.channel.default_language,
            "topic_categories": list(self.channel.topic_categories),
            "keywords": [
                cleaned
                for kw in self.channel.keywords
                if (cleaned := sanitize_single_line(kw, max_length=64))
            ],
            "score": round(self.score, 6),
            "feature_scores": {key: round(val, 6) for key, val in self.feature_scores.items()},
            "matched_signals": list(self.matched_signals),
        }


@dataclass(frozen=True, slots=True)
class ChannelSimilarityResult:
    """Complete deterministic channel similarity ranking output."""

    seed_channel: ChannelMeta
    active_weights: dict[str, float]
    ranked_channels: tuple[RankedSimilarChannel, ...]
    total_candidates_evaluated: int


def resolve_channel_similarity_weights(
    config: SimilarityConfig | None = None,
) -> dict[str, float]:
    """Resolve frozen ADR-0003 channel weights (topics 0.25, keywords 0.20, uploads 0.55)."""
    cfg = config or SimilarityConfig()
    topics_w = float(cfg.topics_weight)
    keywords_w = float(cfg.keywords_weight)
    uploads_w = max(0.0, 1.0 - topics_w - keywords_w)
    return {
        "topics": topics_w,
        "keywords": keywords_w,
        "recent_uploads": uploads_w,
    }


def _normalize_topic_slug(raw_topic: str) -> str:
    cleaned = raw_topic.strip().rstrip("/")
    if "/" in cleaned:
        cleaned = cleaned.rsplit("/", 1)[-1]
    return cleaned.replace("_", " ").strip().lower()


def compute_topic_overlap(
    seed_topics: Sequence[str],
    candidate_topics: Sequence[str],
) -> float:
    """Compute normalized topic overlap across Wikipedia topic identifiers."""
    seed_set = {slug for t in seed_topics if (slug := _normalize_topic_slug(t))}
    cand_set = {slug for t in candidate_topics if (slug := _normalize_topic_slug(t))}
    if not seed_set or not cand_set:
        return 0.0
    union = seed_set | cand_set
    return len(seed_set & cand_set) / len(union)


def build_channel_profile(
    channel: ChannelMeta,
    recent_uploads: Sequence[UserEvent] = (),
) -> ChannelProfile:
    """Build an objective ChannelProfile capped at 10 recent uploads (ADR-0003)."""
    return ChannelProfile(
        channel=channel,
        recent_uploads=tuple(recent_uploads[:_MAX_RECENT_UPLOADS]),
    )


def _channel_keyword_tokens(channel: ChannelMeta) -> tuple[str, ...]:
    return (
        *tokenize_text(channel.title),
        *tokenize_text(channel.description, max_length=DEFAULT_DESCRIPTION_PREFIX_LENGTH),
        *tokenize_tags(channel.keywords),
    )


def _channel_upload_tokens(uploads: Sequence[UserEvent]) -> tuple[str, ...]:
    tokens: list[str] = []
    for ev in uploads[:_MAX_RECENT_UPLOADS]:
        tokens.extend(tokenize_text(ev.title))
        tokens.extend(tokenize_tags(ev.tags))
    return tuple(tokens)


def _redistribute_channel_weights(
    raw_weights: Mapping[str, float],
    active_flags: Mapping[str, bool],
) -> dict[str, float]:
    active_sum = sum(
        raw_weights[feat] for feat in CHANNEL_SIMILARITY_FEATURES if active_flags[feat]
    )
    if active_sum <= 0.0:
        active_feats = [feat for feat in CHANNEL_SIMILARITY_FEATURES if active_flags[feat]]
        if not active_feats:
            return {feat: 0.0 for feat in CHANNEL_SIMILARITY_FEATURES}
        uniform = 1.0 / len(active_feats)
        return {
            feat: (uniform if active_flags[feat] else 0.0) for feat in CHANNEL_SIMILARITY_FEATURES
        }
    return {
        feat: (raw_weights[feat] / active_sum if active_flags[feat] else 0.0)
        for feat in CHANNEL_SIMILARITY_FEATURES
    }


def rank_similar_channels(
    seed_profile: ChannelProfile,
    candidate_profiles: Sequence[ChannelProfile],
    *,
    max_results: int = 10,
    similarity_config: SimilarityConfig | None = None,
) -> ChannelSimilarityResult:
    """Rank eligible candidate channels by objective metadata without subscriber counts."""
    if max_results <= 0:
        raise ValueError(f"max_results must be positive, got {max_results}.")

    raw_weights = resolve_channel_similarity_weights(config=similarity_config)
    seed_ch = seed_profile.channel

    eligible: list[ChannelProfile] = []
    seen_ids: set[str] = {seed_ch.channel_id}
    for prof in candidate_profiles:
        if prof.channel.channel_id in seen_ids:
            continue
        seen_ids.add(prof.channel.channel_id)
        eligible.append(prof)

    seed_topics = {slug for t in seed_ch.topic_categories if (slug := _normalize_topic_slug(t))}
    seed_kw_tokens = _channel_keyword_tokens(seed_ch)
    seed_upload_tokens = _channel_upload_tokens(seed_profile.recent_uploads)

    active_flags = {
        "topics": bool(seed_topics),
        "keywords": bool(seed_kw_tokens),
        "recent_uploads": bool(seed_upload_tokens),
    }
    active_weights = _redistribute_channel_weights(raw_weights, active_flags)

    if not eligible:
        return ChannelSimilarityResult(
            seed_channel=seed_ch,
            active_weights=active_weights,
            ranked_channels=(),
            total_candidates_evaluated=0,
        )

    cand_kw_docs = [_channel_keyword_tokens(p.channel) for p in eligible]
    cand_upload_docs = [_channel_upload_tokens(p.recent_uploads) for p in eligible]

    kw_scores = score_texts_cosine(seed_kw_tokens, cand_kw_docs)
    upload_scores = score_texts_cosine(seed_upload_tokens, cand_upload_docs)

    seed_combined = (*seed_kw_tokens, *seed_upload_tokens)
    ranked: list[RankedSimilarChannel] = []

    for idx, prof in enumerate(eligible):
        topic_score = compute_topic_overlap(
            seed_ch.topic_categories, prof.channel.topic_categories
        )
        f_scores = {
            "topics": topic_score,
            "keywords": kw_scores[idx],
            "recent_uploads": upload_scores[idx],
        }
        total_score = sum(
            active_weights[feat] * f_scores[feat] for feat in CHANNEL_SIMILARITY_FEATURES
        )
        total_score = min(1.0, max(0.0, total_score))
        cand_combined = (*cand_kw_docs[idx], *cand_upload_docs[idx])
        matched = shared_matched_terms(seed_combined, cand_combined, limit=5)
        ranked.append(
            RankedSimilarChannel(
                channel=prof.channel,
                score=total_score,
                feature_scores=f_scores,
                matched_signals=matched,
            )
        )

    ranked.sort(key=lambda item: (-round(item.score, 12), item.channel.channel_id))
    return ChannelSimilarityResult(
        seed_channel=seed_ch,
        active_weights=active_weights,
        ranked_channels=tuple(ranked[:max_results]),
        total_candidates_evaluated=len(eligible),
    )
