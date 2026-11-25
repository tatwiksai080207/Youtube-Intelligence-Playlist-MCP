"""Frozen error taxonomy, outcome statuses, envelopes, and upstream error mapping."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from yt_intel_mcp.models import QuotaUsed

__all__ = [
    "UPSTREAM_REASON_TO_ERROR_CODE",
    "ErrorCode",
    "OutcomeStatus",
    "ToolError",
    "error_response",
    "map_upstream_error",
    "success_response",
]


class ErrorCode(StrEnum):
    """Binding MCP error codes specified in Final SRS v1.0 Section 5."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    VIDEO_UNAVAILABLE = "VIDEO_UNAVAILABLE"
    INSUFFICIENT_USER_SIGNAL = "INSUFFICIENT_USER_SIGNAL"
    CONSTRAINTS_UNSATISFIABLE = "CONSTRAINTS_UNSATISFIABLE"
    CONFIRMATION_MISMATCH = "CONFIRMATION_MISMATCH"
    DRAFT_EXPIRED = "DRAFT_EXPIRED"
    CONFIRMATION_REUSED = "CONFIRMATION_REUSED"
    CONFIRMATION_DECLINED = "CONFIRMATION_DECLINED"
    CONFIRMATION_UNAVAILABLE = "CONFIRMATION_UNAVAILABLE"
    DRAFT_STALE = "DRAFT_STALE"
    QUOTA_BUDGET_INSUFFICIENT = "QUOTA_BUDGET_INSUFFICIENT"
    QUOTA_EXHAUSTED_UPSTREAM = "QUOTA_EXHAUSTED_UPSTREAM"
    RATE_LIMITED = "RATE_LIMITED"
    CHANNEL_REQUIRED = "CHANNEL_REQUIRED"
    SCOPE_INSUFFICIENT = "SCOPE_INSUFFICIENT"
    AUTH_REAUTHORIZATION_REQUIRED = "AUTH_REAUTHORIZATION_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class OutcomeStatus(StrEnum):
    """Completion status reported for playlist creation runs (FR-5.5)."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"


UPSTREAM_REASON_TO_ERROR_CODE: dict[str, ErrorCode] = {
    "quotaexceeded": ErrorCode.QUOTA_EXHAUSTED_UPSTREAM,
    "ratelimitexceeded": ErrorCode.RATE_LIMITED,
    "userratelimitexceeded": ErrorCode.RATE_LIMITED,
    "videonotfound": ErrorCode.VIDEO_UNAVAILABLE,
    "videoprivate": ErrorCode.VIDEO_UNAVAILABLE,
    "private": ErrorCode.VIDEO_UNAVAILABLE,
    "deleted": ErrorCode.VIDEO_UNAVAILABLE,
    "youtubesignuprequired": ErrorCode.CHANNEL_REQUIRED,
    "insufficientpermissions": ErrorCode.SCOPE_INSUFFICIENT,
    "invalid_grant": ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
    "forbidden": ErrorCode.PERMISSION_DENIED,
}


class ToolError(Exception):
    """Structured domain/provider error convertible into an MCP error envelope."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        quota_used: QuotaUsed | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: dict[str, Any] = dict(details) if details is not None else {}
        self.quota_used: QuotaUsed = quota_used if quota_used is not None else QuotaUsed()

    def to_envelope(self, quota_used: QuotaUsed | None = None) -> dict[str, Any]:
        """Serialize this error into the SRS Section 4.1 JSON error envelope."""
        effective_quota = quota_used if quota_used is not None else self.quota_used
        return {
            "code": self.code.value,
            "message": self.message,
            "details": dict(self.details),
            "quota_used": effective_quota.to_dict(),
        }


def success_response(
    summary: str,
    data: Mapping[str, Any],
    quota_used: QuotaUsed | None = None,
) -> dict[str, Any]:
    """Build the canonical SRS Section 4.1 JSON success response envelope."""
    effective_quota = quota_used if quota_used is not None else QuotaUsed()
    return {
        "summary": summary,
        "data": dict(data),
        "quota_used": effective_quota.to_dict(),
    }


def error_response(
    code: ErrorCode,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
    quota_used: QuotaUsed | None = None,
) -> dict[str, Any]:
    """Build a canonical error response dict directly from components."""
    return ToolError(code, message, details=details, quota_used=quota_used).to_envelope()


def map_upstream_error(
    reason: str | None = None,
    *,
    http_status: int | None = None,
    message: str | None = None,
    details: Mapping[str, Any] | None = None,
    quota_used: QuotaUsed | None = None,
) -> ToolError:
    """Map YouTube Data API v3 or Google OAuth error signals into a typed ToolError."""
    normalized_reason = reason.strip().lower() if reason else ""
    code = UPSTREAM_REASON_TO_ERROR_CODE.get(normalized_reason)

    if code is None:
        if http_status == 429:
            code = ErrorCode.RATE_LIMITED
        elif http_status == 401:
            code = ErrorCode.AUTH_REAUTHORIZATION_REQUIRED
        elif http_status == 404:
            code = ErrorCode.VIDEO_UNAVAILABLE
        else:
            code = ErrorCode.PERMISSION_DENIED

    merged_details: dict[str, Any] = dict(details) if details is not None else {}
    if reason:
        merged_details.setdefault("upstream_reason", reason)
    if http_status is not None:
        merged_details.setdefault("http_status", http_status)

    effective_message = message or f"Upstream request failed ({code.value})."
    return ToolError(
        code,
        effective_message,
        details=merged_details,
        quota_used=quota_used,
    )
