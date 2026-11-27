"""MCP system and negative tests for get_similar_videos (ST_FR1, NT_VID, FR-1.1..1.4)."""

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
from yt_intel_mcp.tools.get_similar_videos import register_get_similar_videos

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
                "video_id": "seedPy00001",
                "title": "Python Asyncio Internals and Event Loops",
                "description": "Deep dive into coroutines, tasks, and structured concurrency.",
                "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
                "channel_title": "Systems Craft",
                "published_at": "2026-09-10T14:00:00Z",
                "tags": ["python", "asyncio", "concurrency", "systems"],
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
                "video_id": "candNoTag02",
                "title": "Async Concurrency Patterns in Python 3.11",
                "description": "TaskGroup cancellation, coroutines, and async iterators.",
                "channel_id": "UC_TECH_00000000000002",
                "channel_title": "Code Mechanics",
                "published_at": "2026-09-18T09:30:00Z",
                "tags": [],
                "category_id": "28",
                "category_name": "Science & Technology",
                "duration_seconds": 540,
                "default_audio_language": "en-US",
                "default_language": "en",
                "live_broadcast_content": "none",
                "is_embeddable": True,
                "privacy_status": "public",
                "is_age_restricted": False,
                "is_available": True,
            },
            {
                "video_id": "candOther03",
                "title": "SQLite WAL Mode in Three Minutes",
                "description": "Quick walkthrough of write-ahead logging.",
                "channel_id": "UC_TECH_00000000000003",
                "channel_title": "Storage Foundry",
                "published_at": "2026-10-05T11:15:00Z",
                "tags": ["sqlite", "database"],
                "category_id": "27",
                "category_name": "Education",
                "duration_seconds": 195,
                "default_audio_language": "en",
                "default_language": "en",
                "live_broadcast_content": "none",
                "is_embeddable": True,
                "privacy_status": "public",
                "is_age_restricted": False,
                "is_available": True,
            },
            {
                "video_id": "privVid0004",
                "title": "Private Draft Lecture",
                "description": "Private recording unavailable to callers.",
                "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
                "channel_title": "Systems Craft",
                "published_at": "2026-08-01T10:00:00Z",
                "tags": ["python"],
                "category_id": "27",
                "category_name": "Education",
                "duration_seconds": 480,
                "default_audio_language": "en",
                "default_language": "en",
                "live_broadcast_content": "none",
                "is_embeddable": False,
                "privacy_status": "private",
                "is_age_restricted": False,
                "is_available": False,
            },
            {
                "video_id": "deleVid0005",
                "title": "Deleted Seminar",
                "description": "Removed video fixture.",
                "channel_id": "UC_TECH_00000000000002",
                "channel_title": "Code Mechanics",
                "published_at": "2026-07-12T10:00:00Z",
                "tags": ["systems"],
                "category_id": "27",
                "category_name": "Education",
                "duration_seconds": 360,
                "default_audio_language": "en",
                "default_language": "en",
                "live_broadcast_content": "none",
                "is_embeddable": False,
                "privacy_status": "deleted",
                "is_age_restricted": False,
                "is_available": False,
            },
            {
                "video_id": "liveVid0006",
                "title": "Live Systems Office Hours Stream",
                "description": "Active livestream excluded from similarity.",
                "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
                "channel_title": "Systems Craft",
                "published_at": "2026-11-25T16:00:00Z",
                "tags": ["python", "live"],
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
    searches = {
        "video_queries": {
            "python asyncio internals event loops": [
                "seedPy00001",
                "candNoTag02",
                "candOther03",
                "privVid0004",
                "deleVid0005",
                "liveVid0006",
            ]
        },
        "channel_queries": {},
    }
    (public / "videos.json").write_text(json.dumps(videos), encoding="utf-8")
    (public / "channels.json").write_text(json.dumps({"channels": []}), encoding="utf-8")
    (public / "searches.json").write_text(json.dumps(searches), encoding="utf-8")
    (public / "categories.json").write_text(json.dumps({"US": {"28": "SciTech"}}), encoding="utf-8")
    (synthetic / "default_user.json").write_text(
        json.dumps({"has_channel": False, "subscriptions": [], "playlists": []}),
        encoding="utf-8",
    )
    return root


class _CountingProvider(FixtureYouTubeProvider):
    def __init__(self, fixture_dir: Path) -> None:
        super().__init__(fixture_dir)
        self.trace: list[str] = []

    async def get_videos(self, video_ids: list[str] | tuple[str, ...]) -> list[Any]:
        self.trace.append(f"get_videos:{len(video_ids)}")
        return await super().get_videos(video_ids)

    async def search_videos(self, query: str, **kwargs: Any) -> list[Any]:
        self.trace.append(f"search_videos:{query}")
        return await super().search_videos(query, **kwargs)


async def _call_get_similar_videos(
    fixture_dir: Path,
    db_path: Path,
    arguments: dict[str, Any],
    *,
    quota_config: QuotaConfig | None = None,
) -> tuple[bool, dict[str, Any], _CountingProvider]:
    store = SQLiteStore(db_path)
    ledger = PersistentQuotaLedger(store, config=quota_config or QuotaConfig())
    provider = _CountingProvider(fixture_dir)
    server = create_server()
    register_get_similar_videos(server, provider=provider, quota_guard=ledger)

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
                result = await session.call_tool("get_similar_videos", arguments)
                tg.cancel_scope.cancel()
    assert result.structured_content is not None
    return result.is_error, dict(result.structured_content), provider


def test_ST_FR1_get_similar_videos_ranks_objective_metadata_within_quota(
    tmp_path: Path,
) -> None:
    fixture_dir = _write_test_fixtures(tmp_path / "fixtures")
    db_path = tmp_path / "quota.db"

    async def _run() -> None:
        is_err, payload, provider = await _call_get_similar_videos(
            fixture_dir,
            db_path,
            {
                "video_id": "https://www.youtube.com/watch?v=seedPy00001",
                "max_results": 5,
                "scoring_weights": {"title": 0.6, "tags": 0.1},
            },
        )
        assert is_err is False
        assert payload["quota_used"]["search_calls"] <= 1
        assert payload["quota_used"]["units"] <= 2
        assert provider.trace[0] == "get_videos:1"

        data = payload["data"]
        assert data["seed_video"]["video_id"] == "seedPy00001"
        results = data["results"]
        assert len(results) == 2
        returned_ids = {item["video_id"] for item in results}
        assert returned_ids == {"candNoTag02", "candOther03"}
        assert results[0]["video_id"] == "candNoTag02"
        assert set(results[0]["feature_scores"]) == {
            "title",
            "tags",
            "description",
            "category",
            "duration",
        }
        serialized = json.dumps(payload)
        for forbidden in FORBIDDEN_POPULARITY_KEYS:
            assert forbidden not in serialized

    anyio.run(_run)


def test_NT_VID_get_similar_videos_rejects_unavailable_and_invalid_inputs(
    tmp_path: Path,
) -> None:
    fixture_dir = _write_test_fixtures(tmp_path / "fixtures")

    async def _run() -> None:
        # Private seed -> VIDEO_UNAVAILABLE (costs 1u for seed lookup, 0 searches).
        is_err, payload, provider = await _call_get_similar_videos(
            fixture_dir,
            tmp_path / "q1.db",
            {"video_id": "privVid0004"},
        )
        assert is_err is True
        assert payload["code"] == "VIDEO_UNAVAILABLE"
        assert payload["quota_used"]["search_calls"] == 0
        assert len(provider.trace) == 1

        # Invalid video ID -> INVALID_ARGUMENT with ZERO provider calls.
        is_err2, payload2, provider2 = await _call_get_similar_videos(
            fixture_dir,
            tmp_path / "q2.db",
            {"video_id": "not-valid"},
        )
        assert is_err2 is True
        assert payload2["code"] == "INVALID_ARGUMENT"
        assert provider2.trace == []

        # Insufficient quota -> QUOTA_BUDGET_INSUFFICIENT with ZERO provider calls.
        is_err3, payload3, provider3 = await _call_get_similar_videos(
            fixture_dir,
            tmp_path / "q3.db",
            {"video_id": "seedPy00001"},
            quota_config=QuotaConfig(daily_units_limit=1, daily_search_limit=1),
        )
        assert is_err3 is True
        assert payload3["code"] == "QUOTA_BUDGET_INSUFFICIENT"
        assert provider3.trace == []

    anyio.run(_run)


@pytest.mark.parametrize("bad_max", [0, 51, True, "10"])
def test_NT_VID_get_similar_videos_rejects_invalid_max_results(
    tmp_path: Path,
    bad_max: Any,
) -> None:
    fixture_dir = _write_test_fixtures(tmp_path / "fixtures")

    async def _run() -> None:
        is_err, payload, provider = await _call_get_similar_videos(
            fixture_dir,
            tmp_path / "q.db",
            {"video_id": "seedPy00001", "max_results": bad_max},
        )
        assert is_err is True
        assert payload["code"] == "INVALID_ARGUMENT"
        assert provider.trace == []

    anyio.run(_run)
