"""Objective metadata TF-IDF and cosine similarity package (TS-08, FR-1.2, FR-2.2)."""

from __future__ import annotations

from yt_intel_mcp.similarity.channels import (
    CHANNEL_SIMILARITY_FEATURES,
    ChannelProfile,
    ChannelSimilarityResult,
    RankedSimilarChannel,
    build_channel_profile,
    compute_topic_overlap,
    rank_similar_channels,
    resolve_channel_similarity_weights,
)
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
    "CHANNEL_SIMILARITY_FEATURES",
    "DEFAULT_DESCRIPTION_PREFIX_LENGTH",
    "ENGLISH_STOP_WORDS",
    "VIDEO_SIMILARITY_FEATURES",
    "ChannelProfile",
    "ChannelSimilarityResult",
    "RankedSimilarChannel",
    "RankedSimilarVideo",
    "SparseVector",
    "TfidfVectorizer",
    "VideoSimilarityResult",
    "build_channel_profile",
    "build_search_query",
    "compute_duration_similarity",
    "compute_topic_overlap",
    "cosine_similarity",
    "extract_key_terms",
    "is_eligible_candidate",
    "rank_similar_channels",
    "rank_similar_videos",
    "resolve_channel_similarity_weights",
    "resolve_video_similarity_weights",
    "score_texts_cosine",
    "shared_matched_terms",
    "tokenize_tags",
    "tokenize_text",
]
