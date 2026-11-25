"""Package-bundled JSON Schemas for yt-intel-mcp tools (NFR-5, ADR-0001)."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

__all__ = [
    "ANALYSIS_SCHEMA_NAMES",
    "list_schema_names",
    "load_schema",
]

ANALYSIS_SCHEMA_NAMES: tuple[str, ...] = (
    "get_video_details",
    "get_similar_videos",
    "get_similar_channels",
    "get_recommendations",
    "analyze_engagement",
)

_SCHEMA_PACKAGE = __package__ or "yt_intel_mcp.schemas"


def list_schema_names() -> tuple[str, ...]:
    """Return sorted tool schema names bundled under `yt_intel_mcp.schemas`."""
    package_dir = files(_SCHEMA_PACKAGE)
    names = [
        entry.name[:-5]
        for entry in package_dir.iterdir()
        if entry.is_file() and entry.name.endswith(".json")
    ]
    return tuple(sorted(names))


def load_schema(tool_name: str) -> dict[str, Any]:
    """Load and decode a bundled MCP tool input JSON Schema by tool name."""
    if (
        not tool_name
        or "/" in tool_name
        or "\\" in tool_name
        or ".." in tool_name
        or tool_name.endswith(".json")
    ):
        raise ValueError(f"Invalid schema tool name: {tool_name!r}")

    resource = files(_SCHEMA_PACKAGE).joinpath(f"{tool_name}.json")
    if not resource.is_file():
        raise FileNotFoundError(f"Tool JSON Schema not found: {tool_name!r}")

    raw = resource.read_text(encoding="utf-8")
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValueError(f"Schema {tool_name!r} must decode to a JSON object.")
    return {str(key): value for key, value in decoded.items()}
