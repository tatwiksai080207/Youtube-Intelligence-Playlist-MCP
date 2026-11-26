"""Shared MCP client and server system test harness (SR-09, TQ-3)."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import anyio
import mcp.types as types
import pytest
from mcp.client.session import ClientRequestContext, ClientSession, ElicitationFnT
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.mcpserver import MCPServer
from mcp.shared.memory import create_client_server_memory_streams

from yt_intel_mcp.config import AppConfig, load_config
from yt_intel_mcp.provider import FixtureYouTubeProvider
from yt_intel_mcp.quota.guard import QuotaGuard
from yt_intel_mcp.server import create_server

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

ElicitationAction = Literal["accept", "decline", "cancel"]
TransportMode = Literal["memory", "stdio"]
ElicitationHandlerT = Callable[
    [ClientRequestContext, types.ElicitRequestParams],
    Awaitable[types.ElicitResult | types.ErrorData] | types.ElicitResult | types.ErrorData,
]


@dataclass(frozen=True, slots=True)
class ElicitationResponseSpec:
    """Declarative response specification for a single simulated elicitation prompt."""

    action: ElicitationAction = "accept"
    content: dict[str, str | int | float | bool | list[str] | None] | None = None
    error_message: str | None = None


@dataclass(slots=True)
class ElicitationRecorder:
    """Captures all MCP elicitation requests and responses during a system session."""

    enabled: bool
    requests: list[types.ElicitRequestParams] = field(default_factory=list)
    responses: list[types.ElicitResult | types.ErrorData] = field(default_factory=list)

    @property
    def call_count(self) -> int:
        """Return total number of elicitation prompts observed."""
        return len(self.requests)

    @property
    def messages(self) -> list[str]:
        """Return human readable messages presented by the server during prompts."""
        return [request.message for request in self.requests]

    @property
    def actions(self) -> list[str]:
        """Return recorded response actions in chronological order."""
        recorded: list[str] = []
        for response in self.responses:
            if isinstance(response, types.ElicitResult):
                recorded.append(response.action)
            else:
                recorded.append("error")
        return recorded

    def clear(self) -> None:
        """Reset recorded requests and responses."""
        self.requests.clear()
        self.responses.clear()


def _coerce_elicitation_spec(
    entry: ElicitationResponseSpec | ElicitationAction | Mapping[str, Any],
) -> ElicitationResponseSpec:
    if isinstance(entry, ElicitationResponseSpec):
        return entry
    if isinstance(entry, str):
        return ElicitationResponseSpec(action=entry)
    raw_action = entry.get("action", "accept")
    action: ElicitationAction = (
        raw_action if raw_action in ("accept", "decline", "cancel") else "accept"
    )
    raw_content = entry.get("content")
    content = dict(raw_content) if isinstance(raw_content, Mapping) else None
    raw_err = entry.get("error_message")
    return ElicitationResponseSpec(
        action=action,
        content=content,
        error_message=str(raw_err) if raw_err is not None else None,
    )


def build_elicitation_callback(
    *,
    action: ElicitationAction = "accept",
    content: dict[str, str | int | float | bool | list[str] | None] | None = None,
    sequence: Sequence[ElicitationResponseSpec | ElicitationAction | Mapping[str, Any]]
    | None = None,
    custom_handler: ElicitationHandlerT | None = None,
) -> tuple[ElicitationRecorder, ElicitationFnT]:
    """Create a recording ClientSession elicitation callback for accept, decline, or cancel."""
    recorder = ElicitationRecorder(enabled=True)
    call_index = 0
    coerced_sequence = [_coerce_elicitation_spec(item) for item in sequence] if sequence else None

    async def _callback(
        context: ClientRequestContext,
        params: types.ElicitRequestParams,
    ) -> types.ElicitResult | types.ErrorData:
        nonlocal call_index
        recorder.requests.append(params)

        if custom_handler is not None:
            raw_result = custom_handler(context, params)
            result = await raw_result if hasattr(raw_result, "__await__") else raw_result
            assert isinstance(result, types.ElicitResult | types.ErrorData)
            recorder.responses.append(result)
            call_index += 1
            return result

        if coerced_sequence:
            spec = coerced_sequence[min(call_index, len(coerced_sequence) - 1)]
        else:
            spec = ElicitationResponseSpec(action=action, content=content)
        call_index += 1

        if spec.error_message is not None:
            error_data = types.ErrorData(code=types.INVALID_REQUEST, message=spec.error_message)
            recorder.responses.append(error_data)
            return error_data

        payload_content = spec.content
        if spec.action == "accept" and payload_content is None:
            payload_content = {"confirm": True}
        elif spec.action != "accept":
            payload_content = None

        elicit_result = types.ElicitResult(action=spec.action, content=payload_content)
        recorder.responses.append(elicit_result)
        return elicit_result

    return recorder, _callback


def initialize_temp_sqlite(db_path: Path) -> Path:
    """Create an isolated temporary SQLite database configured in WAL mode."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        mode_row = connection.execute("PRAGMA journal_mode=WAL;").fetchone()
        if mode_row is None or str(mode_row[0]).lower() != "wal":
            raise RuntimeError(f"Expected SQLite WAL journal mode, got {mode_row!r}.")
        connection.execute("PRAGMA synchronous=NORMAL;")
        connection.execute("PRAGMA foreign_keys=ON;")
        connection.execute("PRAGMA busy_timeout=5000;")
        connection.commit()
    finally:
        connection.close()
    return db_path


def build_system_env(
    data_dir: Path,
    *,
    fixture_dir: Path = FIXTURES_DIR,
    extra_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build deterministic environment variables isolating tests to fixture mode and tmp_path."""
    env: dict[str, str] = {
        "YT_INTEL_PROVIDER": "fixture",
        "YT_INTEL_DATA_DIR": str(data_dir),
        "YT_INTEL_FIXTURE_DIR": str(fixture_dir),
    }
    if extra_env:
        env.update(extra_env)
    return env


@dataclass(slots=True)
class SystemHarness:
    """Active end to end MCP client and server system test harness."""

    session: ClientSession
    initialize_result: types.InitializeResult
    config: AppConfig
    data_dir: Path
    sqlite_path: Path
    provider: FixtureYouTubeProvider
    elicitation: ElicitationRecorder
    elicitation_enabled: bool
    transport: TransportMode
    env: dict[str, str]
    server: MCPServer | None = None
    fixtures_dir: Path = FIXTURES_DIR

    def open_sqlite(self) -> sqlite3.Connection:
        """Open a SQLite connection to the isolated test database with SRS WAL pragmas."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    async def list_tool_names(self) -> list[str]:
        """Return all registered tool names across paginated list_tools responses."""
        names: list[str] = []
        listed = await self.session.list_tools()
        while True:
            names.extend(tool.name for tool in listed.tools)
            if not listed.next_cursor:
                return names
            listed = await self.session.list_tools(
                params=types.PaginatedRequestParams(cursor=listed.next_cursor)
            )

    async def list_resource_uris(self) -> list[str]:
        """Return all registered static resource URIs from the server."""
        listed = await self.session.list_resources()
        return [str(resource.uri) for resource in listed.resources]

    async def call_tool_json(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> tuple[types.CallToolResult, dict[str, Any] | None]:
        """Invoke an MCP tool and extract structured or JSON encoded payload when present."""
        result = await self.session.call_tool(name, arguments=arguments or {})
        if result.structured_content is not None:
            return result, dict(result.structured_content)
        for item in result.content:
            if isinstance(item, types.TextContent):
                try:
                    decoded = json.loads(item.text)
                except json.JSONDecodeError:
                    continue
                if isinstance(decoded, dict):
                    return result, decoded
        return result, None

    async def read_resource_text(self, uri: str) -> str:
        """Read a resource URI as text through the MCP client session."""
        response = await self.session.read_resource(types.AnyUrl(uri))
        for item in response.contents:
            if isinstance(item, types.TextResourceContents):
                return item.text
        raise AssertionError(f"Resource {uri!r} returned no text contents: {response.contents!r}")


@asynccontextmanager
async def open_system_harness(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch | None = None,
    transport: TransportMode = "memory",
    enable_elicitation: bool = True,
    elicitation_action: ElicitationAction = "accept",
    elicitation_content: dict[str, str | int | float | bool | list[str] | None] | None = None,
    elicitation_sequence: Sequence[ElicitationResponseSpec | ElicitationAction | Mapping[str, Any]]
    | None = None,
    elicitation_handler: ElicitationHandlerT | None = None,
    quota_guard: QuotaGuard | None = None,
    persona: str = "default_user",
    extra_env: Mapping[str, str] | None = None,
    server_factory: Callable[[AppConfig, FixtureYouTubeProvider], MCPServer] | None = None,
    configure_server: Callable[[MCPServer, AppConfig, FixtureYouTubeProvider], None] | None = None,
) -> AsyncIterator[SystemHarness]:
    """Run an isolated MCP server with fixture provider, temp SQLite, and elicitation control."""
    data_dir = tmp_path / "yt-intel-data"
    sqlite_path = initialize_temp_sqlite(data_dir / "yt_intel.db")
    env = build_system_env(data_dir, fixture_dir=FIXTURES_DIR, extra_env=extra_env)

    if monkeypatch is not None:
        for key, value in env.items():
            monkeypatch.setenv(key, value)

    config = load_config(env)
    provider = FixtureYouTubeProvider.from_config(
        config,
        quota_guard=quota_guard,
        persona=persona,
    )

    callback: ElicitationFnT | None
    if enable_elicitation:
        recorder, callback = build_elicitation_callback(
            action=elicitation_action,
            content=elicitation_content,
            sequence=elicitation_sequence,
            custom_handler=elicitation_handler,
        )
    else:
        recorder = ElicitationRecorder(enabled=False)
        callback = None

    if transport == "memory":
        server = server_factory(config, provider) if server_factory is not None else create_server()
        if configure_server is not None:
            configure_server(server, config, provider)

        async with (
            create_client_server_memory_streams() as (client_streams, server_streams),
            anyio.create_task_group() as task_group,
        ):

            async def _serve() -> None:
                await server._lowlevel_server.run(
                    server_streams[0],
                    server_streams[1],
                    server._lowlevel_server.create_initialization_options(),
                )

            task_group.start_soon(_serve)
            async with ClientSession(
                client_streams[0],
                client_streams[1],
                elicitation_callback=callback,
            ) as session:
                with anyio.fail_after(15):
                    init_result = await session.initialize()
                harness = SystemHarness(
                    session=session,
                    initialize_result=init_result,
                    config=config,
                    data_dir=data_dir,
                    sqlite_path=sqlite_path,
                    provider=provider,
                    elicitation=recorder,
                    elicitation_enabled=enable_elicitation,
                    transport="memory",
                    env=env,
                    server=server,
                )
                yield harness
            task_group.cancel_scope.cancel()
        return

    if transport == "stdio":
        subprocess_env = {
            **os.environ,
            **env,
            "PYTHONPATH": str(REPO_ROOT / "src"),
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "yt_intel_mcp"],
            cwd=REPO_ROOT,
            env=subprocess_env,
        )
        async with (
            stdio_client(params) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream, elicitation_callback=callback) as session,
        ):
            with anyio.fail_after(15):
                init_result = await session.initialize()
            harness = SystemHarness(
                session=session,
                initialize_result=init_result,
                config=config,
                data_dir=data_dir,
                sqlite_path=sqlite_path,
                provider=provider,
                elicitation=recorder,
                elicitation_enabled=enable_elicitation,
                transport="stdio",
                env=env,
                server=None,
            )
            yield harness
        return

    raise ValueError(f"Unsupported transport mode: {transport!r}.")


@pytest.fixture
def system_data_dir(tmp_path: Path) -> Path:
    """Return an isolated per test data directory under pytest tmp_path."""
    path = tmp_path / "yt-intel-data"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def system_sqlite_path(system_data_dir: Path) -> Path:
    """Create and return an isolated temporary WAL SQLite database path."""
    return initialize_temp_sqlite(system_data_dir / "yt_intel.db")


@pytest.fixture
def system_env(
    system_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    """Configure environment variables for offline fixture mode and temp SQLite storage."""
    env = build_system_env(system_data_dir, fixture_dir=FIXTURES_DIR)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


@pytest.fixture
def system_config(system_env: dict[str, str]) -> AppConfig:
    """Load AppConfig bound to the fixture directory and isolated temp data directory."""
    return load_config(system_env)


@pytest.fixture
def fixture_provider(system_config: AppConfig) -> FixtureYouTubeProvider:
    """Return a clean FixtureYouTubeProvider instance wired to system_config."""
    return FixtureYouTubeProvider.from_config(system_config)


@pytest.fixture
def elicitation_enabled() -> bool:
    """Default elicitation capability flag; override per test via parametrize."""
    return True


@pytest.fixture
def elicitation_action() -> ElicitationAction:
    """Default simulated user elicitation decision; override via parametrize."""
    return "accept"


@pytest.fixture
def system_harness_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., Any]:
    """Return an async context manager factory for customizable MCP system sessions."""

    def _factory(**kwargs: Any) -> Any:
        return open_system_harness(tmp_path, monkeypatch=monkeypatch, **kwargs)

    return _factory


@pytest.fixture
async def system_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    elicitation_enabled: bool,
    elicitation_action: ElicitationAction,
) -> AsyncIterator[SystemHarness]:
    """Yield an active in process MCP server and client session with temp SQLite and fixtures."""
    async with open_system_harness(
        tmp_path,
        monkeypatch=monkeypatch,
        transport="memory",
        enable_elicitation=elicitation_enabled,
        elicitation_action=elicitation_action,
    ) as harness:
        yield harness


@pytest.fixture
async def stdio_system_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    elicitation_enabled: bool,
    elicitation_action: ElicitationAction,
) -> AsyncIterator[SystemHarness]:
    """Yield a real stdio subprocess MCP client session wired to fixture mode and temp SQLite."""
    async with open_system_harness(
        tmp_path,
        monkeypatch=monkeypatch,
        transport="stdio",
        enable_elicitation=elicitation_enabled,
        elicitation_action=elicitation_action,
    ) as harness:
        yield harness
