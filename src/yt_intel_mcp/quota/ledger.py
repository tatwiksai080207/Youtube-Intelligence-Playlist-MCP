"""Persistent dual-budget quota ledger enforcing FR-6.1, FR-6.2, C-2, and INV-19."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from yt_intel_mcp.config import AppConfig, QuotaConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import CostEstimate
from yt_intel_mcp.quota.guard import QuotaStatus
from yt_intel_mcp.store import QuotaLedgerRow, SQLiteStore

__all__ = ["PersistentQuotaLedger"]

_LIST_OPERATIONS = frozenset(
    {
        "videos.list",
        "videos.list:myrating",
        "get_videos",
        "channels.list",
        "get_channels",
        "get_channel_by_handle",
        "get_my_channel",
        "subscriptions.list",
        "list_subscriptions_mine",
        "playlists.list",
        "list_playlists_mine",
        "playlistitems.list",
        "list_playlist_items",
        "videocategories.list",
        "get_video_categories",
        "list_liked_videos_rated",
    }
)

_SEARCH_OPERATIONS = frozenset(
    {
        "search.list",
        "search.list:videos",
        "search.list:channels",
        "search_videos",
        "search_channels",
    }
)

_PLAYLIST_CREATE_OPERATIONS = frozenset(
    {
        "playlists.insert",
        "insert_playlist",
    }
)

_PLAYLIST_ITEM_OPERATIONS = frozenset(
    {
        "playlistitems.insert",
        "insert_playlist_item",
    }
)

_PLAYLIST_WRITE_WORKFLOW_OPERATIONS = frozenset(
    {
        "playlist_write",
        "create_curated_playlist",
    }
)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class PersistentQuotaLedger:
    """SQLite-backed QuotaGuard tracking daily units and search calls with PT DST resets."""

    def __init__(
        self,
        store: SQLiteStore,
        config: QuotaConfig | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.config = config or QuotaConfig()
        self._timezone = ZoneInfo(self.config.reset_timezone)
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> PersistentQuotaLedger:
        """Create a PersistentQuotaLedger backed by ``config.data_dir / 'yt_intel.db'``."""
        return cls(SQLiteStore.from_config(config), config.quota, clock=clock)

    def _now_utc(self) -> datetime:
        return _ensure_utc(self._clock())

    def _budget_window(self, now_utc: datetime) -> tuple[str, datetime]:
        local_now = now_utc.astimezone(self._timezone)
        budget_date = local_now.date().isoformat()
        next_day = local_now.date() + timedelta(days=1)
        next_midnight_local = datetime.combine(next_day, time(0, 0), tzinfo=self._timezone)
        return budget_date, next_midnight_local.astimezone(UTC)

    def _is_row_exhausted(self, row: QuotaLedgerRow | None, now_utc: datetime) -> bool:
        if row is None or not row.upstream_exhausted:
            return False
        if row.exhausted_until_utc is None:
            return True
        until = _ensure_utc(datetime.fromisoformat(row.exhausted_until_utc))
        return now_utc < until

    def _to_status(
        self,
        row: QuotaLedgerRow | None,
        *,
        reset_at: datetime,
        now_utc: datetime,
    ) -> QuotaStatus:
        units_used = row.units_used if row is not None else 0
        search_used = row.search_calls_used if row is not None else 0
        units_remaining = max(0, self.config.daily_units_limit - units_used)
        search_remaining = max(0, self.config.daily_search_limit - search_used)
        return QuotaStatus(
            units_used=units_used,
            units_limit=self.config.daily_units_limit,
            units_remaining=units_remaining,
            search_calls_used=search_used,
            search_calls_limit=self.config.daily_search_limit,
            search_calls_remaining=search_remaining,
            reset_at=reset_at,
            upstream_exhausted=self._is_row_exhausted(row, now_utc),
        )

    def estimate(self, operation: str, *, count: int = 1) -> CostEstimate:
        """Compute expected quota cost for an SRS Section 3.2 (R-5) operation or workflow."""
        if count < 0:
            raise ValueError(f"Quota estimate count must be non-negative, got {count}.")

        normalized = operation.strip().lower()
        if normalized in _LIST_OPERATIONS:
            return CostEstimate(
                units=self.config.list_unit_cost * count,
                search_calls=0,
                operation=operation,
            )
        if normalized in _SEARCH_OPERATIONS:
            return CostEstimate(
                units=self.config.search_unit_cost * count,
                search_calls=self.config.search_call_cost * count,
                operation=operation,
            )
        if normalized in _PLAYLIST_CREATE_OPERATIONS:
            return CostEstimate(
                units=self.config.playlist_insert_unit_cost * count,
                search_calls=0,
                operation=operation,
            )
        if normalized in _PLAYLIST_ITEM_OPERATIONS:
            return CostEstimate(
                units=self.config.playlist_item_insert_unit_cost * count,
                search_calls=0,
                operation=operation,
            )
        if normalized in _PLAYLIST_WRITE_WORKFLOW_OPERATIONS:
            return CostEstimate(
                units=(
                    self.config.playlist_insert_unit_cost
                    + self.config.playlist_item_insert_unit_cost * count
                ),
                search_calls=0,
                operation=operation,
            )
        raise ValueError(f"Unknown YouTube quota operation: {operation!r}.")

    def estimate_playlist_write(
        self,
        video_count: int,
        *,
        include_stale_check: bool = False,
    ) -> CostEstimate:
        """Estimate playlist creation cost (50 + 50/video, optionally plus 1u stale check)."""
        if video_count < 0:
            raise ValueError(f"video_count must be non-negative, got {video_count}.")
        stale_units = self.config.list_unit_cost if include_stale_check else 0
        write_units = (
            self.config.playlist_insert_unit_cost
            + self.config.playlist_item_insert_unit_cost * video_count
        )
        return CostEstimate(
            units=stale_units + write_units,
            search_calls=0,
            operation="playlist_write",
        )

    def estimate_workflow(
        self,
        calls: Sequence[tuple[str, int]] | Mapping[str, int],
    ) -> CostEstimate:
        """Sum cost estimates across multiple named operations for workflow preflight."""
        items = calls.items() if isinstance(calls, Mapping) else calls
        total_units = 0
        total_searches = 0
        names: list[str] = []
        for op_name, op_count in items:
            est = self.estimate(op_name, count=op_count)
            total_units += est.units
            total_searches += est.search_calls
            names.append(f"{op_name}x{op_count}")
        return CostEstimate(
            units=total_units,
            search_calls=total_searches,
            operation="+".join(names),
        )

    def preflight(self, cost: CostEstimate) -> QuotaStatus:
        """Check upstream exhaustion and both daily budgets atomically before dispatching calls."""
        now_utc = self._now_utc()
        budget_date, reset_at = self._budget_window(now_utc)

        with self.store.transaction(immediate=True) as conn:
            row = self.store.read_quota_row(conn, budget_date)
            status = self._to_status(row, reset_at=reset_at, now_utc=now_utc)

        if status.upstream_exhausted:
            raise ToolError(
                ErrorCode.QUOTA_EXHAUSTED_UPSTREAM,
                "YouTube API upstream quota is exhausted until the next 00:00 Pacific Time reset.",
                details={
                    "budget_date": budget_date,
                    "reset_at": status.reset_at.isoformat(),
                    "units_used": status.units_used,
                    "search_calls_used": status.search_calls_used,
                    "operation": cost.operation,
                },
            )

        units_exceeded = (status.units_used + cost.units) > self.config.daily_units_limit
        searches_exceeded = (
            status.search_calls_used + cost.search_calls
        ) > self.config.daily_search_limit

        if units_exceeded or searches_exceeded:
            exceeded_budgets: list[str] = []
            if units_exceeded:
                exceeded_budgets.append("units")
            if searches_exceeded:
                exceeded_budgets.append("search_calls")
            raise ToolError(
                ErrorCode.QUOTA_BUDGET_INSUFFICIENT,
                (
                    "Insufficient daily YouTube quota budget "
                    f"({', '.join(exceeded_budgets)} limit exceeded)."
                ),
                details={
                    "budget_date": budget_date,
                    "exceeded_budgets": exceeded_budgets,
                    "operation": cost.operation,
                    "requested_units": cost.units,
                    "requested_search_calls": cost.search_calls,
                    "units_used": status.units_used,
                    "units_limit": status.units_limit,
                    "units_remaining": status.units_remaining,
                    "search_calls_used": status.search_calls_used,
                    "search_calls_limit": status.search_calls_limit,
                    "search_calls_remaining": status.search_calls_remaining,
                    "reset_at": status.reset_at.isoformat(),
                },
            )

        return status

    def charge(self, cost: CostEstimate) -> QuotaStatus:
        """Persist consumed units and search calls (both successes and failures) in SQLite."""
        now_utc = self._now_utc()
        budget_date, reset_at = self._budget_window(now_utc)
        now_iso = now_utc.isoformat()

        with self.store.transaction(immediate=True) as conn:
            row = self.store.add_quota_usage(
                conn,
                budget_date,
                units=cost.units,
                search_calls=cost.search_calls,
                updated_at_utc=now_iso,
            )
            return self._to_status(row, reset_at=reset_at, now_utc=now_utc)

    def mark_upstream_exhausted(self, reset_at: datetime | None = None) -> QuotaStatus:
        """Persist upstream quota exhaustion until ``reset_at`` or the next 00:00 PT reset."""
        now_utc = self._now_utc()
        budget_date, default_reset_at = self._budget_window(now_utc)
        effective_reset = _ensure_utc(reset_at) if reset_at is not None else default_reset_at
        now_iso = now_utc.isoformat()

        with self.store.transaction(immediate=True) as conn:
            row = self.store.set_quota_upstream_exhausted(
                conn,
                budget_date,
                exhausted_until_utc=effective_reset.isoformat(),
                updated_at_utc=now_iso,
            )
            return self._to_status(row, reset_at=default_reset_at, now_utc=now_utc)

    def status(self) -> QuotaStatus:
        """Return current Pacific Time daily consumption, remaining headroom, and reset time."""
        now_utc = self._now_utc()
        budget_date, reset_at = self._budget_window(now_utc)
        row = self.store.get_quota_row(budget_date)
        return self._to_status(row, reset_at=reset_at, now_utc=now_utc)
