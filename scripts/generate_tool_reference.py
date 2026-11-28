"""Generate docs/developer/tool-reference.md from JSON Schemas (SE-7, NFR-9, C-03).

This script reads all bundled MCP tool JSON schemas from src/yt_intel_mcp/schemas
and renders a comprehensive, human-readable tool and resource reference guide.
It supports a --check flag for continuous integration drift detection.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "src" / "yt_intel_mcp" / "schemas"
OUTPUT_PATH = ROOT / "docs" / "developer" / "tool-reference.md"

TOOL_METADATA: dict[str, dict[str, Any]] = {
    "get_video_details": {
        "srs_reqs": "FR-1.1, FR-1.4, INV-01",
        "side_effects": "None (read only, zero local or remote state modification)",
        "quota_cost": "1 unit (single videos.list call)",
        "error_codes": [
            "INVALID_ARGUMENT",
            "VIDEO_UNAVAILABLE",
            "UPSTREAM_ERROR",
            "QUOTA_EXHAUSTED",
        ],
    },
    "get_similar_videos": {
        "srs_reqs": "FR-1.1, FR-1.2, FR-1.3, FR-6.2, INV-01",
        "side_effects": "None (read only discovery and local TF IDF ranking)",
        "quota_cost": (
            "100 search units (or 1 search call in fixture mode) + 1 unit per candidate "
            "video batch (max 102 units)"
        ),
        "error_codes": [
            "INVALID_ARGUMENT",
            "VIDEO_UNAVAILABLE",
            "UPSTREAM_ERROR",
            "QUOTA_EXHAUSTED",
        ],
    },
    "get_similar_channels": {
        "srs_reqs": "FR-2.1, FR-2.2, FR-6.2, INV-01",
        "side_effects": "None (read only discovery and local metadata similarity)",
        "quota_cost": ("100 search units + 1 unit per candidate channel batch (max 102 units)"),
        "error_codes": [
            "INVALID_ARGUMENT",
            "CHANNEL_UNAVAILABLE",
            "UPSTREAM_ERROR",
            "QUOTA_EXHAUSTED",
        ],
    },
    "get_recommendations": {
        "srs_reqs": "FR-3.1, FR-3.2, FR-3.3, FR-6.2, INV-01",
        "side_effects": ("None (read only personal library aggregation and candidate scoring)"),
        "quota_cost": (
            "1 unit per personal library page + 100 search units per topic query + "
            "1 unit per candidate batch"
        ),
        "error_codes": [
            "INVALID_ARGUMENT",
            "INSUFFICIENT_USER_SIGNAL",
            "AUTH_REQUIRED",
            "AUTH_REAUTHORIZATION_REQUIRED",
            "UPSTREAM_ERROR",
            "QUOTA_EXHAUSTED",
        ],
    },
    "analyze_engagement": {
        "srs_reqs": "FR-4.1, FR-4.2, FR-4.3, FR-6.2, INV-01",
        "side_effects": ("None (read only library retrieval and local histogram aggregation)"),
        "quota_cost": (
            "1 unit per library page (subscriptions, playlists, playlist items, liked videos)"
        ),
        "error_codes": [
            "INVALID_ARGUMENT",
            "INSUFFICIENT_USER_SIGNAL",
            "AUTH_REQUIRED",
            "AUTH_REAUTHORIZATION_REQUIRED",
            "UPSTREAM_ERROR",
            "QUOTA_EXHAUSTED",
        ],
    },
    "draft_curated_playlist": {
        "srs_reqs": "FR-5.1, FR-5.1a, FR-5.2, FR-5.3, FR-6.2",
        "side_effects": (
            "Creates an immutable, expiring local draft in SQLite (no YouTube writes)"
        ),
        "quota_cost": (
            "Preflights worst case 50 + 50 * max_videos units; charges only actual "
            "discovery search and video list calls (100 search units + candidate batches)"
        ),
        "error_codes": [
            "INVALID_ARGUMENT",
            "CONSTRAINTS_UNSATISFIABLE",
            "UPSTREAM_ERROR",
            "QUOTA_EXHAUSTED",
        ],
    },
    "create_curated_playlist": {
        "srs_reqs": "FR-5.4, FR-5.5, FR-6.2, FR-7.1, FR-7.3",
        "side_effects": (
            "Modifies YouTube: inserts 1 new playlist and N playlist items into "
            "authenticated user channel"
        ),
        "quota_cost": (
            "Exact preflight and execution: 50 units (playlists.insert) + "
            "50 units * N items (playlistItems.insert)"
        ),
        "error_codes": [
            "INVALID_ARGUMENT",
            "DRAFT_NOT_FOUND",
            "DRAFT_EXPIRED",
            "DRAFT_STALE",
            "CONFIRMATION_DECLINED",
            "CONFIRMATION_EXPIRED",
            "CONFIRMATION_UNAVAILABLE",
            "AUTH_REQUIRED",
            "AUTH_REAUTHORIZATION_REQUIRED",
            "WRITE_CONSENT_REQUIRED",
            "CHANNEL_REQUIRED",
            "UPSTREAM_ERROR",
            "QUOTA_EXHAUSTED",
        ],
    },
    "get_quota_status": {
        "srs_reqs": "FR-6.1, FR-6.2, C-01, NFR-9",
        "side_effects": "None (purely local persistent SQLite ledger read)",
        "quota_cost": "0 units (zero YouTube Data API calls)",
        "error_codes": [
            "INVALID_ARGUMENT",
        ],
    },
    "get_auth_status": {
        "srs_reqs": "FR-7.2, NFR-3, NFR-7, NFR-9",
        "side_effects": (
            "None (purely local encrypted token store inspection, zero token logging)"
        ),
        "quota_cost": "0 units (zero YouTube Data API calls)",
        "error_codes": [
            "INVALID_ARGUMENT",
        ],
    },
}

RESOURCE_METADATA: list[dict[str, Any]] = [
    {
        "uri": "youtube://metrics/quota",
        "name": "Daily Quota Metrics",
        "mime_type": "application/json",
        "description": (
            "Real time daily quota usage, remaining limits, and reset timestamp "
            "for units and search calls."
        ),
        "quota_cost": "0 units (purely local read)",
        "payload_fields": [
            (
                "units.limit",
                "integer",
                "Configured daily quota units limit (default 10,000)",
            ),
            (
                "units.used",
                "integer",
                "Cumulative units consumed during the current Pacific Time day",
            ),
            (
                "units.remaining",
                "integer",
                "Remaining units available before upstream exhaustion",
            ),
            (
                "search_calls.limit",
                "integer",
                "Configured daily search.list calls limit (default 100)",
            ),
            (
                "search_calls.used",
                "integer",
                "Search calls dispatched during the current Pacific Time day",
            ),
            (
                "search_calls.remaining",
                "integer",
                "Remaining search calls available before exhaustion",
            ),
            (
                "reset_at",
                "string",
                "ISO 8601 timestamp of the next midnight Pacific Time reset",
            ),
            (
                "timezone",
                "string",
                "Quota tracking timezone (America/Los_Angeles)",
            ),
        ],
    },
    {
        "uri": "youtube://user/context",
        "name": "User Context and Topic Profile",
        "mime_type": "application/json",
        "description": (
            "Aggregated user context with zero PII, including channel ID, signal counts, "
            "and topic interest distribution."
        ),
        "quota_cost": "0 units (cached/local aggregate read)",
        "payload_fields": [
            (
                "channel_id",
                "string",
                "Authenticated YouTube channel ID or empty string",
            ),
            (
                "has_channel",
                "boolean",
                "Whether the authenticated user owns a YouTube channel",
            ),
            (
                "total_signals",
                "integer",
                "Total engagement signals aggregated across subscriptions, playlists, and likes",
            ),
            (
                "subscriptions_count",
                "integer",
                "Number of active channel subscriptions",
            ),
            (
                "playlists_count",
                "integer",
                "Number of user created or saved playlists",
            ),
            (
                "liked_videos_count",
                "integer",
                "Number of liked videos accessible in personal library",
            ),
            (
                "topic_distribution",
                "object",
                "Map of topic categories to normalized interest weights [0.0, 1.0]",
            ),
        ],
    },
]


def format_type(prop: dict[str, Any]) -> str:
    """Format schema property type including arrays and enums."""
    prop_type = prop.get("type", "any")
    if prop_type == "array":
        items = prop.get("items", {})
        item_type = items.get("type", "any")
        if "enum" in items:
            enums = ", ".join(f"`{val}`" for val in items["enum"])
            return f"array of {item_type} ({enums})"
        return f"array of {item_type}"
    if "enum" in prop:
        enums = ", ".join(f"`{val}`" for val in prop["enum"])
        return f"{prop_type} ({enums})"
    return str(prop_type)


def format_constraints(prop: dict[str, Any]) -> str:
    """Format property constraints like length, bounds, or patterns."""
    constraints: list[str] = []
    if "default" in prop:
        constraints.append(f"default: `{prop['default']}`")
    if "minimum" in prop:
        constraints.append(f"min: `{prop['minimum']}`")
    if "maximum" in prop:
        constraints.append(f"max: `{prop['maximum']}`")
    if "minLength" in prop:
        constraints.append(f"min length: `{prop['minLength']}`")
    if "maxLength" in prop:
        constraints.append(f"max length: `{prop['maxLength']}`")
    if "pattern" in prop:
        pattern = prop["pattern"].replace("|", "\\|")
        constraints.append(f"pattern: `{pattern}`")
    return "; ".join(constraints) if constraints else "None"


def generate_tool_reference() -> str:
    """Generate complete markdown reference from schemas and metadata."""
    schema_files = sorted(SCHEMAS_DIR.glob("*.json"))
    if not schema_files:
        raise FileNotFoundError(f"No JSON schema files found in {SCHEMAS_DIR}")

    lines: list[str] = [
        "# YouTube Video Intelligence MCP Server Tool and Resource Reference",
        "",
        (
            "This document is automatically generated from the bundled JSON Schemas under "
            "`src/yt_intel_mcp/schemas/`."
        ),
        (
            "It provides the canonical reference for all MCP tools, arguments, "
            "return payloads, quota costs, side effects, and resources."
        ),
        "",
        (
            "> Generated by `scripts/generate_tool_reference.py`. Do not edit directly; "
            "run the script or CI check to update."
        ),
        "",
        "## Table of Contents",
        "",
        "### MCP Tools",
    ]

    for schema_file in schema_files:
        tool_name = schema_file.stem
        lines.append(f"- [{tool_name}](#{tool_name.replace('_', '-')})")

    lines.extend(
        [
            "",
            "### MCP Resources",
            "- [youtube://metrics/quota](#youtubemetricsquota)",
            "- [youtube://user/context](#youtubeusercontext)",
            "",
            "---",
            "",
            "## MCP Tools",
            "",
        ]
    )

    for schema_file in schema_files:
        tool_name = schema_file.stem
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        meta = TOOL_METADATA.get(tool_name, {})

        title = schema.get("title", tool_name)
        description = schema.get("description", "No description provided.")
        required_fields = set(schema.get("required", []))
        properties = schema.get("properties", {})

        srs_reqs = meta.get("srs_reqs", "SRS Section 3.1")
        side_effects = meta.get("side_effects", "None")
        quota_cost = meta.get("quota_cost", "Varies by request")
        error_codes = meta.get("error_codes", ["INVALID_ARGUMENT", "UPSTREAM_ERROR"])

        lines.extend(
            [
                f"### `{title}`",
                "",
                f"**Description:** {description}",
                "",
                f"- **SRS Requirements:** `{srs_reqs}`",
                f"- **Side Effects:** {side_effects}",
                f"- **Quota Cost:** {quota_cost}",
                "",
                "#### Input Arguments",
                "",
            ]
        )

        if properties:
            lines.extend(
                [
                    "| Argument | Type | Required | Constraints | Description |",
                    "|---|---|---|---|---|",
                ]
            )
            for prop_name, prop_def in properties.items():
                is_req = "Yes" if prop_name in required_fields else "No"
                prop_type = format_type(prop_def)
                constraints = format_constraints(prop_def)
                prop_desc = prop_def.get("description", "").replace("|", "\\|")
                lines.append(
                    f"| `{prop_name}` | `{prop_type}` | {is_req} | {constraints} | {prop_desc} |"
                )
        else:
            lines.append("This tool accepts an empty JSON object `{}` with no input arguments.")

        lines.extend(
            [
                "",
                "#### Output Structure",
                "",
                (
                    "Every tool invocation returns an MCP CallToolResult with structured "
                    "JSON content following this top level envelope:"
                ),
                "",
                "```json",
                "{",
                '  "summary": "Human readable Markdown summary of the outcome",',
                '  "data": { ... },',
                '  "quota_used": {',
                '    "units": 0,',
                '    "search_calls": 0',
                "  }",
                "}",
                "```",
                "",
                "#### Possible Error Codes",
                "",
                (
                    "When validation fails or an upstream constraint is encountered, "
                    "`is_error` is set to `true` with one of the following codes:"
                ),
                "",
            ]
        )
        for code in error_codes:
            lines.append(f"- `{code}`")

        lines.extend(["", "---", ""])

    lines.extend(
        [
            "## MCP Resources",
            "",
            (
                "Resources allow MCP hosts to inspect live server metrics and aggregated "
                "user context over read only URIs without consuming YouTube API quota."
            ),
            "",
        ]
    )

    for res in RESOURCE_METADATA:
        uri = res["uri"]
        name = res["name"]
        mime = res["mime_type"]
        desc = res["description"]
        cost = res["quota_cost"]
        fields = res["payload_fields"]

        lines.extend(
            [
                f"### `{uri}`",
                "",
                f"**Resource Name:** {name}  ",
                f"**MIME Type:** `{mime}`  ",
                f"**Description:** {desc}  ",
                f"**Quota Cost:** {cost}",
                "",
                "#### JSON Payload Fields",
                "",
                "| Field | Type | Description |",
                "|---|---|---|",
            ]
        )
        for field_path, field_type, field_desc in fields:
            lines.append(f"| `{field_path}` | `{field_type}` | {field_desc} |")
        lines.extend(["", "---", ""])

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate docs/developer/tool-reference.md from JSON Schemas (SE-7, NFR-9, C-03)."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether tool-reference.md matches generated content without writing.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Target output path for the generated markdown reference.",
    )

    args = parser.parse_args()
    generated = generate_tool_reference()

    if args.check:
        if not args.output.is_file():
            print(
                f"Error: {args.output} does not exist. Run scripts/generate_tool_reference.py.",
                file=sys.stderr,
            )
            return 1
        current = args.output.read_text(encoding="utf-8")
        if current != generated:
            diff = difflib.unified_diff(
                current.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=str(args.output),
                tofile="generated",
            )
            print(
                f"Error: {args.output} is out of date with JSON Schemas. Drift detected:",
                file=sys.stderr,
            )
            sys.stderr.writelines(diff)
            print(
                "\nRun: python scripts/generate_tool_reference.py to synchronize documentation.",
                file=sys.stderr,
            )
            return 1
        print(f"Tool reference is up to date: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(f"Successfully generated tool reference at {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
