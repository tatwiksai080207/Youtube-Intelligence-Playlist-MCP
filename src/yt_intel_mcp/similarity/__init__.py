"""Objective metadata TF-IDF and cosine similarity package (TS-08, FR-1.2, FR-2.2)."""

from __future__ import annotations

from yt_intel_mcp.similarity.text import (
    DEFAULT_DESCRIPTION_PREFIX_LENGTH,
    ENGLISH_STOP_WORDS,
    SparseVector,
    TfidfVectorizer,
    build_search_query,
    cosine_similarity,
    extract_key_terms,
    score_texts_cosine,
    shared_matched_terms,
    tokenize_tags,
    tokenize_text,
)
from yt_intel_mcp.similarity.videos import (
    VIDEO_SIMILARITY_FEATURES,
    RankedSimilarVideo,
    VideoSimilarityResult,
    compute_duration_similarity,
    is_eligible_candidate,
    rank_similar_videos,
    resolve_video_similarity_weights,
)

__all__ = [
    "DEFAULT_DESCRIPTION_PREFIX_LENGTH",
    "ENGLISH_STOP_WORDS",
    "VIDEO_SIMILARITY_FEATURES",
    "RankedSimilarVideo",
    "SparseVector",
    "TfidfVectorizer",
    "VideoSimilarityResult",
    "build_search_query",
    "compute_duration_similarity",
    "cosine_similarity",
    "extract_key_terms",
    "is_eligible_candidate",
    "rank_similar_videos",
    "resolve_video_similarity_weights",
    "score_texts_cosine",
    "shared_matched_terms",
    "tokenize_tags",
    "tokenize_text",
]
