"""Contract tests for TS-04 analysis tool JSON Schemas and loader helpers (NFR-5)."""

# ruff: noqa: N802
from __future__ import annotations

from typing import Any

import pytest

from yt_intel_mcp.config import SimilarityConfig
from yt_intel_mcp.models import EventSource
from yt_intel_mcp.schemas import ANALYSIS_SCHEMA_NAMES, list_schema_names, load_schema

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


def test_NFR_5_analysis_schema_registry_and_discovery() -> None:
    expected = (
        "get_video_details",
        "get_similar_videos",
        "get_similar_channels",
        "get_recommendations",
        "analyze_engagement",
    )
    assert expected == ANALYSIS_SCHEMA_NAMES
    discovered = set(list_schema_names())
    assert set(expected).issubset(discovered)


@pytest.mark.parametrize("tool_name", ANALYSIS_SCHEMA_NAMES)
def test_NFR_5_each_schema_is_strict_object_schema(tool_name: str) -> None:
    schema = load_schema(tool_name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == tool_name
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert isinstance(schema["properties"], dict)


def test_NFR_5_required_properties_and_bounds_match_srs() -> None:
    details = load_schema("get_video_details")
    assert details["required"] == ["video_id"]
    assert details["properties"]["video_id"]["type"] == "string"
    assert details["properties"]["video_id"]["minLength"] >= 11

    similar_videos = load_schema("get_similar_videos")
    assert similar_videos["required"] == ["video_id"]
    vid_max = similar_videos["properties"]["max_results"]
    assert vid_max["type"] == "integer"
    assert vid_max["minimum"] == 1
    assert vid_max["maximum"] == 50
    assert vid_max["default"] == 10

    similar_channels = load_schema("get_similar_channels")
    assert similar_channels["required"] == ["channel"]
    ch_max = similar_channels["properties"]["max_results"]
    assert ch_max["type"] == "integer"
    assert ch_max["minimum"] == 1
    assert ch_max["maximum"] == 50
    assert ch_max["default"] == 10

    recommendations = load_schema("get_recommendations")
    assert "required" not in recommendations
    rec_max = recommendations["properties"]["max_results"]
    assert rec_max["minimum"] == 1
    assert rec_max["maximum"] == 50
    sources = recommendations["properties"]["sources"]
    assert sources["type"] == "array"
    assert sources["uniqueItems"] is True
    assert sources["minItems"] == 1
    assert sources["items"]["enum"] == [
        EventSource.LIKED_VIDEO.value,
        EventSource.SUBSCRIPTION.value,
        EventSource.PLAYLIST_ITEM.value,
    ]
    assert set(sources["default"]) == {source.value for source in EventSource}

    engagement = load_schema("analyze_engagement")
    assert "required" not in engagement
    timeframe = engagement["properties"]["timeframe"]
    assert timeframe["type"] == "string"
    assert timeframe["enum"] == ["7d", "30d", "90d", "180d", "365d", "all"]
    assert timeframe["default"] == "90d"
    compare = engagement["properties"]["compare_with_previous_period"]
    assert compare["type"] == "boolean"
    assert compare["default"] is True


def test_INV_01_and_CT_1_scoring_weights_exclude_popularity_and_match_config() -> None:
    schema = load_schema("get_similar_videos")
    weights: dict[str, Any] = schema["properties"]["scoring_weights"]
    assert weights["type"] == "object"
    assert weights["additionalProperties"] is False
    assert weights["minProperties"] == 1

    props: dict[str, dict[str, Any]] = weights["properties"]
    assert set(props) == {"title", "tags", "description", "category", "duration"}
    assert set(props).isdisjoint(FORBIDDEN_POPULARITY_KEYS)

    defaults = SimilarityConfig()
    assert props["title"]["default"] == pytest.approx(defaults.title_weight)
    assert props["tags"]["default"] == pytest.approx(defaults.tags_weight)
    assert props["description"]["default"] == pytest.approx(defaults.description_weight)
    assert props["category"]["default"] == pytest.approx(defaults.category_weight)
    assert props["duration"]["default"] == pytest.approx(defaults.duration_weight)
    for field_spec in props.values():
        assert field_spec["type"] == "number"
        assert field_spec["minimum"] == 0.0
        assert field_spec["maximum"] == 1.0


@pytest.mark.parametrize(
    "bad_name",
    ["", "../get_video_details", "sub/get_video_details", "a\\b", "get_video_details.json"],
)
def test_load_schema_rejects_invalid_names(bad_name: str) -> None:
    with pytest.raises(ValueError, match="Invalid schema tool name"):
        load_schema(bad_name)


def test_load_schema_raises_for_missing_tool() -> None:
    with pytest.raises(FileNotFoundError, match="Tool JSON Schema not found"):
        load_schema("unknown_analysis_tool")
