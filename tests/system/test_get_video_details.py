"""MCP system tests for get_video_details tool (TS-09, SK-1, SK-2, NFR-6, NFR-9)."""

# ruff: noqa: N802
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from yt_intel_mcp.config import QuotaConfig
from yt_intel_mcp.provider import FixtureYouTubeProvider
from yt_intel_mcp.quota.ledger import PersistentQuotaLedger
from yt_intel_mcp.server import create_server
from yt_intel_mcp.store import SQLiteStore
from yt_intel_mcp.tools.get_video_details import register_get_video_details

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

    videos = {
        "videos": [
            {
                "video_id": "dQw4w9WgXcQ",
                "title": "Python Asyncio\u200b Internals https://evil.example.com/phish",
                "description": (
                    "Deep dive into event loops. Visit https://evil.example.com\n"
                    "00:00 Event loop basics\n"
                    "05:30 - Task scheduling\n"
                    "[10:15] Cancellation & timeouts\n"
                ),
                "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
                "channel_title": "Systems Craft",
                "published_at": "2026-09-10T14:00:00Z",
                "tags": ["python", "asyncio", "https://spam.example.com"],
                "category_id": "28",
                "category_name": "Science & Technology",
                "duration_seconds": 620,
                "default_audio_language": "en",
                "default_language": "en",
                "live_broadcast_content": "none",
                "is_embeddable": True,
                "privacy_status": "public",
                "is_age_restricted": False,
                "is_available": True,
            },
            {
                "video_id": "liveVid0005",
                "title": "Live Systems Q&A",
                "description": "Ongoing live stream.",
                "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
                "channel_title": "Systems Craft",
                "published_at": "2026-11-26T10:00:00Z",
                "tags": ["live"],
                "category_id": "28",
                "category_name": "Science & Technology",
                "duration_seconds": 0,
                "default_audio_language": "en",
                "default_language": "en",
                "live_broadcast_content": "live",
                "is_embeddable": True,
                "privacy_status": "public",
                "is_age_restricted": False,
                "is_available": True,
            },
        ]
    }
    (public / "videos.json").write_text(json.dumps(videos), encoding="utf-8")
    (public / "channels.json").write_text(json.dumps({"channels": []}), encoding="utf-8")
    (public / "searches.json").write_text(
        json.dumps({"video_queries": {}, "channel_queries": {}}),
        encoding="utf-8",
    )
    (public / "categories.json").write_text(json.dumps({"US": {"28": "SciTech"}}), encoding="utf-8")
    (synthetic / "default_user.json").write_text(
        json.dumps({"has_channel": False, "subscriptions": [], "playlists": []}),
        encoding="utf-8",
    )
    return root


@pytest.mark.anyio
async def test_TS_09_mcp_get_video_details_returns_sanitized_metadata_and_chapters(
    tmp_path: Path,
) -> None:
    fixtures_dir = _write_test_fixtures(tmp_path / "fixtures")
    store = SQLiteStore(tmp_path / "yt_intel.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig())
    provider = FixtureYouTubeProvider(fixtures_dir, quota_guard=ledger)

    server = create_server()
    register_get_video_details(server, provider=provider, quota_guard=ledger)

    async with (
        create_client_server_memory_streams() as (client_streams, server_streams),
        anyio.create_task_group() as tg,
        ClientSession(client_streams[0], client_streams[1]) as session,
    ):
        tg.start_soon(
            server._lowlevel_server.run,
            server_streams[0],
            server_streams[1],
            server._lowlevel_server.create_initialization_options(),
        )
        await session.initialize()
        tools_res = await session.list_tools()
        tool_names = [t.name for t in tools_res.tools]
        assert "get_video_details" in tool_names

        res = await session.call_tool(
            "get_video_details",
            {"video_id": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert res.is_error is False
        payload: dict[str, Any] = dict(res.structured_content or {})
        assert payload["quota_used"] == {"units": 1, "search_calls": 0}
        assert "Summary based on video metadata, not on the video's content" in payload["summary"]
        data = payload["data"]
        assert data["video_id"] == "dQw4w9WgXcQ"
        assert "https://" not in data["title"]
        assert "\u200b" not in data["title"]
        assert "https://" not in data["description"]
        assert data["duration_seconds"] == 620
        assert data["duration_human"] == "10m 20s"
        assert data["duration_clock"] == "10:20"
        assert data["is_live"] is False
        assert data["default_audio_language"] == "en"
        assert data["chapters"] == [
            {"start_seconds": 0, "start_timestamp": "0:00", "title": "Event loop basics"},
            {"start_seconds": 330, "start_timestamp": "5:30", "title": "Task scheduling"},
            {
                "start_seconds": 615,
                "start_timestamp": "10:15",
                "title": "Cancellation & timeouts",
            },
        ]
        assert set(data).isdisjoint(FORBIDDEN_POPULARITY_KEYS)

        live_res = await session.call_tool("get_video_details", {"video_id": "liveVid0005"})
        assert live_res.is_error is False
        live_data = dict(live_res.structured_content or {})["data"]
        assert live_data["is_live"] is True
        assert live_data["duration_human"] == "Live"

        bad_res = await session.call_tool(
            "get_video_details",
            {"video_id": "dQw4w9WgXcQ", "extra_field": 1},
        )
        assert bad_res.is_error is True
        err = dict(bad_res.structured_content or {})
        assert err["code"] == "INVALID_ARGUMENT"
        assert err["quota_used"] == {"units": 0, "search_calls": 0}
        tg.cancel_scope.cancel()
