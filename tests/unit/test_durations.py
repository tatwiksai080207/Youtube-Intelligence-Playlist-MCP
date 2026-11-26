"""Unit tests for ISO-8601 duration parsing and human-readable formatting (UT_DUR, NFR-9)."""

# ruff: noqa: N802
from __future__ import annotations

import pytest

from yt_intel_mcp.durations import (
    format_duration,
    format_duration_clock,
    format_iso8601_duration,
    is_live_or_zero_duration,
    parse_iso8601_duration,
    parse_optional_duration,
)


@pytest.mark.parametrize(
    ("raw", "expected_seconds"),
    [
        ("P0D", 0),
        ("PT0S", 0),
        ("P0DT0H0M0S", 0),
        ("PT45S", 45),
        ("PT4M", 240),
        ("PT15M33S", 933),
        ("PT20M", 1200),
        ("PT1H2M3S", 3723),
        ("PT2H", 7200),
        ("P1D", 86400),
        ("P1DT2H3M4S", 93784),
        ("P1W", 604800),
        ("pt5m10s", 310),
        ("  PT12.6S  ", 13),
        ("PT1M2,4S", 62),
    ],
)
def test_UT_DUR_parse_iso8601_duration_valid_inputs(raw: str, expected_seconds: int) -> None:
    assert parse_iso8601_duration(raw) == expected_seconds


@pytest.mark.parametrize(
    "bad_value",
    [
        "",
        "   ",
        "P",
        "PT",
        "P1DT",
        "5m",
        "120",
        "-PT5M",
        "P1Y",
        "P1M",
        "PT1H2M3X",
        "PT-5S",
    ],
)
def test_UT_DUR_parse_iso8601_duration_rejects_malformed_inputs(bad_value: str) -> None:
    with pytest.raises(ValueError):
        parse_iso8601_duration(bad_value)


def test_UT_DUR_parse_optional_and_live_or_zero_detection() -> None:
    assert parse_optional_duration(None) is None
    assert parse_optional_duration("   ") is None
    assert parse_optional_duration("PT3M59S") == 239

    assert is_live_or_zero_duration("P0D") is True
    assert is_live_or_zero_duration("PT0S") is True
    assert is_live_or_zero_duration(0) is True
    assert is_live_or_zero_duration(None) is True
    assert is_live_or_zero_duration("PT15M", live_broadcast_content="live") is True
    assert is_live_or_zero_duration(600, live_broadcast_content="upcoming") is True

    assert is_live_or_zero_duration("PT1S") is False
    assert is_live_or_zero_duration(240) is False
    assert is_live_or_zero_duration("PT15M33S", live_broadcast_content="none") is False


@pytest.mark.parametrize(
    ("seconds", "live", "expected_human"),
    [
        (None, False, "Unknown"),
        (None, True, "Live"),
        (0, True, "Live"),
        (0, False, "0s"),
        (45, False, "45s"),
        (240, False, "4m"),
        (933, False, "15m 33s"),
        (3600, False, "1h"),
        (3665, False, "1h 1m 5s"),
        (7200, False, "2h"),
        (93784, False, "26h 3m 4s"),
    ],
)
def test_UT_DUR_format_duration_outputs_human_readable_strings(
    seconds: int | None, live: bool, expected_human: str
) -> None:
    assert format_duration(seconds, live=live) == expected_human


@pytest.mark.parametrize(
    ("seconds", "expected_clock"),
    [
        (None, "--:--"),
        (0, "0:00"),
        (45, "0:45"),
        (933, "15:33"),
        (6840, "1:54:00"),
        (7200, "2:00:00"),
    ],
)
def test_UT_DUR_format_duration_clock_and_iso_round_trip(
    seconds: int | None, expected_clock: str
) -> None:
    assert format_duration_clock(seconds) == expected_clock
    if seconds is not None:
        iso_text = format_iso8601_duration(seconds)
        assert parse_iso8601_duration(iso_text) == seconds


def test_UT_DUR_rejects_negative_and_boolean_inputs() -> None:
    with pytest.raises(ValueError):
        format_duration(-1)
    with pytest.raises(ValueError):
        format_duration(True)
    with pytest.raises(ValueError):
        format_duration_clock(-5)
    with pytest.raises(ValueError):
        format_duration_clock(False)
    with pytest.raises(ValueError):
        format_iso8601_duration(-1)
    with pytest.raises(ValueError):
        format_iso8601_duration(True)
    with pytest.raises(ValueError):
        is_live_or_zero_duration(True)
