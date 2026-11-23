"""Validate the Second Brain structure, note metadata, and links (SB-1)."""

import re
from datetime import date
from pathlib import Path

from _validation import read_frontmatter, resolve_brain_link, run_validator, wiki_targets

PARA_FOLDERS = ("inbox", "projects", "areas", "resources", "archive")
NOTE_TYPES = (
    "reference",
    "concept",
    "architecture",
    "security",
    "project",
    "decision",
    "session",
    "ai-session",
    "stage-review",
    "skill-note",
    "index",
    "log",
)
NOTE_STATUSES = ("inbox", "distilled", "archived")
GITHUB_NUMBER = re.compile(r"#[1-9][0-9]*")
DATE_FORMAT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
NO_REQUIREMENT_REASON = re.compile(r"^\s*(?:[-*] )?Requirements?:\s*n/a\s*[—:-]\s*\S", re.I | re.M)
IDS_FILE = Path(__file__).with_name("srs_ids.txt")


def is_date(value: object) -> bool:
    if type(value) is date:
        return True
    if not isinstance(value, str) or not DATE_FORMAT.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_metadata(metadata: dict[str, object], body: str, allowed_ids: set[str]) -> list[str]:
    errors = []
    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title must be a non-empty string")
    if metadata.get("type") not in NOTE_TYPES:
        errors.append("type must be a valid brain note type")
    if metadata.get("status") not in NOTE_STATUSES:
        errors.append("status must be inbox, distilled, or archived")
    for field in ("created", "updated"):
        if not is_date(metadata.get(field)):
            errors.append(f"{field} must be a YYYY-MM-DD date")
    for field in ("authors", "tags", "sources"):
        values = metadata.get(field)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            errors.append(f"{field} must be a non-empty list of strings")

    requirements = metadata.get("requirements")
    if requirements == ["n/a"]:
        if not NO_REQUIREMENT_REASON.search(body):
            errors.append(
                'explain requirements: ["n/a"] in the body with "Requirements: n/a — reason"'
            )
    elif (
        not isinstance(requirements, list)
        or not requirements
        or any(not isinstance(value, str) or value not in allowed_ids for value in requirements)
    ):
        errors.append("requirements must list valid SRS v1.0 or R-2 requirement IDs")
    for field in ("issues", "prs"):
        refs = metadata.get(field)
        if not isinstance(refs, list) or any(
            not isinstance(ref, str) or not GITHUB_NUMBER.fullmatch(ref) for ref in refs
        ):
            errors.append(f"{field} must be a list of GitHub references such as '#12'")
    return errors


def validate_brain(root: Path) -> list[str]:
    brain = root / "brain"
    if not brain.is_dir():
        return ["brain: missing directory"]
    errors = [
        f"brain/{folder}: missing PARA directory"
        for folder in PARA_FOLDERS
        if not (brain / folder).is_dir()
    ]
    index = brain / "index.md"
    log = brain / "log.md"
    for entry in (index, log):
        if not entry.is_file():
            errors.append(f"{entry.relative_to(root)}: missing entry point")

    allowed_ids = {
        line.strip()
        for line in IDS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    notes = sorted(path for path in brain.rglob("*.md") if path.is_file())
    indexed_notes: set[Path] = set()
    for path in notes:
        label = path.relative_to(root)
        try:
            metadata, body = read_frontmatter(path)
        except (OSError, UnicodeError, ValueError) as error:
            errors.append(f"{label}: {error}")
            continue
        errors.extend(
            f"{label}: {error}" for error in validate_metadata(metadata, body, allowed_ids)
        )

        for target in wiki_targets(body):
            linked = resolve_brain_link(brain, target, path)
            if linked is None:
                errors.append(f"{label}: unresolved wikilink [[{target}]]")
            elif path == index:
                indexed_notes.add(linked)

    for path in notes:
        if path != index and path not in indexed_notes:
            errors.append(f"{path.relative_to(root)}: missing wikilink in brain/index.md")
    return errors


if __name__ == "__main__":
    raise SystemExit(run_validator(validate_brain, "Brain"))
