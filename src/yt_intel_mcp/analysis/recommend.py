"""Objective recommendation scoring and attribution from user interest profiles (TS-13, FR-3.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from yt_intel_mcp.analysis.profile import InterestProfile
from yt_intel_mcp.durations import format_duration
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.sanitize import (
    DEFAULT_MAX_TITLE_LENGTH,
    sanitize_single_line,
    sanitize_video_meta,
)
from yt_intel_mcp.similarity.text import (
    DEFAULT_DESCRIPTION_PREFIX_LENGTH,
    TfidfVectorizer,
    cosine_similarity,
    score_texts_cosine,
    shared_matched_terms,
    tokenize_tags,
    tokenize_text,
)

__all__ = [
    "RecommendationResult",
    "RecommendedVideo",
    "score_recommendations",
]

_MMR_LAMBDA = 0.85


@dataclass(frozen=True, slots=True)
class RecommendedVideo:
    """Single recommended video with objective score and human-readable reason."""

    video: VideoMeta
    score: float
    reason: str
    matched_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize recommendation using objective sanitized metadata only."""
        clean = sanitize_video_meta(self.video)
        clean_channel_title = sanitize_single_line(
            clean.channel_title, max_length=DEFAULT_MAX_TITLE_LENGTH
        )
        return {
            "video_id": clean.video_id,
            "title": clean.title,
            "channel_id": clean.channel_id,
            "channel_title": clean_channel_title,
            "category_id": clean.category_id,
            "category_name": clean.category_name,
            "duration_seconds": clean.duration_seconds,
            "duration_human": format_duration(clean.duration_seconds, live=False),
            "tags": list(clean.tags),
            "score": round(self.score, 6),
            "reason": self.reason,
            "matched_terms": list(self.matched_terms),
        }


@dataclass(frozen=True, slots=True)
class RecommendationResult:
    """Complete deterministic recommendation ranking output (FR-3.3)."""

    profile: InterestProfile
    recommendations: tuple[RecommendedVideo, ...]
    excluded_seen_count: int
    excluded_unavailable_count: int


def _is_available_non_live(video: VideoMeta) -> bool:
    if not video.is_available:
        return False
    if video.privacy_status.strip().lower() in {"private", "deleted"}:
        return False
    return video.live_broadcast_content.strip().lower() in {"", "none"}


def _build_reason(
    matched_terms: Sequence[str],
    *,
    category_match: bool,
    channel_match: bool,
    category_name: str | None,
    channel_title: str,
) -> str:
    if matched_terms:
        joined = ", ".join(matched_terms[:3])
        return f"Matches your interest in {joined}."
    if channel_match and channel_title:
        return f"From {channel_title}, matching channels in your library."
    if category_match and category_name:
        return f"Aligned with your interest in {category_name}."
    return "Aligned with your YouTube library interest profile."


def score_recommendations(
    profile: InterestProfile,
    candidates: Sequence[VideoMeta],
    *,
    max_results: int = 10,
) -> RecommendationResult:
    """Score, filter, and MMR-rerank candidates against an InterestProfile (INV-01, FR-3.3)."""
    if max_results <= 0:
        raise ValueError(f"max_results must be positive, got {max_results}.")

    seen_ids: set[str] = set()
    eligible: list[VideoMeta] = []
    excluded_seen = 0
    excluded_unavailable = 0

    for cand in candidates:
        if cand.video_id in seen_ids:
            continue
        seen_ids.add(cand.video_id)
        if cand.video_id in profile.excluded_video_ids:
            excluded_seen += 1
            continue
        if not _is_available_non_live(cand):
            excluded_unavailable += 1
            continue
        eligible.append(sanitize_video_meta(cand))

    if not eligible:
        return RecommendationResult(
            profile=profile,
            recommendations=(),
            excluded_seen_count=excluded_seen,
            excluded_unavailable_count=excluded_unavailable,
        )

    profile_tokens = profile.top_terms
    cand_docs = [
        (
            *tokenize_text(c.title),
            *tokenize_tags(c.tags),
            *tokenize_text(c.description, max_length=DEFAULT_DESCRIPTION_PREFIX_LENGTH),
        )
        for c in eligible
    ]

    cosine_scores = score_texts_cosine(profile_tokens, cand_docs)
    max_term_weight = max(profile.term_weights.values(), default=1.0) or 1.0
    max_cat_weight = max(profile.category_weights.values(), default=1.0) or 1.0
    max_chan_weight = max(profile.channel_weights.values(), default=1.0) or 1.0

    vectorizer = TfidfVectorizer().fit([profile_tokens, *cand_docs])
    cand_vecs = [vectorizer.transform(doc) for doc in cand_docs]

    scored: list[tuple[RecommendedVideo, Mapping[str, float]]] = []
    for idx, cand in enumerate(eligible):
        doc_set = set(cand_docs[idx])
        overlap_terms = shared_matched_terms(
            profile_tokens,
            cand_docs[idx],
            weights=profile.term_weights,
            limit=3,
        )
        weighted_overlap = sum(profile.term_weights.get(t, 0.0) for t in doc_set) / max(
            1.0, sum(profile.term_weights.get(t, 0.0) for t in profile_tokens)
        )
        cat_affinity = (
            profile.category_weights.get(cand.category_id, 0.0) / max_cat_weight
            if cand.category_id
            else 0.0
        )
        chan_affinity = (
            profile.channel_weights.get(cand.channel_id, 0.0) / max_chan_weight
            if cand.channel_id
            else 0.0
        )

        # Normalize blend cleanly into [0.0, 1.0].
        blended = min(
            1.0,
            max(
                0.0,
                0.55 * cosine_scores[idx]
                + 0.25 * min(1.0, weighted_overlap * (max_term_weight / max_term_weight))
                + 0.10 * cat_affinity
                + 0.10 * chan_affinity,
            ),
        )
        clean_channel_title = sanitize_single_line(
            cand.channel_title, max_length=DEFAULT_MAX_TITLE_LENGTH
        )
        reason = _build_reason(
            overlap_terms,
            category_match=cat_affinity > 0.0,
            channel_match=chan_affinity > 0.0,
            category_name=cand.category_name,
            channel_title=clean_channel_title,
        )
        scored.append(
            (
                RecommendedVideo(
                    video=cand,
                    score=blended,
                    reason=reason,
                    matched_terms=overlap_terms,
                ),
                cand_vecs[idx],
            )
        )

    remaining = list(range(len(scored)))
    selected: list[RecommendedVideo] = []
    selected_vecs: list[Mapping[str, float]] = []
    target_count = min(max_results, len(scored))

    while remaining and len(selected) < target_count:
        best_idx: int | None = None
        best_key: tuple[float, str] | None = None
        for r_idx in remaining:
            item, vec = scored[r_idx]
            if not selected_vecs:
                mmr = item.score
            else:
                max_sim = max(cosine_similarity(vec, s_vec) for s_vec in selected_vecs)
                mmr = _MMR_LAMBDA * item.score - (1.0 - _MMR_LAMBDA) * max_sim
            key = (-round(mmr, 12), item.video.video_id)
            if best_key is None or key < best_key:
                best_key = key
                best_idx = r_idx

        assert best_idx is not None
        remaining.remove(best_idx)
        chosen_item, chosen_vec = scored[best_idx]
        selected.append(chosen_item)
        selected_vecs.append(chosen_vec)

    return RecommendationResult(
        profile=profile,
        recommendations=tuple(selected),
        excluded_seen_count=excluded_seen,
        excluded_unavailable_count=excluded_unavailable,
    )
