"""Offline validator CLI coverage for SB-1 and SB-3."""

# ruff: noqa: N802
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "validators"
NOTE = "brain/resources/fixture.md"
SKILL = "skills/sample-skill/SKILL.md"


@pytest.fixture
def validator_repo(tmp_path: Path) -> Path:
    brain = tmp_path / "brain"
    for folder in ("inbox", "projects", "areas", "resources", "archive"):
        (brain / folder).mkdir(parents=True)

    note = (FIXTURES / "valid-note.md").read_text(encoding="utf-8")
    (tmp_path / NOTE).write_text(note, encoding="utf-8")
    frontmatter, _ = note.rsplit("---\n", 1)
    for kind, body in (
        ("index", "- [[brain/resources/fixture]]\n- [[brain/log.md|Activity log]]"),
        ("log", "- [[brain/resources/fixture.md]]"),
    ):
        metadata = frontmatter.replace("type: reference", f"type: {kind}")
        (brain / f"{kind}.md").write_text(f"{metadata}---\n\n{body}\n", encoding="utf-8")

    skill = tmp_path / SKILL
    skill.parent.mkdir(parents=True)
    skill.write_text((FIXTURES / "valid-skill.md").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def run_validator(repo: Path, name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"validate_{name}.py"), str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


@pytest.mark.parametrize("name", ["brain", "skills"])
def test_TQ_1_valid_repository_passes(validator_repo: Path, name: str) -> None:
    result = run_validator(validator_repo, name)
    assert result.returncode == 0, result.stderr
    assert "validation passed" in result.stdout
    assert not result.stderr


@pytest.mark.parametrize(("name", "file"), [("brain", NOTE), ("skills", SKILL)])
@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("# Missing frontmatter\n", "delimited by"),
        ("---\nname: sample-skill\n", "delimited by"),
        ("---\nname: [broken\n---\n", "invalid YAML"),
        ("---\n- list\n---\n", "must be a mapping"),
        ("---\n---\n", "must be a mapping"),
    ],
)
def test_TQ_4_invalid_frontmatter_fails(
    validator_repo: Path, name: str, file: str, content: str, message: str
) -> None:
    (validator_repo / file).write_text(content, encoding="utf-8")
    result = run_validator(validator_repo, name)
    assert result.returncode == 1
    assert f"{file}: " in result.stderr
    assert message in result.stderr


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("name: sample-skill", "name: different-skill", "name must match its folder"),
        ("name: sample-skill", "name: 12", "invalid skill name"),
        ("name: sample-skill", f"name: {'a' * 65}", "invalid skill name"),
        ("name: sample-skill", 'name: ""', "invalid skill name"),
        ("description: ", "other: ", "description must be a string"),
        ('"Synthetic description with a --- separator"', '""', "description must be a string"),
        (
            '"Synthetic description with a --- separator"',
            "x" * 1025,
            "description must be a string",
        ),
        ("brain/resources/fixture.md", "brain/resources/missing.md", "cite at least one"),
        ("brain/resources/fixture.md", "brain/resources/", "cite at least one"),
    ],
)
def test_TQ_4_invalid_skill_fields_or_citation_fail(
    validator_repo: Path, old: str, new: str, message: str
) -> None:
    replace(validator_repo / SKILL, old, new)
    result = run_validator(validator_repo, "skills")
    assert result.returncode == 1
    assert message in result.stderr


def test_TQ_4_skill_rejects_non_distilled_reference(validator_repo: Path) -> None:
    replace(validator_repo / NOTE, "status: distilled", "status: inbox")
    result = run_validator(validator_repo, "skills")
    assert result.returncode == 1
    assert "cite at least one" in result.stderr


def test_TQ_4_skill_rejects_metadata_and_example_links(validator_repo: Path) -> None:
    (validator_repo / SKILL).write_bytes((FIXTURES / "invalid-skill.md").read_bytes())
    result = run_validator(validator_repo, "skills")
    assert result.returncode == 1
    for message in ("invalid skill name", "description must be a string", "cite at least one"):
        assert message in result.stderr


def test_TQ_4_skill_requires_file_in_folder(validator_repo: Path) -> None:
    (validator_repo / SKILL).unlink()
    result = run_validator(validator_repo, "skills")
    assert result.returncode == 1
    assert f"{SKILL}: missing skill file" in result.stderr


@pytest.mark.parametrize("name", ["brain", "skills"])
def test_TQ_4_validator_requires_root_directory(validator_repo: Path, name: str) -> None:
    empty = validator_repo / "empty"
    empty.mkdir()
    result = run_validator(empty, name)
    assert result.returncode == 1
    assert "missing directory" in result.stderr


@pytest.mark.parametrize("folder", ["inbox", "projects", "areas", "resources", "archive"])
def test_TQ_4_brain_requires_para_directory(validator_repo: Path, folder: str) -> None:
    (validator_repo / "brain" / folder).rename(validator_repo / folder)
    result = run_validator(validator_repo, "brain")
    assert result.returncode == 1
    assert f"brain/{folder}: missing PARA directory" in result.stderr


@pytest.mark.parametrize("file", ["index.md", "log.md"])
def test_TQ_4_brain_requires_entry_point(validator_repo: Path, file: str) -> None:
    (validator_repo / "brain" / file).unlink()
    result = run_validator(validator_repo, "brain")
    assert result.returncode == 1
    assert f"brain/{file}: missing entry point" in result.stderr


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("title: Synthetic fixture note", "title: false", "title must be"),
        ("type: reference", "type: novel", "type must be"),
        ("status: distilled", "status: [inbox]", "status must be"),
        ("created: 2026-01-01", 'created: "2026-02-30"', "created must be"),
        ('updated: "2026-01-02"', "updated: 20260102", "updated must be"),
        ("authors: [Fixture Author]", "authors: []", "authors must be"),
        ("tags: [fixture]", "tags: [1]", "tags must be"),
        ("sources: ", "other: ", "sources must be"),
        ("[FR-5.1a, NFR-10, C-7, TQ-8, SE-7, SB-3]", "[]", "requirements must list"),
        ("[FR-5.1a, NFR-10, C-7, TQ-8, SE-7, SB-3]", "[SB-1, n/a]", "requirements must list"),
        ("[FR-5.1a, NFR-10, C-7, TQ-8, SE-7, SB-3]", "[n/a]", "explain requirements"),
        ('issues: ["#1"]', "issues: false", "issues must be"),
        ('prs: ["#2"]', 'prs: ["pending"]', "prs must be"),
    ],
)
def test_TQ_4_invalid_brain_fields_fail(
    validator_repo: Path, old: str, new: str, message: str
) -> None:
    replace(validator_repo / NOTE, old, new)
    result = run_validator(validator_repo, "brain")
    assert result.returncode == 1
    assert f"{NOTE}: {message}" in result.stderr


def test_TQ_1_brain_accepts_explained_na_and_pending_pr(validator_repo: Path) -> None:
    note = validator_repo / NOTE
    replace(note, "[FR-5.1a, NFR-10, C-7, TQ-8, SE-7, SB-3]", '["n/a"]')
    replace(note, 'prs: ["#2"]', "prs: []")
    with note.open("a", encoding="utf-8") as file:
        file.write("\nRequirements: n/a — synthetic navigation note.\n")
    result = run_validator(validator_repo, "brain")
    assert result.returncode == 0, result.stderr


def test_TQ_4_brain_reports_all_fixture_violations(validator_repo: Path) -> None:
    (validator_repo / NOTE).write_bytes((FIXTURES / "invalid-note.md").read_bytes())
    result = run_validator(validator_repo, "brain")
    assert result.returncode == 1
    for message in ("status must be", "requirements must list", "issues must be", "prs must be"):
        assert f"{NOTE}: {message}" in result.stderr
    assert "unresolved wikilink [[brain/resources/missing]]" in result.stderr


def test_TQ_4_brain_rejects_links_outside_vault(validator_repo: Path) -> None:
    replace(validator_repo / NOTE, "brain/index", "brain/../skills/sample-skill/SKILL.md")
    result = run_validator(validator_repo, "brain")
    assert result.returncode == 1
    assert "unresolved wikilink [[brain/../skills/sample-skill/SKILL.md]]" in result.stderr


def test_TQ_4_brain_requires_direct_index_link_to_each_note(validator_repo: Path) -> None:
    replace(validator_repo / "brain/index.md", "[[brain/resources/fixture]]", "fixture")
    result = run_validator(validator_repo, "brain")
    assert result.returncode == 1
    assert f"{NOTE}: missing wikilink in brain/index.md" in result.stderr
