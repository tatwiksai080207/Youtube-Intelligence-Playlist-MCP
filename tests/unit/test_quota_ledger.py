"""Unit tests for SQLiteStore WAL persistence, DST PT resets, and R-5 ledger costs (UT_QUOTA)."""

# ruff: noqa: N802
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio
import mcp.types as types
import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from yt_intel_mcp.config import AppConfig, QuotaConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import CostEstimate
from yt_intel_mcp.provider import FixtureErrorRule, FixtureYouTubeProvider
from yt_intel_mcp.quota import PersistentQuotaLedger, QuotaGuard
from yt_intel_mcp.schemas import list_schema_names, load_schema
from yt_intel_mcp.server import create_base_server
from yt_intel_mcp.store import SQLiteStore
from yt_intel_mcp.tools import QUOTA_RESOURCE_URI, execute_get_quota_status, register_quota_status

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "tests" / "fixtures"
FORBIDDEN_HTTP_IMPORTS = {
    "httpx",
    "httpx2",
    "httpcore",
    "httpcore2",
    "requests",
    "aiohttp",
    "google",
}


def test_UT_QUOTA_sqlite_wal_store_rollback_and_personal_purge(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "yt_intel.db"
    store = SQLiteStore(db_path)

    assert db_path.is_file()
    assert store.journal_mode() == "wal"

    with store.transaction(immediate=True) as conn:
        store.add_quota_usage(
            conn,
            "2026-11-26",
            units=15,
            search_calls=2,
            updated_at_utc="2026-11-26T10:00:00+00:00",
        )
        conn.executemany(
            """
            INSERT INTO cache_entries (
                cache_key, entry_kind, is_personal, payload_json, created_at_utc, expires_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            [
                ("vid:1", "videos", 0, "{}", "2026-11-26T10:00:00Z", "2026-11-27T10:00:00Z"),
                (
                    "usr:likes",
                    "user_lists",
                    1,
                    "{}",
                    "2026-11-26T10:00:00Z",
                    "2026-11-26T10:15:00Z",
                ),
            ],
        )
        conn.execute(
            """
            INSERT INTO first_observed (source, item_id, first_observed_utc)
            VALUES ('liked_video', 'vid_seed_py01', '2026-11-26T10:00:00Z');
            """
        )

    with pytest.raises(RuntimeError, match="abort"), store.transaction(immediate=True) as conn:
        store.add_quota_usage(
            conn,
            "2026-11-26",
            units=100,
            search_calls=5,
            updated_at_utc="2026-11-26T10:05:00+00:00",
        )
        raise RuntimeError("abort")

    row = store.get_quota_row("2026-11-26")
    assert row is not None
    assert row.units_used == 15
    assert row.search_calls_used == 2

    cache_deleted, observed_deleted = store.purge_personal_data()
    assert cache_deleted == 1
    assert observed_deleted == 1

    # NFR-7 / ADR-0006: public metadata cache and quota_ledger survive auth revocation.
    with store.transaction(immediate=False) as conn:
        remaining_cache = conn.execute("SELECT cache_key FROM cache_entries;").fetchall()
        remaining_observed = conn.execute("SELECT COUNT(*) FROM first_observed;").fetchone()
        remaining_quota = store.read_quota_row(conn, "2026-11-26")
    assert [r["cache_key"] for r in remaining_cache] == ["vid:1"]
    assert remaining_observed is not None and int(remaining_observed[0]) == 0
    assert remaining_quota is not None and remaining_quota.units_used == 15


def test_UT_QUOTA_r5_costs_c01_and_persistence_across_restarts(tmp_path: Path) -> None:
    cfg = AppConfig(data_dir=tmp_path / "state")
    ledger = PersistentQuotaLedger.from_config(
        cfg,
        clock=lambda: datetime(2026, 11, 26, 15, 0, tzinfo=UTC),
    )
    assert isinstance(ledger, QuotaGuard)

    # SRS Section 3.2 (R-5) default costs under C-2 dual budget.
    for list_op in (
        "videos.list",
        "channels.list",
        "subscriptions.list",
        "playlists.list",
        "playlistItems.list",
        "videoCategories.list",
    ):
        assert ledger.estimate(list_op) == CostEstimate(units=1, search_calls=0, operation=list_op)

    assert ledger.estimate("search.list", count=2) == CostEstimate(
        units=0, search_calls=2, operation="search.list"
    )
    assert ledger.estimate("playlists.insert") == CostEstimate(
        units=50, search_calls=0, operation="playlists.insert"
    )
    assert ledger.estimate("playlistItems.insert", count=3) == CostEstimate(
        units=150, search_calls=0, operation="playlistItems.insert"
    )
    assert ledger.estimate_playlist_write(4, include_stale_check=True) == CostEstimate(
        units=251, search_calls=0, operation="playlist_write"
    )
    assert ledger.estimate_workflow([("search.list", 2), ("videos.list", 3)]) == CostEstimate(
        units=3, search_calls=2, operation="search.listx2+videos.listx3"
    )

    # Legacy R-1 / C-2 configurable search unit cost mode (100u/call).
    legacy_ledger = PersistentQuotaLedger(
        SQLiteStore(tmp_path / "legacy" / "yt_intel.db"),
        QuotaConfig(search_unit_cost=100),
    )
    assert legacy_ledger.estimate("search.list", count=2) == CostEstimate(
        units=200, search_calls=2, operation="search.list"
    )

    with pytest.raises(ValueError, match="non-negative"):
        ledger.estimate("videos.list", count=-1)
    with pytest.raises(ValueError, match="Unknown"):
        ledger.estimate("playlists.delete")

    ledger.charge(CostEstimate(units=12, search_calls=3, operation="mixed"))

    # Simulate process restart with a brand new store/ledger instance on the same DB.
    restarted = PersistentQuotaLedger.from_config(
        cfg,
        clock=lambda: datetime(2026, 11, 26, 18, 0, tzinfo=UTC),
    )
    snap = restarted.status()
    assert snap.units_used == 12
    assert snap.units_remaining == 9988
    assert snap.search_calls_used == 3
    assert snap.search_calls_remaining == 97
    assert snap.reset_at == datetime(2026, 11, 27, 8, 0, tzinfo=UTC)


def test_UT_QUOTA_pacific_time_dst_spring_forward_and_fall_back_resets(tmp_path: Path) -> None:
    current = datetime(2026, 3, 8, 7, 59, 59, tzinfo=UTC)  # 2026-03-07 23:59:59 PST
    ledger = PersistentQuotaLedger(
        SQLiteStore(tmp_path / "dst.db"),
        QuotaConfig(),
        clock=lambda: current,
    )

    ledger.charge(CostEstimate(units=250, search_calls=9, operation="before_spring_dst"))
    before_spring = ledger.status()
    assert before_spring.units_used == 250
    assert before_spring.search_calls_used == 9
    assert before_spring.reset_at == datetime(2026, 3, 8, 8, 0, tzinfo=UTC)

    # Cross 00:00 PT on spring-forward day (2026-03-08 is 23h long -> next midnight is 07:00 UTC).
    current = datetime(2026, 3, 8, 8, 0, 0, tzinfo=UTC)
    spring_day = ledger.status()
    assert spring_day.units_used == 0
    assert spring_day.search_calls_used == 0
    assert spring_day.reset_at == datetime(2026, 3, 9, 7, 0, tzinfo=UTC)
    assert spring_day.reset_at - current == timedelta(hours=23)

    # Fall-back DST day (2026-11-01 is 25h long -> 00:00 PDT is 07:00 UTC, next is 08:00 UTC).
    current = datetime(2026, 11, 1, 7, 0, 0, tzinfo=UTC)
    ledger.charge(CostEstimate(units=50, search_calls=1, operation="fall_back_day"))
    fall_back = ledger.status()
    assert fall_back.units_used == 50
    assert fall_back.reset_at == datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
    assert fall_back.reset_at - current == timedelta(hours=25)


@pytest.mark.anyio
async def test_UT_QUOTA_charges_failed_provider_calls_and_marks_exhausted(tmp_path: Path) -> None:
    current = datetime(2026, 11, 26, 14, 0, tzinfo=UTC)
    ledger = PersistentQuotaLedger(
        SQLiteStore(tmp_path / "failures.db"),
        QuotaConfig(),
        clock=lambda: current,
    )
    provider = FixtureYouTubeProvider(
        FIXTURES_DIR,
        quota_guard=ledger,
        error_rules={
            "videos.list": FixtureErrorRule(reason="rateLimitExceeded", http_status=429),
            "search.list": FixtureErrorRule(reason="quotaExceeded", http_status=403),
        },
    )

    with pytest.raises(ToolError) as rate_err:
        await provider.get_videos(["vid_seed_py01"])
    assert rate_err.value.code is ErrorCode.RATE_LIMITED
    assert ledger.status().units_used == 1

    with pytest.raises(ToolError) as exhaust_err:
        await provider.search_videos("python")
    assert exhaust_err.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM
    exhausted_status = ledger.status()
    assert exhausted_status.search_calls_used == 1
    assert exhausted_status.upstream_exhausted is True

    # Next Pacific Time day clears upstream exhaustion cleanly.
    current = datetime(2026, 11, 27, 8, 0, 0, tzinfo=UTC)
    after_reset = ledger.status()
    assert after_reset.upstream_exhausted is False
    assert after_reset.units_used == 0
    assert after_reset.search_calls_used == 0


@pytest.mark.anyio
async def test_UT_QUOTA_tool_and_resource_report_budgets_with_zero_cost(tmp_path: Path) -> None:
    assert "get_quota_status" in list_schema_names()
    schema = load_schema("get_quota_status")
    assert schema["additionalProperties"] is False
    assert schema["properties"] == {}

    ledger = PersistentQuotaLedger(
        SQLiteStore(tmp_path / "mcp_quota.db"),
        QuotaConfig(daily_units_limit=500, daily_search_limit=20),
        clock=lambda: datetime(2026, 11, 26, 20, 0, tzinfo=UTC),
    )
    ledger.charge(CostEstimate(units=75, search_calls=4, operation="seed_work"))

    direct = execute_get_quota_status(ledger)
    assert direct["quota_used"] == {"units": 0, "search_calls": 0}
    assert direct["data"]["units"] == {"used": 75, "limit": 500, "remaining": 425}
    assert direct["data"]["search_calls"] == {"used": 4, "limit": 20, "remaining": 16}

    server = create_base_server()
    register_quota_status(server, ledger)

    async with (
        create_client_server_memory_streams() as (client_streams, server_streams),
        anyio.create_task_group() as task_group,
    ):

        async def _serve() -> None:
            await server._lowlevel_server.run(
                server_streams[0],
                server_streams[1],
                server._lowlevel_server.create_initialization_options(),
            )

        task_group.start_soon(_serve)
        async with ClientSession(client_streams[0], client_streams[1]) as session:
            await session.initialize()

            tools = await session.list_tools()
            assert [tool.name for tool in tools.tools] == ["get_quota_status"]

            call_result = await session.call_tool("get_quota_status", {})
            assert call_result.structured_content is not None
            assert call_result.structured_content["quota_used"] == {"units": 0, "search_calls": 0}
            assert call_result.structured_content["data"]["units"]["remaining"] == 425

            resources = await session.list_resources()
            assert [str(r.uri) for r in resources.resources] == [QUOTA_RESOURCE_URI]
            res = await session.read_resource(QUOTA_RESOURCE_URI)
            first = res.contents[0]
            assert isinstance(first, types.TextResourceContents)
            parsed = json.loads(first.text)
            assert parsed["search_calls"] == {"used": 4, "limit": 20, "remaining": 16}
            assert parsed["reset_timezone"] == "America/Los_Angeles"
        task_group.cancel_scope.cancel()

    # Invoking the tool and resource consumed zero additional quota.
    assert ledger.status().units_used == 75
    assert ledger.status().search_calls_used == 4


def test_SE_6_store_ledger_and_tool_have_no_http_or_google_imports() -> None:
    targets = [
        ROOT / "src" / "yt_intel_mcp" / "store.py",
        ROOT / "src" / "yt_intel_mcp" / "quota" / "ledger.py",
        ROOT / "src" / "yt_intel_mcp" / "tools" / "get_quota_status.py",
    ]
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(FORBIDDEN_HTTP_IMPORTS), f"Disallowed import in {path}"
