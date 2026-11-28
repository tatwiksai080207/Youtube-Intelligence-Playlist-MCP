"""Unit tests for objective channel similarity ranking (UT_SIM, FR-2.2, INV-01)."""

# ruff: noqa: N802
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from yt_intel_mcp.models import ChannelMeta, EventSource, UserEvent
from yt_intel_mcp.similarity.channels import (
    build_channel_profile,
    compute_topic_overlap,
    rank_similar_channels,
)

FORBIDDEN_POPULARITY_AND_HTTP = {
    "httpx",
    "requests",
    "aiohttp",
    "google",
    "view_count",
    "like_count",
    "subscriber_count",
    "statistics",
}


def test_UT_SIM_channel_module_contains_no_subscriber_or_http_imports() -> None:
    src = Path("src/yt_intel_mcp/similarity/channels.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not (names & FORBIDDEN_POPULARITY_AND_HTTP)
    assert not (attrs & FORBIDDEN_POPULARITY_AND_HTTP)
    assert not hasattr(ChannelMeta(channel_id="UC_TEST_001", title="Test"), "subscriber_count")


def test_UT_SIM_channel_ranking_and_missing_topic_redistribution() -> None:
    assert compute_topic_overlap(
        ["https://en.wikipedia.org/wiki/Technology", "https://en.wikipedia.org/wiki/Python"],
        ["https://en.wikipedia.org/wiki/Technology"],
    ) == pytest.approx(0.5)

    seed = build_channel_profile(
        ChannelMeta(
            channel_id="UC_SEED_00000000000001",
            title="Systems Craft",
            description="Python asyncio and event loops.",
            topic_categories=(),
            keywords=("python", "asyncio"),
        ),
        [
            UserEvent(
                source=EventSource.PLAYLIST_ITEM,
                video_id="v1",
                title="Python Asyncio Internals",
                tags=("python", "asyncio"),
            )
        ],
    )
    cand_match = build_channel_profile(
        ChannelMeta(
            channel_id="UC_CAND_00000000000002",
            title="Code Mechanics",
            description="Asyncio concurrency and Python architecture.",
            keywords=("python", "asyncio"),
        ),
        [
            UserEvent(
                source=EventSource.PLAYLIST_ITEM,
                video_id="v2",
                title="Asyncio Concurrency Patterns",
                tags=("python", "asyncio"),
            )
        ],
    )
    cand_unrelated = build_channel_profile(
        ChannelMeta(
            channel_id="UC_CAND_00000000000003",
            title="Kitchen Lab",
            description="Sourdough fermentation.",
            keywords=("baking",),
        ),
        [
            UserEvent(
                source=EventSource.PLAYLIST_ITEM,
                video_id="v3",
                title="Sourdough Starter Guide",
                tags=("baking",),
            )
        ],
    )

    result = rank_similar_channels(seed, [cand_unrelated, cand_match], max_results=5)
    assert result.active_weights["topics"] == 0.0
    assert sum(result.active_weights.values()) == pytest.approx(1.0)
    assert result.ranked_channels[0].channel.channel_id == "UC_CAND_00000000000002"
    assert result.ranked_channels[0].score > result.ranked_channels[1].score
