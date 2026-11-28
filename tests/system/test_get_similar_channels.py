"""MCP system and negative tests for get_similar_channels (ST_FR2, FR-2.1, FR-2.2)."""

# ruff: noqa: N802
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from yt_intel_mcp.config import QuotaConfig
from yt_intel_mcp.provider import FixtureYouTubeProvider
from yt_intel_mcp.quota.ledger import PersistentQuotaLedger
from yt_intel_mcp.server import create_server
from yt_intel_mcp.store import SQLiteStore
from yt_intel_mcp.tools.get_similar_channels import register_get_similar_channels

FORBIDDEN_POPULARITY_KEYS = {
    "view_count",
    "viewCount",
    "like_count",
    "likeCount",
    "subscriber_count",
    "subscriberCount",
    "statistics",
}


def _write_test_fixtures(root: Path) -> Path:
    public = root / "public"
    synthetic = root / "synthetic"
    public.mkdir(parents=True)
    synthetic.mkdir(parents=True)

    channels = {
        "channels": [
            {
                "channel_id": "UC_SEED_TECH_00000000001",
                "title": "Systems Craft",
                "description": "Python asyncio and systems engineering.",
                "custom_url": "@systemscraft",
                "topic_categories": ["https://en.wikipedia.org/wiki/Technology"],
                "keywords": ["python", "asyncio", "systems"],
                "uploads_playlist_id": "UU_SEED_001",
            },
            {
                "channel_id": "UC_CAND_TECH_00000000002",
                "title": "Code Mechanics",
                "description": "Python concurrency and MCP architecture.",
                "custom_url": "@codemechanics",
                "topic_categories": ["https://en.wikipedia.org/wiki/Technology"],
                "keywords": ["python", "asyncio", "mcp"],
                "uploads_playlist_id": "UU_CAND_002",
            },
            {
                "channel_id": "UC_CAND_COOK_00000000003",
                "title": "Kitchen Lab",
                "description": "Sourdough bread baking.",
                "custom_url": "@kitchenlab",
                "topic_categories": ["https://en.wikipedia.org/wiki/Food"],
                "keywords": ["baking", "sourdough"],
                "uploads_playlist_id": "UU_CAND_003",
            },
        ],
        "uploads": {
            "UU_SEED_001": ["vidSeed0001"],
            "UU_CAND_002": ["vidCand0002"],
            "UU_CAND_003": ["vidCook0003"],
        },
    }
    videos = {
        "videos": [
            {
                "video_id": "vidSeed0001",
                "title": "Python Asyncio Event Loops",
                "channel_id": "UC_SEED_TECH_00000000001",
                "tags": ["python", "asyncio"],
                "duration_seconds": 600,
            },
            {
                "video_id": "vidCand0002",
                "title": "Async Concurrency in Python",
                "channel_id": "UC_CAND_TECH_00000000002",
                "tags": ["python", "asyncio"],
                "duration_seconds": 540,
            },
            {
                "video_id": "vidCook0003",
                "title": "Sourdough Starter Guide",
                "channel_id": "UC_CAND_COOK_00000000003",
                "tags": ["baking"],
                "duration_seconds": 480,
            },
        ]
    }
    searches = {
        "video_queries": {},
        "channel_queries": {
            "systems craft python asyncio": [
                "UC_SEED_TECH_00000000001",
                "UC_CAND_TECH_00000000002",
                "UC_CAND_COOK_00000000003",
            ]
        },
    }
    (public / "channels.json").write_text(json.dumps(channels), encoding="utf-8")
    (public / "videos.json").write_text(json.dumps(videos), encoding="utf-8")
    (public / "searches.json").write_text(json.dumps(searches), encoding="utf-8")
    (public / "categories.json").write_text(json.dumps({"US": {"28": "SciTech"}}), encoding="utf-8")
    (synthetic / "default_user.json").write_text(
        json.dumps({"has_channel": False, "subscriptions": [], "playlists": []}),
        encoding="utf-8",
    )
    return root


async def _call_get_similar_channels(
    fixture_dir: Path,
    db_path: Path,
    arguments: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    store = SQLiteStore(db_path)
    ledger = PersistentQuotaLedger(store, config=QuotaConfig())
    provider = FixtureYouTubeProvider(fixture_dir, quota_guard=ledger)
    server = create_server()
    register_get_similar_channels(server, provider=provider, quota_guard=ledger)

    async with create_client_server_memory_streams() as (client_streams, server_streams):
        read_c, write_c = client_streams
        read_s, write_s = server_streams
        async with anyio.create_task_group() as tg:
            tg.start_soon(
                server._lowlevel_server.run,
                read_s,
                write_s,
                server._lowlevel_server.create_initialization_options(),
            )
            async with ClientSession(read_c, write_c) as session:
                await session.initialize()
                result = await session.call_tool("get_similar_channels", arguments)
                tg.cancel_scope.cancel()
    assert result.structured_content is not None
    return result.is_error, dict(result.structured_content)


def test_ST_FR2_get_similar_channels_resolves_handle_and_ranks_without_subscribers(
    tmp_path: Path,
) -> None:
    fixture_dir = _write_test_fixtures(tmp_path / "fixtures")

    async def _run() -> None:
        is_err, payload = await _call_get_similar_channels(
            fixture_dir,
            tmp_path / "quota.db",
            {"channel": "https://www.youtube.com/@systemscraft", "max_results": 5},
        )
        assert is_err is False
        assert payload["quota_used"]["search_calls"] <= 1
        assert payload["quota_used"]["units"] <= 32

        data = payload["data"]
        assert data["seed_channel"]["channel_id"] == "UC_SEED_TECH_00000000001"
        results = data["results"]
        assert len(results) == 2
        assert results[0]["channel_id"] == "UC_CAND_TECH_00000000002"
        assert set(results[0]["feature_scores"]) == {"topics", "keywords", "recent_uploads"}
        serialized = json.dumps(payload)
        for forbidden in FORBIDDEN_POPULARITY_KEYS:
            assert forbidden not in serialized

        # G-01 Option A: nonexistent channel returns INVALID_ARGUMENT.
        is_err2, payload2 = await _call_get_similar_channels(
            fixture_dir,
            tmp_path / "q2.db",
            {"channel": "@nonexistent_handle_999"},
        )
        assert is_err2 is True
        assert payload2["code"] == "INVALID_ARGUMENT"

        # Invalid channel format rejected pre-quota.
        is_err3, payload3 = await _call_get_similar_channels(
            fixture_dir,
            tmp_path / "q3.db",
            {"channel": "not_a_channel"},
        )
        assert is_err3 is True
        assert payload3["code"] == "INVALID_ARGUMENT"
        assert payload3["quota_used"] == {"units": 0, "search_calls": 0}

    anyio.run(_run)
