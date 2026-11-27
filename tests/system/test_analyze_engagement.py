"""MCP system and privacy tests for analyze_engagement and youtube://user/context (ST_FR4)."""

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
from yt_intel_mcp.tools.analyze_engagement import (
    USER_CONTEXT_RESOURCE_URI,
    register_analyze_engagement,
)


def _write_test_fixtures(root: Path) -> Path:
    public = root / "public"
    synthetic = root / "synthetic"
    public.mkdir(parents=True)
    synthetic.mkdir(parents=True)

    videos = {
        "videos": [
            {
                "video_id": "likedVid001",
                "title": "Python Asyncio Event Loops",
                "channel_id": "UC_PRIV_CHANNEL_0001",
                "channel_title": "Systems Craft",
                "published_at": "2020-01-01T00:00:00Z",
                "tags": ["python", "asyncio"],
                "category_id": "28",
                "category_name": "Science & Technology",
                "duration_seconds": 600,
                "live_broadcast_content": "none",
                "privacy_status": "public",
                "is_available": True,
            }
        ]
    }
    user_payload = {
        "has_channel": True,
        "subscriptions": [
            {
                "source": "subscription",
                "time_kind": "dated",
                "event_time": "2026-11-20T12:00:00Z",
                "channel_id": "UC_PRIV_CHANNEL_0001",
                "title": "Systems Craft",
                "tags": ["python", "systems"],
            }
        ],
        "playlists": [
            {
                "playlist_id": "PL_PRIV_0001",
                "title": "Study Queue",
                "item_count": 2,
            }
        ],
        "playlist_items": {
            "PL_PRIV_0001": [
                {
                    "source": "playlist_item",
                    "time_kind": "dated",
                    "event_time": "2026-11-22T12:00:00Z",
                    "video_id": "savedVid002",
                    "channel_id": "UC_PRIV_CHANNEL_0001",
                    "playlist_id": "PL_PRIV_0001",
                    "title": "Asyncio Coroutines",
                    "category_id": "28",
                    "duration_seconds": 239,
                    "tags": ["python"],
                },
                {
                    "source": "playlist_item",
                    "time_kind": "dated",
                    "event_time": "2026-11-23T12:00:00Z",
                    "video_id": "savedVid003",
                    "channel_id": "UC_PRIV_CHANNEL_0001",
                    "playlist_id": "PL_PRIV_0001",
                    "title": "SQLite WAL",
                    "category_id": "28",
                    "duration_seconds": 1201,
                    "tags": ["sqlite"],
                },
            ]
        },
        "liked_videos_rated": ["likedVid001"],
    }

    (public / "videos.json").write_text(json.dumps(videos), encoding="utf-8")
    (public / "channels.json").write_text(json.dumps({"channels": []}), encoding="utf-8")
    (public / "searches.json").write_text(
        json.dumps({"video_queries": {}, "channel_queries": {}}),
        encoding="utf-8",
    )
    (public / "categories.json").write_text(
        json.dumps({"US": {"28": "Science & Technology"}}),
        encoding="utf-8",
    )
    (synthetic / "default_user.json").write_text(json.dumps(user_payload), encoding="utf-8")
    return root


def test_ST_FR4_and_SEC_PII_analyze_engagement_and_user_context_resource(
    tmp_path: Path,
) -> None:
    fixture_dir = _write_test_fixtures(tmp_path / "fixtures")
    store = SQLiteStore(tmp_path / "quota.db")
    ledger = PersistentQuotaLedger(store, config=QuotaConfig())
    provider = FixtureYouTubeProvider(fixture_dir, quota_guard=ledger)
    server = create_server()
    register_analyze_engagement(server, provider=provider, quota_guard=ledger, store=store)

    async def _run() -> None:
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

                    res = await session.call_tool(
                        "analyze_engagement",
                        {"timeframe": "all", "compare_with_previous_period": True},
                    )
                    assert res.is_error is False
                    payload: dict[str, Any] = dict(res.structured_content or {})
                    assert payload["quota_used"]["search_calls"] == 0
                    data = payload["data"]
                    assert data["total_signals"] == 4
                    assert "watch history" in data["watch_history_disclaimer"].lower()
                    assert data["period_comparison"]["status"] == "not_applicable_for_all_timeframe"

                    # SEC_PII: raw personal IDs MUST NEVER appear in aggregate responses.
                    serialized_tool = json.dumps(payload)
                    forbidden_ids = (
                        "likedVid001",
                        "savedVid002",
                        "savedVid003",
                        "UC_PRIV_CHANNEL_0001",
                        "PL_PRIV_0001",
                    )
                    for raw_id in forbidden_ids:
                        assert raw_id not in serialized_tool

                    # Read youtube://user/context resource.
                    res_list = await session.list_resources()
                    uris = {str(item.uri) for item in res_list.resources}
                    assert USER_CONTEXT_RESOURCE_URI in uris

                    read_res = await session.read_resource(USER_CONTEXT_RESOURCE_URI)
                    ctx_text = read_res.contents[0].text
                    ctx_json = json.loads(ctx_text)
                    assert ctx_json["total_signals"] == 4
                    for raw_id in forbidden_ids:
                        assert raw_id not in ctx_text

                    # Invalid timeframe rejected pre-quota.
                    bad = await session.call_tool("analyze_engagement", {"timeframe": "10y"})
                    assert bad.is_error is True
                    bad_payload = dict(bad.structured_content or {})
                    assert bad_payload["code"] == "INVALID_ARGUMENT"

                    tg.cancel_scope.cancel()

    anyio.run(_run)
