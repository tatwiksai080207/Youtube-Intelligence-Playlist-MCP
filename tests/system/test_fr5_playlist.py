"""System tests for draft_curated_playlist and immutable expiring drafts (MF-11, ST_FR5)."""

# ruff: noqa: N802
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pytest
from mcp.server.mcpserver import MCPServer

from yt_intel_mcp.cache import CachedYouTubeProvider, MetadataCache
from yt_intel_mcp.config import AppConfig, DraftConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import CreatedPlaylist, QuotaUsed, SearchHit, VideoMeta
from yt_intel_mcp.playlist import DraftStore
from yt_intel_mcp.provider import FixtureYouTubeProvider
from yt_intel_mcp.quota import PersistentQuotaLedger
from yt_intel_mcp.server import create_server
from yt_intel_mcp.store import SQLiteStore
from yt_intel_mcp.tools import execute_draft_curated_playlist, register_draft_curated_playlist

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _make_configure(
    *,
    ledger: PersistentQuotaLedger,
    draft_store: DraftStore,
) -> Callable[[MCPServer, AppConfig, FixtureYouTubeProvider], None]:
    def _configure(server: MCPServer, config: AppConfig, provider: FixtureYouTubeProvider) -> None:
        register_draft_curated_playlist(
            server,
            provider=provider,
            quota_guard=ledger,
            draft_store=draft_store,
            app_config=config,
        )

    return _configure


@pytest.mark.anyio
async def test_ST_FR5_draft_curated_playlist_end_to_end_zero_writes_and_expiry(
    system_harness_factory: object,
    tmp_path: Path,
) -> None:
    factory = system_harness_factory
    assert callable(factory)

    current = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)
    store = SQLiteStore(tmp_path / "draft_sys.db")
    ledger = PersistentQuotaLedger(store, clock=lambda: current)
    draft_store = DraftStore(DraftConfig(ttl_seconds=600), clock=lambda: current)

    async with factory(
        transport="memory",
        enable_elicitation=True,
        quota_guard=ledger,
        configure_server=_make_configure(ledger=ledger, draft_store=draft_store),
    ) as harness:
        assert "draft_curated_playlist" in await harness.list_tool_names()

        listed = await harness.session.list_tools()
        draft_tool = next(tool for tool in listed.tools if tool.name == "draft_curated_playlist")
        tool_dict = draft_tool.model_dump(by_alias=True)
        assert tool_dict["inputSchema"]["additionalProperties"] is False

        result, payload = await harness.call_tool_json(
            "draft_curated_playlist",
            {
                "topic": "python asyncio",
                "target_total_minutes": 20,
                "tolerance_percent": 5,
                "max_video_minutes": 15,
                "max_videos": 10,
                "language": "en",
                "allow_unknown_language": False,
                "title": "Asyncio Study Session",
                "privacy_status": "private",
            },
        )
        assert result.is_error is False
        assert payload is not None
        assert payload["quota_used"] == {"units": 1, "search_calls": 1}

        data = payload["data"]
        draft_id = str(data["draft_id"])
        assert data["title"] == "Asyncio Study Session"
        assert data["privacy_status"] == "private"
        assert data["side_effects"] == "none"
        assert 1140 <= data["total_duration_seconds"] <= 1200

        video_ids = [item["video_id"] for item in data["videos"]]
        # Exclude Spanish audio (vid_es_lang9), unknown audio (vid_unk_au10), live, private.
        assert "vid_es_lang9" not in video_ids
        assert "vid_unk_au10" not in video_ids
        assert "vid_live0005" not in video_ids
        assert "vid_priv0003" not in video_ids
        assert set(video_ids).issubset(
            {"vid_seed_py01", "vid_notags02", "vid_med_2407", "vid_short006"}
        )

        # Strictly read-only: ZERO write calls executed
        assert harness.provider.created_playlists == []
        assert harness.provider.inserted_items == []
        assert [c.operation for c in harness.provider.calls] == [
            "search.list:videos",
            "videos.list",
        ]
        assert ledger.status().units_used == 1
        assert ledger.status().search_calls_used == 1

        # Draft expires deterministically after 10 minutes
        stored = draft_store.get(draft_id)
        assert stored.ordered_video_ids == tuple(video_ids)
        current = current + timedelta(seconds=600)
        with pytest.raises(ToolError) as expired:
            draft_store.get(draft_id)
        assert expired.value.code is ErrorCode.DRAFT_EXPIRED


@pytest.mark.anyio
async def test_ST_FR5_allow_unknown_language_and_prompt_injection_sanitization(
    system_harness_factory: object,
    tmp_path: Path,
) -> None:
    factory = system_harness_factory
    assert callable(factory)

    ledger = PersistentQuotaLedger(SQLiteStore(tmp_path / "draft_lang.db"))
    draft_store = DraftStore()

    async with factory(
        transport="memory",
        quota_guard=ledger,
        configure_server=_make_configure(ledger=ledger, draft_store=draft_store),
    ) as harness:
        # 1. With allow_unknown_language=True on "python asyncio", 620 + 540 + 960 = 2120s
        #    falls strictly inside 36m @ 5% ([2052, 2160]s).
        res, payload = await harness.call_tool_json(
            "draft_curated_playlist",
            {
                "topic": "python asyncio",
                "target_total_minutes": 36,
                "tolerance_percent": 5,
                "max_video_minutes": 20,
                "language": "en",
                "allow_unknown_language": True,
            },
        )
        assert res.is_error is False
        assert payload is not None
        videos = payload["data"]["videos"]
        by_id = {v["video_id"]: v for v in videos}
        assert "vid_unk_au10" in by_id
        assert by_id["vid_unk_au10"]["is_audio_language_unverified"] is True
        assert by_id["vid_unk_au10"]["audio_language_label"] == "Audio language unverified"
        assert "vid_es_lang9" not in by_id

        # 2. Prompt-injection fixture video metadata is neutralized and creates ZERO playlists.
        inj_res, inj_payload = await harness.call_tool_json(
            "draft_curated_playlist",
            {
                "topic": "Prompt Security",
                "target_total_minutes": 12,
                "tolerance_percent": 5,
                "language": "en",
            },
        )
        assert inj_res.is_error is False
        assert inj_payload is not None
        inj_video = inj_payload["data"]["videos"][0]
        assert inj_video["video_id"] == "vid_inj_0011"
        assert "\u200b" not in inj_video["title"]
        assert "\u202e" not in inj_video["title"]
        assert "https://" not in inj_video["title"]
        assert harness.provider.created_playlists == []
        assert harness.provider.inserted_items == []


@pytest.mark.anyio
async def test_ST_FR5_mcp_errors_invalid_argument_zero_quota_and_unsatisfiable(
    system_harness_factory: object,
    tmp_path: Path,
) -> None:
    factory = system_harness_factory
    assert callable(factory)

    ledger = PersistentQuotaLedger(SQLiteStore(tmp_path / "draft_errs.db"))
    draft_store = DraftStore()

    async with factory(
        transport="memory",
        quota_guard=ledger,
        configure_server=_make_configure(ledger=ledger, draft_store=draft_store),
    ) as harness:
        # Invalid extra parameter and invalid language MUST reject pre-quota
        res_extra, err_extra = await harness.call_tool_json(
            "draft_curated_playlist",
            {"topic": "python", "target_total_minutes": 20, "approved": True},
        )
        assert res_extra.is_error is True
        assert err_extra is not None
        assert err_extra["code"] == "INVALID_ARGUMENT"
        assert err_extra["quota_used"] == {"units": 0, "search_calls": 0}

        res_bad_lang, err_lang = await harness.call_tool_json(
            "draft_curated_playlist",
            {"topic": "python", "target_total_minutes": 20, "language": "english"},
        )
        assert res_bad_lang.is_error is True
        assert err_lang is not None
        assert err_lang["code"] == "INVALID_ARGUMENT"
        assert harness.provider.calls == []
        assert ledger.status().units_used == 0
        assert ledger.status().search_calls_used == 0

        # Unsatisfiable target window returns rich structured error
        res_unsat, err_unsat = await harness.call_tool_json(
            "draft_curated_playlist",
            {"topic": "sourdough", "target_total_minutes": 500, "language": "en"},
        )
        assert res_unsat.is_error is True
        assert err_unsat is not None
        assert err_unsat["code"] == "CONSTRAINTS_UNSATISFIABLE"
        assert err_unsat["details"]["candidates_retrieved"] == 1
        assert err_unsat["details"]["binding_constraint"] == "insufficient_candidate_pool"
        assert err_unsat["quota_used"] == {"units": 1, "search_calls": 1}
        assert harness.provider.created_playlists == []

        # Zero search hits also produces clean CONSTRAINTS_UNSATISFIABLE (0 retrieved)
        res_empty, err_empty = await harness.call_tool_json(
            "draft_curated_playlist",
            {"topic": "zyxwvu nonexistent query", "target_total_minutes": 20, "language": "en"},
        )
        assert res_empty.is_error is True
        assert err_empty is not None
        assert err_empty["code"] == "CONSTRAINTS_UNSATISFIABLE"
        assert err_empty["details"]["candidates_retrieved"] == 0
        assert err_empty["quota_used"] == {"units": 0, "search_calls": 1}

    # Direct server.call_tool invocation (without wire RequestContext params) works cleanly
    direct_server = create_server()
    direct_ledger = PersistentQuotaLedger(SQLiteStore(tmp_path / "direct.db"))
    direct_provider = FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=direct_ledger)
    register_draft_curated_playlist(
        direct_server,
        provider=direct_provider,
        quota_guard=direct_ledger,
        draft_store=DraftStore(),
    )
    direct_result = await direct_server.call_tool(
        "draft_curated_playlist",
        {"topic": "python asyncio", "target_total_minutes": 20, "language": "en"},
    )
    assert isinstance(direct_result.content[0].text, str)
    direct_payload = json.loads(direct_result.content[0].text)
    assert direct_payload["data"]["side_effects"] == "none"


@pytest.mark.anyio
async def test_ST_FR5_pagination_cache_hit_and_read_error_charging(
    tmp_path: Path,
) -> None:
    # 1. CachedYouTubeProvider integration: second identical draft consumes 0 quota on cache hits
    store = SQLiteStore(tmp_path / "cached_draft.db")
    ledger = PersistentQuotaLedger(store)
    upstream = FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=ledger)
    cached_provider = CachedYouTubeProvider(upstream, MetadataCache(store), quota_guard=ledger)
    draft_store = DraftStore()

    args = {
        "topic": "python asyncio",
        "target_total_minutes": 20,
        "tolerance_percent": 5,
        "language": "en",
    }
    first = await execute_draft_curated_playlist(
        args, provider=cached_provider, quota_guard=ledger, draft_store=draft_store
    )
    assert first["quota_used"] == {"units": 1, "search_calls": 1}

    second = await execute_draft_curated_playlist(
        args, provider=cached_provider, quota_guard=ledger, draft_store=draft_store
    )
    assert second["quota_used"] == {"units": 0, "search_calls": 0}
    assert second["data"]["draft_id"] != first["data"]["draft_id"]
    assert len(upstream.calls) == 2

    # 2. Multi-page & >50-ID batch capping (<= 3 searches, <= 5 lists), skip non-video hits
    class _PagedTestProvider:
        def __init__(self) -> None:
            self.search_queries: list[tuple[str, str | None]] = []
            self.list_batches: list[list[str]] = []
            self.writes = 0
            self.fail_on_batch: bool = False
            self.fail_on_search: bool = False

        async def search_videos(
            self,
            query: str,
            *,
            max_results: int = 25,
            video_duration: Literal["any", "short", "medium", "long"] | None = None,
            relevance_language: str | None = None,
            region_code: str | None = None,
            page_token: str | None = None,
        ) -> list[SearchHit]:
            del max_results, video_duration, relevance_language, region_code
            if self.fail_on_search:
                raise ToolError(ErrorCode.QUOTA_EXHAUSTED_UPSTREAM, "upstream quota exceeded")
            self.search_queries.append((query, page_token))
            if page_token is None and len(self.search_queries) == 1:
                hits = [
                    SearchHit(kind="channel", item_id="UC_SKIP_ME", title="Skip channel hit"),
                ]
                hits.extend(
                    SearchHit(kind="video", item_id=f"V1_{i:02d}", title=f"Asyncio Talk {i}")
                    for i in range(49)
                )
                # Length 50 triggers pagination check (1 channel + 49 unique video hits).
                return hits
            if page_token == "50":
                return [
                    SearchHit(kind="video", item_id=f"V2_{i:03d}", title=f"Asyncio P2 {i}")
                    for i in range(250)
                ]
            return []

        async def get_videos(self, video_ids: list[str]) -> list[VideoMeta]:
            if self.fail_on_batch:
                raise ToolError(ErrorCode.QUOTA_EXHAUSTED_UPSTREAM, "upstream batch quota exceeded")
            self.list_batches.append(list(video_ids))
            out: list[VideoMeta] = []
            for vid in video_ids:
                dur = 1800 if vid == "V2_000" else 120
                out.append(
                    VideoMeta(
                        video_id=vid,
                        title=f"Asyncio Video {vid}",
                        duration_seconds=dur,
                        default_audio_language="en",
                    )
                )
            return out

        async def insert_playlist(self, **kwargs: Any) -> CreatedPlaylist:  # pragma: no cover
            self.writes += 1
            raise AssertionError("Draft MUST never call insert_playlist")

        async def insert_playlist_item(self, **kwargs: Any) -> str:  # pragma: no cover
            self.writes += 1
            raise AssertionError("Draft MUST never call insert_playlist_item")

    paged_ledger = PersistentQuotaLedger(SQLiteStore(tmp_path / "paged.db"))
    paged_provider = _PagedTestProvider()
    paged_res = await execute_draft_curated_playlist(
        {
            "topic": "Learn about python and asyncio",
            "target_total_minutes": 45,
            "tolerance_percent": 5,
            "max_videos": 10,
            "language": "en",
        },
        provider=paged_provider,  # type: ignore[arg-type]
        quota_guard=paged_ledger,
        draft_store=DraftStore(),
    )
    assert paged_res["quota_used"] == {"units": 5, "search_calls": 2}
    assert len(paged_provider.list_batches) == 5
    assert paged_provider.writes == 0
    assert paged_ledger.status().units_used == 5
    assert paged_ledger.status().search_calls_used == 2

    # 3. Compact query fallback with stopwords (skipped duplicate get_videos -> 2s, 1u)
    compact_ledger = PersistentQuotaLedger(SQLiteStore(tmp_path / "compact.db"))
    no_guard_fixture = FixtureYouTubeProvider(FIXTURES_DIR)
    with pytest.raises(ToolError) as compact_err:
        await execute_draft_curated_playlist(
            {
                "topic": "How to bake sourdough with starter",
                "target_total_minutes": 500,
                "language": "en",
            },
            provider=no_guard_fixture,
            quota_guard=compact_ledger,
            draft_store=DraftStore(),
        )
    assert compact_err.value.code is ErrorCode.CONSTRAINTS_UNSATISFIABLE
    assert compact_err.value.quota_used == QuotaUsed(units=1, search_calls=2)

    # 4. Upstream error during read on non-self-charging provider marks ledger & charges attempt
    err_ledger = PersistentQuotaLedger(SQLiteStore(tmp_path / "err_search.db"))
    err_provider = _PagedTestProvider()
    err_provider.fail_on_search = True
    with pytest.raises(ToolError) as upstream_s_err:
        await execute_draft_curated_playlist(
            {"topic": "python", "target_total_minutes": 20},
            provider=err_provider,  # type: ignore[arg-type]
            quota_guard=err_ledger,
            draft_store=DraftStore(),
        )
    assert upstream_s_err.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    assert err_ledger.status().upstream_exhausted is True
    assert err_ledger.status().search_calls_used == 1

    batch_err_ledger = PersistentQuotaLedger(SQLiteStore(tmp_path / "err_batch.db"))
    batch_err_provider = _PagedTestProvider()
    batch_err_provider.fail_on_batch = True
    with pytest.raises(ToolError) as upstream_b_err:
        await execute_draft_curated_playlist(
            {"topic": "python", "target_total_minutes": 20},
            provider=batch_err_provider,  # type: ignore[arg-type]
            quota_guard=batch_err_ledger,
            draft_store=DraftStore(),
        )
    assert upstream_b_err.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    assert batch_err_ledger.status().upstream_exhausted is True
    assert batch_err_ledger.status().units_used == 1
    assert batch_err_ledger.status().search_calls_used == 1
