"""Validate skill frontmatter and citations to distilled brain notes (SB-3)."""

import re
from pathlib import Path

from _validation import read_frontmatter, resolve_brain_link, run_validator, wiki_targets

SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def cites_distilled_note(root: Path, skill: Path, body: str) -> bool:
    for target in wiki_targets(body):
        note = resolve_brain_link(root / "brain", target, skill)
        if note is None or not target.startswith("brain/") or not note.is_file():
            continue
        try:
            metadata, _ = read_frontmatter(note)
        except (OSError, UnicodeError, ValueError):
            continue
        if metadata.get("status") == "distilled":
            return True
    return False


def validate_skills(root: Path) -> list[str]:
    skills = root / "skills"
    if not skills.is_dir():
        return ["skills: missing directory"]
    errors = []
    for folder in sorted(skills.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        skill = folder / "SKILL.md"
        label = skill.relative_to(root)
        if not skill.is_file():
            errors.append(f"{label}: missing skill file")
            continue
        try:
            metadata, body = read_frontmatter(skill)
        except (OSError, UnicodeError, ValueError) as error:
            errors.append(f"{label}: {error}")
            continue

        name = metadata.get("name")
        if not isinstance(name, str) or len(name) > 64 or not SKILL_NAME.fullmatch(name):
            errors.append(f"{label}: invalid skill name")
        elif name != folder.name:
            errors.append(f"{label}: name must match its folder")

        description = metadata.get("description")
        if not isinstance(description, str) or not description.strip() or len(description) > 1024:
            errors.append(f"{label}: description must be a string of 1 to 1024 characters")

        if not cites_distilled_note(root, skill, body):
            errors.append(f"{label}: cite at least one distilled brain note in the body")
    return errors


if __name__ == "__main__":
    raise SystemExit(run_validator(validate_skills, "Skill"))
