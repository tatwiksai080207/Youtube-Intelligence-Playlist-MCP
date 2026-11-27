"""Deterministic objective metadata similarity ranking for YouTube videos (TS-10, FR-1.2..1.3)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from yt_intel_mcp.config import SimilarityConfig
from yt_intel_mcp.durations import format_duration
from yt_intel_mcp.errors import ErrorCode, ToolError
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
    "VIDEO_SIMILARITY_FEATURES",
    "RankedSimilarVideo",
    "VideoSimilarityResult",
    "compute_duration_similarity",
    "is_eligible_candidate",
    "rank_similar_videos",
    "resolve_video_similarity_weights",
]

VIDEO_SIMILARITY_FEATURES: tuple[str, ...] = (
    "title",
    "tags",
    "description",
    "category",
    "duration",
)

_MMR_LAMBDA = 0.85


@dataclass(frozen=True, slots=True)
class RankedSimilarVideo:
    """Single ranked candidate video with per-feature similarity breakdown."""

    video: VideoMeta
    score: float
    feature_scores: dict[str, float]
    matched_signals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize ranked video match using objective sanitized metadata only."""
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
            "feature_scores": {
                key: round(val, 6) for key, val in self.feature_scores.items()
            },
            "matched_signals": list(self.matched_signals),
        }


@dataclass(frozen=True, slots=True)
class VideoSimilarityResult:
    """Complete deterministic video similarity ranking output."""

    seed_video: VideoMeta
    active_weights: dict[str, float]
    ranked_videos: tuple[RankedSimilarVideo, ...]
    total_candidates_evaluated: int
    excluded_count: int


def resolve_video_similarity_weights(
    scoring_weights: Mapping[str, Any] | None = None,
    *,
    config: SimilarityConfig | None = None,
) -> dict[str, float]:
    """Validate and resolve objective video similarity feature weights (ADR-0003)."""
    cfg = config or SimilarityConfig()
    weights: dict[str, float] = {
        "title": float(cfg.title_weight),
        "tags": float(cfg.tags_weight),
        "description": float(cfg.description_weight),
        "category": float(cfg.category_weight),
        "duration": float(cfg.duration_weight),
    }

    if scoring_weights is not None:
        if not isinstance(scoring_weights, Mapping) or len(scoring_weights) == 0:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "scoring_weights must be a non-empty JSON object.",
                details={"field": "scoring_weights"},
            )
        for key, raw_val in scoring_weights.items():
            if key not in VIDEO_SIMILARITY_FEATURES:
                raise ToolError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"Unknown scoring_weights feature {key!r}.",
                    details={"field": f"scoring_weights.{key}"},
                )
            if isinstance(raw_val, bool) or not isinstance(raw_val, int | float):
                raise ToolError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"scoring_weights.{key} must be a number in [0.0, 1.0].",
                    details={"field": f"scoring_weights.{key}"},
                )
            val = float(raw_val)
            if not math.isfinite(val) or val < 0.0 or val > 1.0:
                raise ToolError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"scoring_weights.{key} must be between 0.0 and 1.0.",
                    details={"field": f"scoring_weights.{key}"},
                )
            weights[key] = val

    if sum(weights.values()) <= 0.0:
        raise ToolError(
            ErrorCode.INVALID_ARGUMENT,
            "At least one scoring weight must be greater than 0.0.",
            details={"field": "scoring_weights"},
        )
    return weights


def is_eligible_candidate(video: VideoMeta, *, seed_video_id: str) -> bool:
    """Return True if candidate is public, available, non-live, and not the seed video."""
    if video.video_id == seed_video_id:
        return False
    if not video.is_available:
        return False
    if video.privacy_status.strip().lower() in {"private", "deleted"}:
        return False
    return video.live_broadcast_content.strip().lower() in {"", "none"}


def compute_duration_similarity(
    seed_seconds: int | None,
    candidate_seconds: int | None,
) -> float:
    """Compute bounded relative duration closeness in `[0.0, 1.0]` (ADR-0003)."""
    if (
        seed_seconds is None
        or candidate_seconds is None
        or seed_seconds <= 0
        or candidate_seconds <= 0
    ):
        return 0.0
    denom = max(seed_seconds, candidate_seconds, 1)
    return max(0.0, min(1.0, 1.0 - abs(seed_seconds - candidate_seconds) / denom))


def _redistribute_active_weights(
    raw_weights: Mapping[str, float],
    active_flags: Mapping[str, bool],
) -> dict[str, float]:
    """Drop inactive seed features and renormalize active weights to sum to 1.0."""
    active_sum = sum(
        raw_weights[feat] for feat in VIDEO_SIMILARITY_FEATURES if active_flags[feat]
    )
    if active_sum <= 0.0:
        active_feats = [feat for feat in VIDEO_SIMILARITY_FEATURES if active_flags[feat]]
        if not active_feats:
            return {feat: 0.0 for feat in VIDEO_SIMILARITY_FEATURES}
        uniform = 1.0 / len(active_feats)
        return {
            feat: (uniform if active_flags[feat] else 0.0) for feat in VIDEO_SIMILARITY_FEATURES
        }
    return {
        feat: (raw_weights[feat] / active_sum if active_flags[feat] else 0.0)
        for feat in VIDEO_SIMILARITY_FEATURES
    }


def rank_similar_videos(
    seed_video: VideoMeta,
    candidates: Sequence[VideoMeta],
    *,
    weights: Mapping[str, float] | None = None,
    max_results: int = 10,
    similarity_config: SimilarityConfig | None = None,
) -> VideoSimilarityResult:
    """Score and MMR-rerank eligible candidate videos using objective metadata only."""
    if max_results <= 0:
        raise ValueError(f"max_results must be positive, got {max_results}.")

    raw_weights = (
        dict(weights)
        if weights is not None
        else resolve_video_similarity_weights(config=similarity_config)
    )

    clean_seed = sanitize_video_meta(seed_video)
    eligible: list[VideoMeta] = []
    seen_ids: set[str] = set()
    excluded_count = 0

    for cand in candidates:
        if cand.video_id in seen_ids:
            continue
        seen_ids.add(cand.video_id)
        if not is_eligible_candidate(cand, seed_video_id=clean_seed.video_id):
            excluded_count += 1
            continue
        eligible.append(sanitize_video_meta(cand))

    seed_title_tokens = tokenize_text(clean_seed.title)
    seed_tag_tokens = tokenize_tags(clean_seed.tags)
    seed_desc_tokens = tokenize_text(
        clean_seed.description, max_length=DEFAULT_DESCRIPTION_PREFIX_LENGTH
    )
    seed_cat = (clean_seed.category_id or "").strip()

    active_flags = {
        "title": bool(seed_title_tokens),
        "tags": bool(seed_tag_tokens),
        "description": bool(seed_desc_tokens),
        "category": bool(seed_cat),
        "duration": clean_seed.duration_seconds is not None and clean_seed.duration_seconds > 0,
    }
    active_weights = _redistribute_active_weights(raw_weights, active_flags)

    if not eligible:
        return VideoSimilarityResult(
            seed_video=clean_seed,
            active_weights=active_weights,
            ranked_videos=(),
            total_candidates_evaluated=0,
            excluded_count=excluded_count,
        )

    cand_titles = [tokenize_text(c.title) for c in eligible]
    cand_tags = [tokenize_tags(c.tags) for c in eligible]
    cand_descs = [
        tokenize_text(c.description, max_length=DEFAULT_DESCRIPTION_PREFIX_LENGTH)
        for c in eligible
    ]

    title_scores = score_texts_cosine(seed_title_tokens, cand_titles)
    tag_scores = score_texts_cosine(seed_tag_tokens, cand_tags)
    desc_scores = score_texts_cosine(seed_desc_tokens, cand_descs)

    seed_combined = (*seed_title_tokens, *seed_tag_tokens, *seed_desc_tokens)
    cand_combined = [
        (*t, *g, *d) for t, g, d in zip(cand_titles, cand_tags, cand_descs, strict=True)
    ]
    combined_vec = TfidfVectorizer().fit([seed_combined, *cand_combined])
    cand_vectors = [combined_vec.transform(doc) for doc in cand_combined]

    base_items: list[tuple[RankedSimilarVideo, dict[str, float]]] = []
    for idx, cand in enumerate(eligible):
        cand_cat = (cand.category_id or "").strip()
        cat_score = 1.0 if seed_cat and cand_cat and seed_cat == cand_cat else 0.0
        dur_score = compute_duration_similarity(
            clean_seed.duration_seconds, cand.duration_seconds
        )
        f_scores = {
            "title": title_scores[idx],
            "tags": tag_scores[idx],
            "description": desc_scores[idx],
            "category": cat_score,
            "duration": dur_score,
        }
        total_score = sum(
            active_weights[feat] * f_scores[feat] for feat in VIDEO_SIMILARITY_FEATURES
        )
        total_score = min(1.0, max(0.0, total_score))
        matched = shared_matched_terms(
            seed_combined,
            cand_combined[idx],
            weights=combined_vec.idf,
            limit=5,
        )
        ranked_item = RankedSimilarVideo(
            video=cand,
            score=total_score,
            feature_scores=f_scores,
            matched_signals=matched,
        )
        base_items.append((ranked_item, cand_vectors[idx]))

    # Deterministic MMR re-ranking (ADR-0003 Section 4).
    remaining = list(range(len(base_items)))
    selected: list[RankedSimilarVideo] = []
    selected_vecs: list[dict[str, float]] = []

    target_count = min(max_results, len(base_items))
    while remaining and len(selected) < target_count:
        best_idx: int | None = None
        best_key: tuple[float, str] | None = None
        for r_idx in remaining:
            item, vec = base_items[r_idx]
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
        chosen_item, chosen_vec = base_items[best_idx]
        selected.append(chosen_item)
        selected_vecs.append(chosen_vec)

    return VideoSimilarityResult(
        seed_video=clean_seed,
        active_weights=active_weights,
        ranked_videos=tuple(selected),
        total_candidates_evaluated=len(eligible),
        excluded_count=excluded_count,
    )
