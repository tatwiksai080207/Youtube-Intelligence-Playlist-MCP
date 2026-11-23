"""SR-01 smoke tests: package imports and the stdio server answers MCP initialize."""

import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.mcpserver import MCPServer

import yt_intel_mcp
from yt_intel_mcp import __main__ as entry
from yt_intel_mcp.server import create_server


def test_package_exposes_version() -> None:
    assert yt_intel_mcp.__version__ == "0.1.0"
    assert yt_intel_mcp.SERVER_NAME == "yt-intel-mcp"


def test_create_server_has_identity() -> None:
    server = create_server()
    assert server.name == "yt-intel-mcp"
    assert server.version == yt_intel_mcp.__version__


def test_main_runs_server_over_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(MCPServer, "run", lambda self, transport="stdio": calls.append(transport))
    entry.main()
    assert calls == ["stdio"]


@pytest.mark.anyio
async def test_server_has_no_tools_yet() -> None:
    assert await create_server().list_tools() == []


@pytest.mark.anyio
async def test_stdio_server_handles_initialize() -> None:
    """Launch `python -m yt_intel_mcp` as a subprocess and complete the handshake."""
    params = StdioServerParameters(command=sys.executable, args=["-m", "yt_intel_mcp"])
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        result = await session.initialize()
        assert result.server_info.name == "yt-intel-mcp"
        assert result.server_info.version == yt_intel_mcp.__version__
        tools = await session.list_tools()
        assert tools.tools == []
