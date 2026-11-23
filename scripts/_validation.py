"""Shared Markdown validation helpers for the repository checks."""

import argparse
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import yaml

# Skip Markdown examples and comments. A citation must appear in the visible body.
WIKILINK_PATTERN = re.compile(
    r"^ {0,3}(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^ {0,3}(?P=fence)[`~]*[ \t]*$"
    r"|(?P<ticks>`+)[^`\n]+(?P=ticks)"
    r"|<!--.*?-->"
    r"|(?<!\\)\[\[(?P<link>[^\[\]\n]+)\]\]",
    re.MULTILINE | re.DOTALL,
)


def read_frontmatter(path: Path) -> tuple[dict[str, object], str]:
    opening, _, rest = path.read_text(encoding="utf-8-sig").partition("\n")
    closing = re.search(r"^---[ \t]*$", rest, re.MULTILINE)
    if opening.strip() != "---" or closing is None:
        raise ValueError("expected YAML frontmatter delimited by '---' lines")

    try:
        metadata = yaml.safe_load(rest[: closing.start()])
    except yaml.YAMLError as error:
        raise ValueError("invalid YAML frontmatter") from error
    if not isinstance(metadata, dict):
        raise ValueError("YAML frontmatter must be a mapping")
    return metadata, rest[closing.end() :]


def wiki_targets(body: str) -> Iterator[str]:
    for match in WIKILINK_PATTERN.finditer(body):
        if (link := match.group("link")) is not None:
            target = link.split("|", 1)[0].removesuffix("\\").strip()
            yield target


def resolve_brain_link(brain: Path, target: str, source: Path) -> Path | None:
    target, anchor, _ = target.partition("#")
    if not target and anchor:
        return source  # A heading or block reference in the current note.
    if not target.startswith("brain/"):
        return None

    path = brain / target.removeprefix("brain/")
    if target.endswith("/"):
        path = path.resolve()
        return path if path.is_relative_to(brain) and path.is_dir() else None
    if path.suffix != ".md":
        path = path.with_name(f"{path.name}.md")
    path = path.resolve()
    return path if path.is_relative_to(brain) and path.is_file() else None


def run_validator(validate: Callable[[Path], list[str]], name: str) -> int:
    parser = argparse.ArgumentParser(description=f"Validate the repository's {name}.")
    parser.add_argument(
        "root",
        type=Path,
        nargs="?",
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the repository containing this script)",
    )
    root = parser.parse_args().root.resolve()
    try:
        errors = validate(root)
    except (OSError, UnicodeError) as error:
        print(f"{name}: {error}", file=sys.stderr)
        return 1
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"{name} validation passed.")
    return 0
