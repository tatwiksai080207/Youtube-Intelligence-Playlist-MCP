"""Contract tests for MF-04 playlist tool JSON Schemas and loader helpers (NFR-5, FR-5)."""

# ruff: noqa: N802
from __future__ import annotations

import re
from typing import Any

import pytest

from yt_intel_mcp.config import PlaylistConfig
from yt_intel_mcp.schemas import (
    ALL_SCHEMA_NAMES,
    ANALYSIS_SCHEMA_NAMES,
    PLAYLIST_SCHEMA_NAMES,
    list_schema_names,
    load_schema,
)

FORBIDDEN_POPULARITY_KEYS = {
    "view_count",
    "viewCount",
    "like_count",
    "likeCount",
    "dislike_count",
    "comment_count",
    "favorite_count",
    "subscriber_count",
    "subscriberCount",
    "video_count",
    "statistics",
}

FORBIDDEN_UNTRUSTED_APPROVAL_KEYS = {
    "token",
    "confirmation_token",
    "approved",
    "confirm",
    "video_ids",
    "videos",
    "title",
    "privacy_status",
    "channel_id",
}


def test_NFR_5_playlist_schema_registry_and_discovery() -> None:
    expected = ("draft_curated_playlist", "create_curated_playlist")
    assert expected == PLAYLIST_SCHEMA_NAMES
    assert ALL_SCHEMA_NAMES == ANALYSIS_SCHEMA_NAMES + PLAYLIST_SCHEMA_NAMES
    discovered = set(list_schema_names())
    assert set(ALL_SCHEMA_NAMES).issubset(discovered)


@pytest.mark.parametrize("tool_name", PLAYLIST_SCHEMA_NAMES)
def test_NFR_5_playlist_schemas_are_strict_draft_2020_12(tool_name: str) -> None:
    schema = load_schema(tool_name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == f"https://yt-intel-mcp.local/schemas/{tool_name}.json"
    assert schema["title"] == tool_name
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert isinstance(schema["properties"], dict)
    assert set(schema["properties"]).isdisjoint(FORBIDDEN_POPULARITY_KEYS)


def test_NFR_5_and_FR_5_1_draft_schema_bounds_and_defaults() -> None:
    schema = load_schema("draft_curated_playlist")
    assert schema["required"] == ["topic", "target_total_minutes"]

    props: dict[str, dict[str, Any]] = schema["properties"]
    expected_keys = {
        "topic",
        "target_total_minutes",
        "tolerance_percent",
        "max_video_minutes",
        "max_videos",
        "language",
        "allow_unknown_language",
        "title",
        "privacy_status",
    }
    assert set(props) == expected_keys

    assert props["topic"]["type"] == "string"
    assert props["topic"]["minLength"] >= 1
    assert props["target_total_minutes"]["type"] == "number"
    assert props["target_total_minutes"]["minimum"] >= 1

    defaults = PlaylistConfig()
    assert props["tolerance_percent"]["default"] == pytest.approx(
        defaults.duration_tolerance_fraction * 100.0
    )
    assert props["tolerance_percent"]["minimum"] == 0.0
    assert props["tolerance_percent"]["maximum"] <= 50.0

    assert props["max_videos"]["type"] == "integer"
    assert props["max_videos"]["minimum"] == 1
    assert props["max_videos"]["maximum"] == 50
    assert props["max_videos"]["default"] == defaults.default_max_videos

    assert props["allow_unknown_language"]["type"] == "boolean"
    assert props["allow_unknown_language"]["default"] is defaults.allow_unknown_language

    assert props["privacy_status"]["enum"] == ["private", "unlisted", "public"]
    assert props["privacy_status"]["default"] == defaults.default_privacy_status

    lang_pattern = re.compile(props["language"]["pattern"])
    assert lang_pattern.fullmatch("en")
    assert lang_pattern.fullmatch("en-GB")
    assert lang_pattern.fullmatch("pt-BR")
    assert not lang_pattern.fullmatch("english language with spaces")


def test_INV_13_INV_14_create_curated_playlist_accepts_draft_id_only() -> None:
    schema = load_schema("create_curated_playlist")
    assert schema["required"] == ["draft_id"]
    assert schema["additionalProperties"] is False

    props: dict[str, dict[str, Any]] = schema["properties"]
    assert set(props) == {"draft_id"}
    assert set(props).isdisjoint(FORBIDDEN_UNTRUSTED_APPROVAL_KEYS)

    draft_id_spec = props["draft_id"]
    assert draft_id_spec["type"] == "string"
    assert draft_id_spec["minLength"] >= 8
    draft_pattern = re.compile(draft_id_spec["pattern"])
    assert draft_pattern.fullmatch("draft_20261126_abc123")
    assert not draft_pattern.fullmatch("draft with spaces")


def test_NFR_9_playlist_tool_descriptions_state_semantics_and_side_effects() -> None:
    draft_desc = load_schema("draft_curated_playlist")["description"].lower()
    assert "draft" in draft_desc
    assert "read only" in draft_desc or "without modifying" in draft_desc

    create_desc = load_schema("create_curated_playlist")["description"].lower()
    assert "confirmation" in create_desc
    assert "write" in create_desc
