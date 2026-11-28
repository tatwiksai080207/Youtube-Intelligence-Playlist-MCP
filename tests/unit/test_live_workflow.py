"""Dry-run unit tests for scheduled live API test workflow and quota abort (SR-16, TQ-5, NFR-2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from yt_intel_mcp.config import LiveTestConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import CostEstimate
from yt_intel_mcp.provider import LiveYouTubeProvider
from yt_intel_mcp.quota import PersistentQuotaLedger
from yt_intel_mcp.store import SQLiteStore


class _MockLiveTransport:
    """Mock live transport tracking requests without making network calls."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, str], dict[str, Any]]:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "params": params or {},
                "json_body": json_body,
            }
        )
        return 200, {}, {"items": []}


def test_dry_run_live_test_config_hard_limits() -> None:
    """LiveTestConfig defines hard 300 unit and 10 search call ceilings (NFR-2)."""
    cfg = LiveTestConfig()
    assert cfg.max_units == 300
    assert cfg.max_search_calls == 10

    quota_cfg = cfg.to_quota_config()
    assert quota_cfg.daily_units_limit == 300
    assert quota_cfg.daily_search_limit == 10
    assert quota_cfg.search_unit_cost == 0


def test_dry_run_persistent_quota_ledger_for_live_tests(tmp_path: Path) -> None:
    """PersistentQuotaLedger.for_live_tests applies LiveTestConfig limits (NFR-2, TQ-5)."""
    store = SQLiteStore(tmp_path / "live_quota.db")
    ledger = PersistentQuotaLedger.for_live_tests(store)

    status = ledger.status()
    assert status.units_limit == 300
    assert status.search_calls_limit == 10
    assert status.units_used == 0
    assert status.search_calls_used == 0


@pytest.mark.anyio
async def test_dry_run_live_provider_aborts_when_unit_budget_exceeded(tmp_path: Path) -> None:
    """Live provider aborts with zero network calls when live unit cap is reached (NFR-2)."""
    store = SQLiteStore(tmp_path / "quota.db")
    ledger = PersistentQuotaLedger.for_live_tests(store)
    transport = _MockLiveTransport()
    provider = LiveYouTubeProvider(
        api_key="AIzaSyMockKey",
        quota_guard=ledger,
        http_transport=transport,
    )

    # Exhaust the 300 unit budget exactly
    ledger.charge(CostEstimate(units=300, search_calls=0, operation="prior_live_reads"))
    assert ledger.status().units_remaining == 0

    # Next read operation must abort before making any HTTP request
    with pytest.raises(ToolError) as exc_info:
        await provider.get_video_categories(region_code="US")

    err = exc_info.value
    assert err.code is ErrorCode.QUOTA_BUDGET_INSUFFICIENT
    assert "units" in err.details["exceeded_budgets"]
    assert transport.requests == []


@pytest.mark.anyio
async def test_dry_run_live_provider_aborts_when_search_calls_exceeded(tmp_path: Path) -> None:
    """Live provider aborts with zero network calls when live search limit is reached (NFR-2)."""
    store = SQLiteStore(tmp_path / "quota.db")
    ledger = PersistentQuotaLedger.for_live_tests(store)
    transport = _MockLiveTransport()
    provider = LiveYouTubeProvider(
        api_key="AIzaSyMockKey",
        quota_guard=ledger,
        http_transport=transport,
    )

    # Exhaust the 10 search call budget
    ledger.charge(CostEstimate(units=10, search_calls=10, operation="prior_live_searches"))
    assert ledger.status().search_calls_remaining == 0

    # Next search operation must abort before making any HTTP request
    with pytest.raises(ToolError) as exc_info:
        await provider.search_videos("python tutorials")

    err = exc_info.value
    assert err.code is ErrorCode.QUOTA_BUDGET_INSUFFICIENT
    assert "search_calls" in err.details["exceeded_budgets"]
    assert transport.requests == []


def test_dry_run_live_workflow_definition() -> None:
    """Verify .github/workflows/live.yml triggers and environment settings (TQ-5, NFR-2)."""
    workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "live.yml"
    assert workflow_path.is_file(), f"Workflow file missing: {workflow_path}"

    with workflow_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Verify triggers: MUST have schedule and workflow_dispatch,
    # MUST NOT trigger on pull_request or push events.
    triggers = data.get("on") or data.get(True) or {}
    assert "schedule" in triggers, "Scheduled trigger must be present in live.yml"
    assert "workflow_dispatch" in triggers, "Manual workflow_dispatch must be present in live.yml"
    assert "pull_request" not in triggers, "live.yml MUST NEVER run on pull requests (TQ-5, NFR-2)"
    assert "push" not in triggers, "live.yml MUST NOT run on push events"

    # Verify jobs and environment
    jobs = data.get("jobs", {})
    assert "live-smoke-tests" in jobs
    job = jobs["live-smoke-tests"]
    env = job.get("env", {})
    assert env.get("YT_INTEL_PROVIDER") == "live"
    assert env.get("YT_INTEL_TEST_LIVE") == "1"

    # Verify pytest step
    steps = job.get("steps", [])
    step_runs = [step.get("run", "") for step in steps]
    assert any("pytest -m live" in run for run in step_runs)
