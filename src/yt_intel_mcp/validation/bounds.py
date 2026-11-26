"""Strict numeric, list, enum, and scoring weight range validators (NFR-5, INV-02)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import EventSource

__all__ = [
    "ALLOWED_SCORING_WEIGHT_KEYS",
    "ALLOWED_TIMEFRAMES",
    "validate_float_range",
    "validate_int_range",
    "validate_max_results",
    "validate_scoring_weights",
    "validate_sources",
    "validate_timeframe",
]

ALLOWED_SCORING_WEIGHT_KEYS: frozenset[str] = frozenset(
    {"title", "tags", "description", "category", "duration"}
)
ALLOWED_TIMEFRAMES: frozenset[str] = frozenset({"7d", "30d", "90d", "180d", "365d", "all"})


def _invalid(field: str, message: str) -> ToolError:
    return ToolError(ErrorCode.INVALID_ARGUMENT, message, details={"field": field})


def validate_int_range(value: object, field: str, *, minimum: int, maximum: int) -> int:
    """Validate an integer (excluding booleans) within inclusive [minimum, maximum]."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid(field, f"Parameter '{field}' must be an integer.")
    if value < minimum or value > maximum:
        raise _invalid(
            field,
            f"Parameter '{field}' must be between {minimum} and {maximum} (got {value}).",
        )
    return value


def validate_float_range(value: object, field: str, *, minimum: float, maximum: float) -> float:
    """Validate a finite number (excluding booleans) within inclusive [minimum, maximum]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(field, f"Parameter '{field}' must be a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise _invalid(field, f"Parameter '{field}' must be finite (not NaN or infinity).")
    if number < minimum or number > maximum:
        raise _invalid(
            field,
            f"Parameter '{field}' must be between {minimum} and {maximum} (got {number}).",
        )
    return number


def validate_max_results(value: object = 10, *, maximum: int = 50) -> int:
    """Validate bounded result limit parameter matching SRS Section 3.1 (1..50)."""
    return validate_int_range(value, "max_results", minimum=1, maximum=maximum)


def validate_scoring_weights(weights: object) -> dict[str, float]:
    """Validate objective similarity weights (INV-01, ADR-0003, NFR-5)."""
    if not isinstance(weights, Mapping) or not weights:
        raise _invalid(
            "scoring_weights",
            "Parameter 'scoring_weights' must be a non-empty mapping of objective weights.",
        )

    validated: dict[str, float] = {}
    for raw_key, raw_value in weights.items():
        if not isinstance(raw_key, str) or raw_key not in ALLOWED_SCORING_WEIGHT_KEYS:
            raise _invalid(
                "scoring_weights",
                f"Unsupported scoring weight key {raw_key!r}; popularity signals are forbidden.",
            )
        validated[raw_key] = validate_float_range(
            raw_value, f"scoring_weights.{raw_key}", minimum=0.0, maximum=1.0
        )

    if sum(validated.values()) <= 0.0:
        raise _invalid(
            "scoring_weights",
            "At least one supplied weight in 'scoring_weights' must be greater than 0.0.",
        )
    return validated


def validate_sources(sources: object) -> tuple[EventSource, ...]:
    """Validate non-empty unique user library EventSource subset (FR-3.1, NFR-5)."""
    if isinstance(sources, (str, bytes)) or not isinstance(sources, Sequence) or not sources:
        raise _invalid(
            "sources",
            "Parameter 'sources' must be a non-empty array of valid EventSource values.",
        )

    seen: set[EventSource] = set()
    ordered: list[EventSource] = []
    for item in sources:
        if not isinstance(item, str):
            raise _invalid("sources", "Each entry in 'sources' must be a string.")
        try:
            source = EventSource(item)
        except ValueError as exc:
            raise _invalid("sources", f"Unsupported signal source {item!r}.") from exc
        if source in seen:
            raise _invalid("sources", f"Duplicate signal source {item!r} is not permitted.")
        seen.add(source)
        ordered.append(source)
    return tuple(ordered)


def validate_timeframe(timeframe: object = "90d") -> str:
    """Validate engagement timeframe selector against frozen ADR-0007 presets."""
    if not isinstance(timeframe, str) or timeframe not in ALLOWED_TIMEFRAMES:
        raise _invalid(
            "timeframe",
            f"Unsupported timeframe {timeframe!r}; expected one of {sorted(ALLOWED_TIMEFRAMES)}.",
        )
    return timeframe
