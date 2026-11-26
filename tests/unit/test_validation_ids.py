"""Unit tests for YouTube ID, handle, URL, and range validation (UT_ID, FR-1.1, FR-2.1)."""

# ruff: noqa: N802
from __future__ import annotations

import pytest

from yt_intel_mcp.models import EventSource
from yt_intel_mcp.validation import (
    ChannelReference,
    extract_channel_id,
    extract_playlist_id,
    extract_video_id,
    parse_channel_reference,
    validate_float_range,
    validate_int_range,
    validate_max_results,
    validate_scoring_weights,
    validate_sources,
    validate_timeframe,
)


@pytest.mark.parametrize(
    ("raw_input", "expected_id"),
    [
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("  a-B_012345z  ", "a-B_012345z"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?feature=share&v=a1B2c3D4e5F", "a1B2c3D4e5F"),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("http://youtu.be/dQw4w9WgXcQ?t=10", "dQw4w9WgXcQ"),
    ],
)
def test_UT_ID_extract_video_id_accepts_valid_ids_and_urls(
    raw_input: str, expected_id: str
) -> None:
    assert extract_video_id(raw_input) == expected_id


@pytest.mark.parametrize(
    ("raw_input", "expected_kind", "expected_value"),
    [
        ("UCuAXFkgsw1L7xaCfnd5JJOw", "channel_id", "UCuAXFkgsw1L7xaCfnd5JJOw"),
        ("  UC_x5XG1OV2P6uZZ5FSM9Ttw  ", "channel_id", "UC_x5XG1OV2P6uZZ5FSM9Ttw"),
        ("@SystemsCraft", "handle", "@SystemsCraft"),
        ("@code.mechanics-01", "handle", "@code.mechanics-01"),
        (
            "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw",
            "channel_id",
            "UCuAXFkgsw1L7xaCfnd5JJOw",
        ),
        (
            "https://m.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw/",
            "channel_id",
            "UC_x5XG1OV2P6uZZ5FSM9Ttw",
        ),
        ("https://www.youtube.com/@SystemsCraft", "handle", "@SystemsCraft"),
        ("https://youtube.com/@SystemsCraft/videos", "handle", "@SystemsCraft"),
        ("https://www.youtube.com/@code.mechanics-01/playlists", "handle", "@code.mechanics-01"),
    ],
)
def test_UT_ID_parse_channel_reference_accepts_ids_handles_and_urls(
    raw_input: str, expected_kind: str, expected_value: str
) -> None:
    ref = parse_channel_reference(raw_input)
    assert isinstance(ref, ChannelReference)
    assert ref.kind == expected_kind
    assert ref.value == expected_value
    assert extract_channel_id(raw_input) == expected_value


@pytest.mark.parametrize(
    ("raw_input", "expected_id"),
    [
        ("PL1234567890abcdef", "PL1234567890abcdef"),
        ("PL_SYNTH_STUDY_001", "PL_SYNTH_STUDY_001"),
        ("LL_SYNTH_USER_001", "LL_SYNTH_USER_001"),
        ("OLAK5uy_k9x8y7z6a5b4", "OLAK5uy_k9x8y7z6a5b4"),
        ("https://www.youtube.com/playlist?list=PL1234567890abcdef", "PL1234567890abcdef"),
    ],
)
def test_UT_ID_extract_playlist_id_accepts_valid_ids_and_urls(
    raw_input: str, expected_id: str
) -> None:
    assert extract_playlist_id(raw_input) == expected_id


def test_UT_ID_range_bounds_and_scoring_weights_accept_valid_values() -> None:
    assert validate_int_range(1, "count", minimum=1, maximum=50) == 1
    assert validate_int_range(50, "count", minimum=1, maximum=50) == 50
    assert validate_float_range(0, "weight", minimum=0.0, maximum=1.0) == 0.0
    assert validate_float_range(0.35, "weight", minimum=0.0, maximum=1.0) == pytest.approx(0.35)
    assert validate_max_results(10) == 10
    assert validate_max_results(50) == 50

    weights = validate_scoring_weights({"title": 0.6, "tags": 0.0, "duration": 0.4})
    assert weights == {"title": 0.6, "tags": 0.0, "duration": 0.4}

    sources = validate_sources(["liked_video", "subscription"])
    assert sources == (EventSource.LIKED_VIDEO, EventSource.SUBSCRIPTION)
    assert validate_timeframe("90d") == "90d"
    assert validate_timeframe("all") == "all"
