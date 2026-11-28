"""AST and import boundary linting tests for provider isolation (SR-15, SE-6, FR-8.1, NFR-10).

Enforces that ONLY provider/live.py and auth/oauth.py may import HTTP or Google client libraries,
and domain modules never import concrete providers directly.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from yt_intel_mcp.config import AppConfig
from yt_intel_mcp.provider.fixture import FixtureYouTubeProvider
from yt_intel_mcp.provider.live import LiveYouTubeProvider
from yt_intel_mcp.server import (
    ServerRuntime,
    build_server_runtime,
    create_base_server,
    create_server,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "yt_intel_mcp"

FORBIDDEN_HTTP_CLIENT_MODULES: frozenset[str] = frozenset(
    {
        "aiohttp",
        "google",
        "google_auth_oauthlib",
        "googleapiclient",
        "http.client",
        "httpx",
        "requests",
        "urllib.error",
        "urllib.request",
        "urllib3",
    }
)

ALLOWED_HTTP_FILES: frozenset[Path] = frozenset(
    {
        (SRC_ROOT / "provider" / "live.py").resolve(),
        (SRC_ROOT / "auth" / "oauth.py").resolve(),
    }
)

DOMAIN_SUBDIRS: tuple[str, ...] = (
    "tools",
    "playlist",
    "similarity",
    "confirmation",
    "validation",
)

DOMAIN_SINGLE_FILES: tuple[str, ...] = (
    "cache.py",
    "store.py",
    "models.py",
    "errors.py",
    "durations.py",
    "sanitize.py",
)


def _iter_python_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*.py"):
        if "__pycache__" not in path.parts:
            yield path.resolve()


def _extract_imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    """Return all imported module names and their line numbers from an AST tree."""
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, node.lineno))
    return imports


def test_import_lint_no_external_http_outside_provider_and_oauth() -> None:
    """Only provider/live.py and auth/oauth.py may import HTTP libraries (SE-6, FR-8.1)."""
    violations: list[str] = []

    for file_path in _iter_python_files(SRC_ROOT):
        if file_path in ALLOWED_HTTP_FILES:
            continue

        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        imported_modules = _extract_imported_modules(tree)

        for mod_name, lineno in imported_modules:
            for forbidden in FORBIDDEN_HTTP_CLIENT_MODULES:
                if mod_name == forbidden or mod_name.startswith(f"{forbidden}."):
                    violations.append(
                        f"{file_path.relative_to(REPO_ROOT)}:{lineno} imports '{mod_name}' "
                        f"(forbidden outside provider/live.py and auth/oauth.py)"
                    )

    assert not violations, "HTTP library boundary violations found:\n" + "\n".join(violations)


def test_import_lint_domain_modules_never_import_concrete_providers() -> None:
    """Domain modules must depend only on YouTubeProvider protocol (SE-6, INV-18)."""
    concrete_providers = {"LiveYouTubeProvider", "FixtureYouTubeProvider"}
    violations: list[str] = []

    domain_files: list[Path] = []
    for subdir in DOMAIN_SUBDIRS:
        dir_path = SRC_ROOT / subdir
        if dir_path.is_dir():
            domain_files.extend(_iter_python_files(dir_path))

    for single_file in DOMAIN_SINGLE_FILES:
        target = SRC_ROOT / single_file
        if target.is_file():
            domain_files.append(target.resolve())

    for file_path in domain_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in concrete_providers:
                        rel_path = file_path.relative_to(REPO_ROOT)
                        violations.append(
                            f"{rel_path}:{node.lineno} imports '{alias.name}' "
                            f"(domain modules must only depend on YouTubeProvider protocol)"
                        )

    assert not violations, "Concrete provider boundary violations found:\n" + "\n".join(violations)


def test_import_lint_statistics_never_in_forbidden_metadata_requests() -> None:
    """Metadata queries must never request the statistics part (FR-1.3, FR-2.2, INV-01)."""
    checked_files = [
        SRC_ROOT / "provider" / "fixture.py",
        SRC_ROOT / "provider" / "live.py",
        SRC_ROOT / "cache.py",
    ]

    for file_path in checked_files:
        if not file_path.is_file():
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "part"
                        and isinstance(keyword.value, ast.Constant)
                        and "statistics" in str(keyword.value.value)
                    ):
                        pytest.fail(
                            f"File {file_path.name}:{node.lineno} passes 'statistics' part: "
                            f"{keyword.value.value!r}"
                        )


@pytest.mark.anyio
async def test_server_runtime_initialization_registers_exact_tools_and_resources(
    tmp_path: Path,
) -> None:
    """build_server_runtime registers exactly the 8 SRS Section 3.1 tools and 2 static resources."""
    config = AppConfig(
        provider_mode="fixture",
        data_dir=tmp_path / "data",
        fixture_dir=REPO_ROOT / "tests" / "fixtures",
    )
    runtime = build_server_runtime(config)
    assert isinstance(runtime, ServerRuntime)
    assert isinstance(runtime.base_provider, FixtureYouTubeProvider)
    assert runtime.cache is not None

    tools = await runtime.server.list_tools()
    tool_names = {t.name for t in tools}
    expected_tools = {
        "get_video_details",
        "get_similar_videos",
        "get_recommendations",
        "analyze_engagement",
        "draft_curated_playlist",
        "create_curated_playlist",
        "get_quota_status",
        "get_auth_status",
    }
    assert tool_names == expected_tools

    resources = await runtime.server.list_resources()
    resource_uris = {str(r.uri) for r in resources}
    expected_resources = {
        "youtube://metrics/quota",
        "youtube://user/context",
    }
    assert resource_uris == expected_resources


@pytest.mark.anyio
async def test_server_runtime_live_provider_mode(tmp_path: Path) -> None:
    """build_server_runtime wires LiveYouTubeProvider when provider_mode is 'live'."""
    config = AppConfig(
        provider_mode="live",
        data_dir=tmp_path / "data",
    )
    runtime = build_server_runtime(config)
    assert isinstance(runtime.base_provider, LiveYouTubeProvider)


@pytest.mark.anyio
async def test_server_runtime_cache_disabled_option(tmp_path: Path) -> None:
    """build_server_runtime bypasses caching layer when enable_cache is False."""
    config = AppConfig(
        provider_mode="fixture",
        data_dir=tmp_path / "data",
        fixture_dir=REPO_ROOT / "tests" / "fixtures",
    )
    runtime = build_server_runtime(config, enable_cache=False)
    assert runtime.cache is None
    assert runtime.provider is runtime.base_provider


@pytest.mark.anyio
async def test_create_base_server_and_unregistered_tools_option() -> None:
    """create_base_server and create_server(register_tools=False) produce empty server."""
    base_server = create_base_server()
    assert await base_server.list_tools() == []

    unregistered = create_server(register_tools=False)
    assert await unregistered.list_tools() == []
