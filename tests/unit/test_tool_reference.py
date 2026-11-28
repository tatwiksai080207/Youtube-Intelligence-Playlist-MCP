"""Unit tests for tool reference generator and zero drift check (SE-7, NFR-9, C-03)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "src" / "yt_intel_mcp" / "schemas"
TOOL_REFERENCE_PATH = ROOT / "docs" / "developer" / "tool-reference.md"


def _load_generator_module() -> ModuleType:
    script_path = ROOT / "scripts" / "generate_tool_reference.py"
    spec = importlib.util.spec_from_file_location("generate_tool_reference", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    return _load_generator_module()


def test_generate_tool_reference_renders_all_schemas(generator: ModuleType) -> None:
    output = generator.generate_tool_reference()
    schema_files = list(SCHEMAS_DIR.glob("*.json"))
    assert len(schema_files) > 0

    for schema_file in schema_files:
        tool_name = schema_file.stem
        assert f"### `{tool_name}`" in output, f"Missing tool section for {tool_name}"
        assert f"[{tool_name}](#{tool_name.replace('_', '-')})" in output


def test_generate_tool_reference_includes_quota_and_side_effects(generator: ModuleType) -> None:
    output = generator.generate_tool_reference()
    assert "- **Quota Cost:**" in output
    assert "- **Side Effects:**" in output
    assert "- **SRS Requirements:**" in output

    # Check key tools explicitly
    assert "1 unit (single videos.list call)" in output
    assert "preflights worst case 50 + 50 * max_videos units" in output.lower()
    assert "0 units (zero YouTube Data API calls)" in output


def test_generate_tool_reference_includes_resources(generator: ModuleType) -> None:
    output = generator.generate_tool_reference()
    assert "### `youtube://metrics/quota`" in output
    assert "### `youtube://user/context`" in output
    assert "Daily Quota Metrics" in output
    assert "User Context and Topic Profile" in output
    assert "units.remaining" in output
    assert "topic_distribution" in output


def test_tool_reference_docs_match_generated_without_drift(generator: ModuleType) -> None:
    assert TOOL_REFERENCE_PATH.is_file(), f"{TOOL_REFERENCE_PATH} does not exist"
    disk_content = TOOL_REFERENCE_PATH.read_text(encoding="utf-8")
    generated = generator.generate_tool_reference()
    assert disk_content == generated, (
        "docs/developer/tool-reference.md is out of date with src/yt_intel_mcp/schemas/*.json. "
        "Run `python scripts/generate_tool_reference.py` to synchronize."
    )


def test_generate_tool_reference_cli_check_success(
    generator: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["generate_tool_reference.py", "--check"])
    exit_code = generator.main()
    assert exit_code == 0


def test_generate_tool_reference_cli_check_fails_on_drift(
    generator: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_doc = tmp_path / "tool-reference.md"
    fake_doc.write_text("Outdated content\n", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["generate_tool_reference.py", "--check", "--output", str(fake_doc)],
    )
    exit_code = generator.main()
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "Drift detected" in err
