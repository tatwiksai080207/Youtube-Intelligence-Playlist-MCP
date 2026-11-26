"""Dual quota preflight guard tests for FR-6.2, C-2, and ADR-0005 (QT_1, QT_2, QT_3)."""

# ruff: noqa: N802
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from yt_intel_mcp.config import QuotaConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import CostEstimate
from yt_intel_mcp.playlist import DraftStore
from yt_intel_mcp.provider import FixtureYouTubeProvider
from yt_intel_mcp.quota import PersistentQuotaLedger
from yt_intel_mcp.store import SQLiteStore
from yt_intel_mcp.tools import execute_draft_curated_playlist

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _make_ledger_and_provider(
    tmp_path: Path,
    *,
    units_limit: int = 10_000,
    search_limit: int = 100,
    search_unit_cost: int = 0,
) -> tuple[PersistentQuotaLedger, FixtureYouTubeProvider]:
    cfg = QuotaConfig(
        daily_units_limit=units_limit,
        daily_search_limit=search_limit,
        search_unit_cost=search_unit_cost,
    )
    ledger = PersistentQuotaLedger(
        SQLiteStore(tmp_path / "quota.db"),
        cfg,
        clock=lambda: datetime(2026, 11, 26, 18, 0, tzinfo=UTC),
    )
    provider = FixtureYouTubeProvider(FIXTURES_DIR, quota_guard=ledger)
    return ledger, provider


@pytest.mark.anyio
async def test_QT_1_insufficient_unit_budget_rejects_with_zero_provider_calls(
    tmp_path: Path,
) -> None:
    ledger, provider = _make_ledger_and_provider(tmp_path, units_limit=100, search_limit=50)
    ledger.charge(CostEstimate(units=99, search_calls=0, operation="prior_reads"))

    estimated = ledger.estimate_workflow([("videos.list", 2)])
    with pytest.raises(ToolError) as exc_info:
        ledger.preflight(estimated)
        await provider.get_videos(["vid_seed_py01"])  # pragma: no cover

    err = exc_info.value
    assert err.code is ErrorCode.QUOTA_BUDGET_INSUFFICIENT
    assert "units" in err.details["exceeded_budgets"]
    assert err.details["units_remaining"] == 1
    assert provider.calls == []
    assert ledger.status().units_used == 99


@pytest.mark.anyio
async def test_QT_2_insufficient_search_budget_rejects_even_with_ample_units(
    tmp_path: Path,
) -> None:
    ledger, provider = _make_ledger_and_provider(tmp_path, units_limit=10_000, search_limit=100)
    ledger.charge(CostEstimate(units=10, search_calls=99, operation="prior_searches"))

    # Units have 9,990 headroom, but search bucket has only 1 call left while workflow needs 2.
    workflow_cost = ledger.estimate_workflow([("search.list", 2), ("videos.list", 2)])
    with pytest.raises(ToolError) as exc_info:
        ledger.preflight(workflow_cost)
        await provider.search_videos("python")  # pragma: no cover

    err = exc_info.value
    assert err.code is ErrorCode.QUOTA_BUDGET_INSUFFICIENT
    assert err.details["exceeded_budgets"] == ["search_calls"]
    assert err.details["units_remaining"] == 9990
    assert err.details["search_calls_remaining"] == 1
    assert provider.calls == []
    assert ledger.status().search_calls_used == 99


@pytest.mark.anyio
async def test_QT_3_playlist_workflow_preflight_includes_50_plus_50_per_video_write_cost(
    tmp_path: Path,
) -> None:
    ledger, provider = _make_ledger_and_provider(tmp_path, units_limit=10_000, search_limit=100)
    ledger.charge(CostEstimate(units=9_600, search_calls=10, operation="earlier_usage"))

    # Reads alone (3s + 5u) fit inside 400 remaining units, but adding 8 videos' worst-case write
    # cost (50 + 50 * 8 = 450u -> total 455u) MUST fail preflight with zero provider calls.
    draft_read_units = 5
    worst_case_write = ledger.estimate_playlist_write(video_count=8, include_stale_check=False)
    draft_workflow_cost = CostEstimate(
        units=draft_read_units + worst_case_write.units,
        search_calls=3,
        operation="draft_curated_playlist_workflow",
    )
    assert draft_workflow_cost.units == 455

    with pytest.raises(ToolError) as exc_info:
        ledger.preflight(draft_workflow_cost)
        await provider.search_videos("python")  # pragma: no cover

    assert exc_info.value.code is ErrorCode.QUOTA_BUDGET_INSUFFICIENT
    assert exc_info.value.details["requested_units"] == 455
    assert exc_info.value.details["units_remaining"] == 400
    assert provider.calls == []
    assert ledger.status().units_used == 9_600

    # A smaller 6-video playlist creation write workflow (1u stale check + 50 + 50*6 = 351u <= 400u)
    # passes preflight cleanly and executes writes against FixtureYouTubeProvider.
    create_cost = ledger.estimate_playlist_write(video_count=6, include_stale_check=True)
    assert create_cost.units == 351
    ledger.preflight(create_cost)
    created = await provider.insert_playlist(title="Python Focused", privacy_status="private")
    await provider.insert_playlist_item(
        playlist_id=created.playlist_id,
        video_id="vid_seed_py01",
        position=0,
    )
    assert ledger.status().units_used == 9_700


def test_QT_preflight_blocks_when_upstream_exhausted_until_pt_reset(tmp_path: Path) -> None:
    current = datetime(2026, 11, 26, 22, 0, tzinfo=UTC)
    ledger = PersistentQuotaLedger(
        SQLiteStore(tmp_path / "exhaust.db"),
        QuotaConfig(),
        clock=lambda: current,
    )
    ledger.mark_upstream_exhausted()

    with pytest.raises(ToolError) as exc_info:
        ledger.preflight(ledger.estimate("videos.list"))
    assert exc_info.value.code is ErrorCode.QUOTA_EXHAUSTED_UPSTREAM

    current = datetime(2026, 11, 27, 8, 0, 0, tzinfo=UTC)
    status = ledger.preflight(ledger.estimate("videos.list"))
    assert status.upstream_exhausted is False


@pytest.mark.anyio
async def test_QT_3_draft_curated_playlist_rejects_insufficient_workflow_budget_with_zero_calls(
    tmp_path: Path,
) -> None:
    ledger, provider = _make_ledger_and_provider(tmp_path, units_limit=10_000, search_limit=100)
    # 400 remaining units suffices for reads (5u), but NOT 8-video worst-case writes (455u total).
    ledger.charge(CostEstimate(units=9_600, search_calls=10, operation="prior_usage"))
    draft_store = DraftStore()

    with pytest.raises(ToolError) as unit_err:
        await execute_draft_curated_playlist(
            {"topic": "python asyncio", "target_total_minutes": 20, "max_videos": 8},
            provider=provider,
            quota_guard=ledger,
            draft_store=draft_store,
        )
    assert unit_err.value.code is ErrorCode.QUOTA_BUDGET_INSUFFICIENT
    assert "units" in unit_err.value.details["exceeded_budgets"]
    assert unit_err.value.details["requested_units"] == 455
    assert provider.calls == []
    assert provider.created_playlists == []
    assert draft_store.list_active_ids() == ()
    assert ledger.status().units_used == 9_600
    assert ledger.status().search_calls_used == 10

    # Also enforce search_calls bucket: 2 remaining searches < 3 planned searches => zero API calls.
    search_ledger, search_provider = _make_ledger_and_provider(
        tmp_path / "search_cap", units_limit=10_000, search_limit=100
    )
    search_ledger.charge(CostEstimate(units=50, search_calls=98, operation="prior_searches"))
    with pytest.raises(ToolError) as search_err:
        await execute_draft_curated_playlist(
            {"topic": "python asyncio", "target_total_minutes": 20, "max_videos": 8},
            provider=search_provider,
            quota_guard=search_ledger,
            draft_store=DraftStore(),
        )
    assert search_err.value.code is ErrorCode.QUOTA_BUDGET_INSUFFICIENT
    assert "search_calls" in search_err.value.details["exceeded_budgets"]
    assert search_provider.calls == []
    assert search_ledger.status().search_calls_used == 98
