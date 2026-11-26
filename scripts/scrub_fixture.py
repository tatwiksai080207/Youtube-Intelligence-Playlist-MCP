"""Scrub recorded YouTube Data API v3 payloads of statistics, secrets, and PII (FR-8.2, NFR-7)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

FORBIDDEN_STATISTICS_KEYS = frozenset(
    {
        "statistics",
        "viewcount",
        "view_count",
        "likecount",
        "like_count",
        "dislikecount",
        "dislike_count",
        "commentcount",
        "comment_count",
        "favoritecount",
        "favorite_count",
        "subscribercount",
        "subscriber_count",
        "videocount",
        "video_count",
        "hiddensubscribercount",
    }
)

FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "access_token",
        "accesstoken",
        "refresh_token",
        "refreshtoken",
        "client_secret",
        "clientsecret",
        "client_id",
        "clientid",
        "id_token",
        "idtoken",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "secret",
        "bearer",
    }
)

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SECRET_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Google OAuth access token", re.compile(r"\bya29\.[A-Za-z0-9_-]{10,}")),
    ("Google OAuth refresh token", re.compile(r"\b1//[A-Za-z0-9_-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}")),
    ("GitHub PAT", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}")),
    ("Bearer header", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{10,}", re.IGNORECASE)),
)


def _scrub_string(value: str, user_id_map: Mapping[str, str] | None = None) -> str:
    cleaned = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    for _, pattern in SECRET_VALUE_PATTERNS:
        cleaned = pattern.sub("[REDACTED_SECRET]", cleaned)
    if user_id_map:
        for original, replacement in user_id_map.items():
            cleaned = cleaned.replace(original, replacement)
    return cleaned


def scrub_payload(
    data: Any,
    *,
    user_id_map: Mapping[str, str] | None = None,
) -> Any:
    """Recursively remove statistics, credentials, and PII from a JSON-compatible payload."""
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            key_str = str(key)
            lowered = key_str.lower()
            if lowered in FORBIDDEN_STATISTICS_KEYS or lowered in FORBIDDEN_SECRET_KEYS:
                continue
            if lowered == "part" and isinstance(value, str):
                parts = [p.strip() for p in value.split(",") if p.strip().lower() != "statistics"]
                result[key_str] = ",".join(parts)
                continue
            result[key_str] = scrub_payload(value, user_id_map=user_id_map)
        return result
    if isinstance(data, list):
        return [scrub_payload(item, user_id_map=user_id_map) for item in data]
    if isinstance(data, str):
        return _scrub_string(data, user_id_map=user_id_map)
    return data


def scan_payload_for_violations(data: Any, *, path: str = "$") -> list[str]:
    """Return human-readable violations if statistics, secrets, or emails remain in data."""
    violations: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            key_str = str(key)
            lowered = key_str.lower()
            child_path = f"{path}.{key_str}"
            if lowered in FORBIDDEN_STATISTICS_KEYS:
                violations.append(f"{child_path}: forbidden statistics key {key_str!r}")
            elif lowered in FORBIDDEN_SECRET_KEYS:
                violations.append(f"{child_path}: forbidden credential key {key_str!r}")
            elif lowered == "part" and isinstance(value, str) and "statistics" in value.lower():
                violations.append(f"{child_path}: forbidden statistics part parameter")
            else:
                violations.extend(scan_payload_for_violations(value, path=child_path))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            violations.extend(scan_payload_for_violations(item, path=f"{path}[{index}]"))
    elif isinstance(data, str):
        if EMAIL_PATTERN.search(data):
            violations.append(f"{path}: email-like identifier found")
        for label, pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(data):
                violations.append(f"{path}: {label} pattern found")
    return violations


def scrub_file(
    input_path: Path,
    output_path: Path | None = None,
    *,
    user_id_map: Mapping[str, str] | None = None,
    check_only: bool = False,
) -> list[str]:
    """Scrub or validate a JSON fixture file on disk, returning any remaining violations."""
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if check_only:
        return scan_payload_for_violations(raw, path=input_path.as_posix())
    cleaned = scrub_payload(raw, user_id_map=user_id_map)
    violations = scan_payload_for_violations(cleaned, path=input_path.as_posix())
    target = output_path or input_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return violations


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for scrubbing or checking JSON fixture files."""
    parser = argparse.ArgumentParser(
        description="Scrub statistics, secrets, and PII from fixtures."
    )
    parser.add_argument("input", type=Path, help="Input JSON fixture file path.")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output JSON path.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate without modifying the file; exit non-zero if violations exist.",
    )
    parser.add_argument(
        "--map-user",
        action="append",
        default=[],
        metavar="ORIG=SYNTH",
        help="Replace real user or channel IDs with synthetic identifiers.",
    )
    args = parser.parse_args(argv)
    user_map: dict[str, str] = {}
    for entry in args.map_user:
        if "=" not in entry:
            print(f"Invalid --map-user value {entry!r}; expected ORIG=SYNTH.", file=sys.stderr)
            return 2
        orig, synth = entry.split("=", 1)
        user_map[orig] = synth

    violations = scrub_file(
        args.input,
        args.output,
        user_id_map=user_map or None,
        check_only=args.check,
    )
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1
    action = "verified clean" if args.check else "scrubbed cleanly"
    print(f"{args.input}: {action}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
