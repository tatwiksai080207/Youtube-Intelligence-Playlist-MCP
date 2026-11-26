"""Offline performance budget benchmarks under NFR-1 (X_PERF_SCORE)."""

# ruff: noqa: N802
from __future__ import annotations

import statistics
import time

from yt_intel_mcp.similarity import score_texts_cosine, tokenize_tags, tokenize_text


def test_X_PERF_SCORE_150_candidates_score_within_150ms() -> None:
    """Verify scoring 150 candidates across title, tags, and description completes in <= 150 ms."""
    topics = ("asyncio", "sqlite", "concurrency", "rust", "systems", "mcp", "consensus", "raft")
    seed_title = tokenize_text("Python Asyncio Internals and Structured Concurrency")
    seed_tags = tokenize_tags(["python", "asyncio", "concurrency", "systems"])
    seed_desc = tokenize_text(
        "Deep dive into coroutines, event loops, task scheduling, and backpressure controls."
    )

    cand_titles = [
        tokenize_text(f"Engineering {topics[i % len(topics)]} Architecture Part {i}")
        for i in range(150)
    ]
    cand_tags = [
        tokenize_tags([topics[i % len(topics)], topics[(i + 3) % len(topics)], "python"])
        for i in range(150)
    ]
    cand_descs = [
        tokenize_text(
            f"Detailed walkthrough on {topics[i % len(topics)]} patterns, testing, and invariants."
        )
        for i in range(150)
    ]

    def _run_batch() -> list[float]:
        t_scores = score_texts_cosine(seed_title, cand_titles)
        g_scores = score_texts_cosine(seed_tags, cand_tags)
        d_scores = score_texts_cosine(seed_desc, cand_descs)
        return [
            0.35 * t + 0.25 * g + 0.20 * d
            for t, g, d in zip(t_scores, g_scores, d_scores, strict=True)
        ]

    # Warm-up pass per docs/testing/test-plan.md Section 4 timing protocol.
    warm = _run_batch()
    assert len(warm) == 150

    durations_ms: list[float] = []
    for _ in range(5):
        start = time.perf_counter()
        result = _run_batch()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert len(result) == 150
        durations_ms.append(elapsed_ms)

    assert statistics.median(durations_ms) <= 150.0
    assert max(durations_ms) <= 150.0
