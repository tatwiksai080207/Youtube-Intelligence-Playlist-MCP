"""MCP system and negative tests for get_recommendations (ST_FR3, NT_SIG, FR-3.3, INV-06)."""

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
from yt_intel_mcp.server import create_base_server
from yt_intel_mcp.store import SQLiteStore
from yt_intel_mcp.tools.get_recommendations import register_get_recommendations

FORBIDDEN_POPULARITY_KEYS = {
    "view_count",
    "viewCount",
    "like_count",
    "likeCount",
    "subscriber_count",
    "subscriberCount",
    "statistics",
}


def _write_test_fixtures(root: Path, *, empty_user: bool = False) -> Path:
    public = root / "public"
    synthetic = root / "synthetic"
    public.mkdir(parents=True)
    synthetic.mkdir(parents=True)

    videos = {
        "videos": [
            {
                "video_id": "likedVid001",
                "title": "Python Asyncio Event Loops",
                "description": "Coroutines and selectors.",
                "channel_id": "UC_PY_0000000000000001",
                "channel_title": "Systems Craft",
                "published_at": "2020-01-01T00:00:00Z",
                "tags": ["python", "asyncio"],
                "category_id": "28",
                "category_name": "Science & Technology",
                "duration_seconds": 600,
                "live_broadcast_content": "none",
                "privacy_status": "public",
                "is_available": True,
            },
            {
                "video_id": "savedVid002",
                "title": "Asyncio TaskGroup Patterns",
                "description": "Structured concurrency.",
                "channel_id": "UC_PY_0000000000000001",
                "channel_title": "Systems Craft",
                "published_at": "2026-08-01T00:00:00Z",
                "tags": ["python", "asyncio"],
                "category_id": "28",
                "category_name": "Science & Technology",
                "duration_seconds": 540,
                "live_broadcast_content": "none",
                "privacy_status": "public",
                "is_available": True,
            },
            {
                "video_id": "freshRec003",
                "title": "Python Asyncio Selectors Deep Dive",
                "description": "Event loop internals and non-blocking I/O.",
                "channel_id": "UC_PY_0000000000000002",
                "channel_title": "Code Mechanics",
                "published_at": "2026-10-01T00:00:00Z",
                "tags": ["python", "asyncio", "systems"],
                "category_id": "28",
                "category_name": "Science & Technology",
                "duration_seconds": 720,
                "live_broadcast_content": "none",
                "privacy_status": "public",
                "is_available": True,
            },
            {
                "video_id": "freshRec004",
                "title": "Asyncio Streams and Backpressure",
                "description": "Building reliable async network services in Python.",
                "channel_id": "UC_PY_0000000000000003",
                "channel_title": "Net Craft",
                "published_at": "2026-10-15T00:00:00Z",
                "tags": ["python", "asyncio"],
                "category_id": "28",
                "category_name": "Science & Technology",
                "duration_seconds": 480,
                "live_broadcast_content": "none",
                "privacy_status": "public",
                "is_available": True,
            },
        ]
    }
    searches = {
        "video_queries": {
            "asyncio python": ["likedVid001", "savedVid002", "freshRec003", "freshRec004"],
            "asyncio python loops": ["likedVid001", "savedVid002", "freshRec003", "freshRec004"],
            "asyncio loops python": ["likedVid001", "savedVid002", "freshRec003", "freshRec004"],
        },
        "channel_queries": {},
    }
    if empty_user:
        user_payload: dict[str, Any] = {
            "has_channel": True,
            "subscriptions": [],
            "playlists": [],
            "playlist_items": {},
            "liked_videos_rated": [],
        }
    else:
        user_payload = {
            "has_channel": True,
            "subscriptions": [
                {
                    "source": "subscription",
                    "time_kind": "dated",
                    "event_time": "2026-11-20T12:00:00Z",
                    "channel_id": "UC_PY_0000000000000001",
                    "title": "Python Asyncio Systems",
                    "tags": ["python", "asyncio"],
                }
            ],
            "playlists": [
                {
                    "playlist_id": "PL_TEST_001",
                    "title": "Asyncio Study",
                    "item_count": 1,
                }
            ],
            "playlist_items": {
                "PL_TEST_001": [
                    {
                        "source": "playlist_item",
                        "time_kind": "dated",
                        "event_time": "2026-11-22T12:00:00Z",
                        "video_id": "savedVid002",
                        "channel_id": "UC_PY_0000000000000001",
                        "playlist_id": "PL_TEST_001",
                        "title": "Asyncio TaskGroup Patterns",
                        "category_id": "28",
                        "tags": ["python", "asyncio"],
                    }
                ]
            },
            "liked_videos_rated": ["likedVid001"],
        }

    (public / "videos.json").write_text(json.dumps(videos), encoding="utf-8")
    (public / "channels.json").write_text(json.dumps({"channels": []}), encoding="utf-8")
    (public / "searches.json").write_text(json.dumps(searches), encoding="utf-8")
    (public / "categories.json").write_text(json.dumps({"US": {"28": "SciTech"}}), encoding="utf-8")
    (synthetic / "default_user.json").write_text(json.dumps(user_payload), encoding="utf-8")
    return root


async def _call_get_recommendations(
    fixture_dir: Path,
    db_path: Path,
    arguments: dict[str, Any],
    *,
    quota_config: QuotaConfig | None = None,
) -> tuple[bool, dict[str, Any]]:
    store = SQLiteStore(db_path)
    ledger = PersistentQuotaLedger(store, config=quota_config or QuotaConfig())
    provider = FixtureYouTubeProvider(fixture_dir, quota_guard=ledger)
    server = create_base_server()
    register_get_recommendations(server, provider=provider, quota_guard=ledger, store=store)

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
                result = await session.call_tool("get_recommendations", arguments)
                tg.cancel_scope.cancel()
    assert result.structured_content is not None
    return result.is_error, dict(result.structured_content)


def test_ST_FR3_get_recommendations_excludes_seen_and_stays_within_budget(
    tmp_path: Path,
) -> None:
    fixture_dir = _write_test_fixtures(tmp_path / "fixtures")

    async def _run() -> None:
        is_err, payload = await _call_get_recommendations(
            fixture_dir,
            tmp_path / "quota.db",
            {"max_results": 5},
        )
        assert is_err is False
        assert payload["quota_used"]["search_calls"] <= 3
        assert payload["quota_used"]["units"] <= 25

        data = payload["data"]
        recs = data["recommendations"]
        rec_ids = {item["video_id"] for item in recs}
        assert "likedVid001" not in rec_ids
        assert "savedVid002" not in rec_ids
        assert rec_ids == {"freshRec003", "freshRec004"}
        for item in recs:
            assert item["reason"]
        serialized = json.dumps(payload)
        for forbidden in FORBIDDEN_POPULARITY_KEYS:
            assert forbidden not in serialized

    anyio.run(_run)


def test_NT_SIG_get_recommendations_empty_signals_and_invalid_args(
    tmp_path: Path,
) -> None:
    empty_dir = _write_test_fixtures(tmp_path / "empty_fixtures", empty_user=True)

    async def _run() -> None:
        is_err, payload = await _call_get_recommendations(
            empty_dir,
            tmp_path / "q1.db",
            {"sources": ["liked_video", "subscription"]},
        )
        assert is_err is True
        assert payload["code"] == "INSUFFICIENT_USER_SIGNAL"

        is_err2, payload2 = await _call_get_recommendations(
            empty_dir,
            tmp_path / "q2.db",
            {"sources": ["watch_history"]},
        )
        assert is_err2 is True
        assert payload2["code"] == "INVALID_ARGUMENT"
        assert payload2["quota_used"] == {"units": 0, "search_calls": 0}

    anyio.run(_run)


@pytest.mark.parametrize("bad_max", [0, 51, True])
def test_NT_SIG_get_recommendations_rejects_invalid_max_results(
    tmp_path: Path,
    bad_max: Any,
) -> None:
    empty_dir = _write_test_fixtures(tmp_path / "fixtures", empty_user=True)

    async def _run() -> None:
        is_err, payload = await _call_get_recommendations(
            empty_dir,
            tmp_path / "q.db",
            {"max_results": bad_max},
        )
        assert is_err is True
        assert payload["code"] == "INVALID_ARGUMENT"
        assert payload["quota_used"] == {"units": 0, "search_calls": 0}

    anyio.run(_run)
