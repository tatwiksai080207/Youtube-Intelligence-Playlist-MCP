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


class _CountingProvider(FixtureYouTubeProvider):
    def __init__(self, fixture_dir: Path) -> None:
        super().__init__(fixture_dir)
        self.calls: list[str] = []

    async def get_videos(self, video_ids: list[str] | tuple[str, ...]) -> list[Any]:
        self.calls.append(f"get_videos:{len(video_ids)}")
        return await super().get_videos(video_ids)

    async def search_videos(self, query: str, **kwargs: Any) -> list[Any]:
        self.calls.append(f"search_videos:{query}")
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

    try:
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
    finally:
        store.close()


def test_ST_FR1_get_similar_videos_ranks_objective_metadata_within_quota(
    tmp_path: Path,
) -> None:
    fixture_dir = Path("tests/fixtures")
    db_path = tmp_path / "quota.db"

    async def _run() -> None:
        is_err, payload, provider = await _call_get_similar_videos(
            fixture_dir,
            db_path,
            {"video_id": "https://www.youtube.com/watch?v=vid_seed_py01", "max_results": 5},
        )
        assert is_err is False
        assert payload["ok"] is True
        assert payload["quota_used"]["search_calls"] <= 1
        assert payload["quota_used"]["units"] <= 2
        assert provider.calls[0] == "get_videos:1"

        data = payload["data"]
        assert data["seed_video"]["video_id"] == "vid_seed_py01"
        results = data["results"]
        assert len(results) >= 2
        # Candidate list excludes seed, private, deleted, and live videos.
        returned_ids = {item["video_id"] for item in results}
        assert "vid_seed_py01" not in returned_ids
        assert "vid_priv0003" not in returned_ids
        assert "vid_del00004" not in returned_ids
        assert "vid_live0005" not in returned_ids
        # Top match is Python concurrency video, with per-feature breakdown.
        assert results[0]["video_id"] == "vid_notags02"
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
    fixture_dir = Path("tests/fixtures")

    async def _run() -> None:
        # Private seed -> VIDEO_UNAVAILABLE (costs 1u for seed lookup, 0 searches).
        is_err, payload, provider = await _call_get_similar_videos(
            fixture_dir,
            tmp_path / "q1.db",
            {"video_id": "vid_priv0003"},
        )
        assert is_err is True
        assert payload["error"]["code"] == "VIDEO_UNAVAILABLE"
        assert payload["quota_used"]["search_calls"] == 0
        assert len(provider.calls) == 1

        # Invalid video ID -> INVALID_ARGUMENT with ZERO provider calls.
        is_err2, payload2, provider2 = await _call_get_similar_videos(
            fixture_dir,
            tmp_path / "q2.db",
            {"video_id": "not-valid"},
        )
        assert is_err2 is True
        assert payload2["error"]["code"] == "INVALID_ARGUMENT"
        assert provider2.calls == []

        # Insufficient quota -> QUOTA_EXHAUSTED_LOCAL with ZERO provider calls.
        is_err3, payload3, provider3 = await _call_get_similar_videos(
            fixture_dir,
            tmp_path / "q3.db",
            {"video_id": "vid_seed_py01"},
            quota_config=QuotaConfig(daily_units_limit=1, daily_search_limit=1),
        )
        assert is_err3 is True
        assert payload3["error"]["code"] == "QUOTA_EXHAUSTED_LOCAL"
        assert provider3.calls == []

    anyio.run(_run)


@pytest.mark.parametrize("bad_max", [0, 51, True, "10"])
def test_NT_VID_get_similar_videos_rejects_invalid_max_results(
    tmp_path: Path,
    bad_max: Any,
) -> None:
    async def _run() -> None:
        is_err, payload, provider = await _call_get_similar_videos(
            Path("tests/fixtures"),
            tmp_path / "q.db",
            {"video_id": "vid_seed_py01", "max_results": bad_max},
        )
        assert is_err is True
        assert payload["error"]["code"] == "INVALID_ARGUMENT"
        assert provider.calls == []

    anyio.run(_run)
