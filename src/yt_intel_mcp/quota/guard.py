"""QuotaGuard Protocol and QuotaStatus contract for dual budget enforcement (FR-6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from yt_intel_mcp.models import CostEstimate

__all__ = ["QuotaGuard", "QuotaStatus"]


@dataclass(frozen=True, slots=True)
class QuotaStatus:
    """Snapshot of the persistent Pacific Time daily quota ledger."""

    units_used: int
    units_limit: int
    units_remaining: int
    search_calls_used: int
    search_calls_limit: int
    search_calls_remaining: int
    reset_at: datetime
    upstream_exhausted: bool = False


@runtime_checkable
class QuotaGuard(Protocol):
    """Dual quota ledger interface enforcing unit and search.list budgets (FR-6.2)."""

    def estimate(self, operation: str, *, count: int = 1) -> CostEstimate:
        """Compute expected quota cost for a named API operation."""
        ...

    def preflight(self, cost: CostEstimate) -> QuotaStatus:
        """Verify sufficient remaining units and search calls before dispatching an API call.

        Implementations MUST raise ToolError(QUOTA_BUDGET_INSUFFICIENT) or
        ToolError(QUOTA_EXHAUSTED_UPSTREAM) when blocked.
        """
        ...

    def charge(self, cost: CostEstimate) -> QuotaStatus:
        """Record actually consumed quota into the persistent ledger."""
        ...

    def mark_upstream_exhausted(self, reset_at: datetime | None = None) -> QuotaStatus:
        """Mark upstream YouTube API quota exhausted until the next PT daily reset."""
        ...

    def status(self) -> QuotaStatus:
        """Return current daily quota consumption, remaining headroom, and reset time."""
        ...
