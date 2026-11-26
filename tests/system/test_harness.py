"""System test harness verification tests for SR-09 (TQ-3)."""

# ruff: noqa: N802
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import mcp.types as types
import pytest
from mcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)
from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from yt_intel_mcp import SERVER_NAME, __version__
from yt_intel_mcp.config import AppConfig
from yt_intel_mcp.provider import FixtureYouTubeProvider

if TYPE_CHECKING:
    from tests.system.conftest import ElicitationAction, SystemHarness


class _ConfirmForm(BaseModel):
    confirm: bool


def _attach_probe_tools(
    server: MCPServer,
    _config: AppConfig,
    provider: FixtureYouTubeProvider,
) -> None:
    @server.tool(name="_probe_elicitation")
    async def _probe_elicitation(ctx: Context, prompt: str) -> dict[str, object]:
        supported = ctx.session.check_client_capability(
            types.ClientCapabilities(elicitation=types.ElicitationCapability())
        )
        if not supported:
            return {"supported": False, "outcome": "unavailable"}
        result = await ctx.elicit(message=prompt, schema=_ConfirmForm)
        if isinstance(result, AcceptedElicitation):
            return {
                "supported": True,
                "outcome": "accept",
                "confirmed": result.data.confirm,
            }
        if isinstance(result, DeclinedElicitation):
            return {"supported": True, "outcome": "decline"}
        if isinstance(result, CancelledElicitation):
            return {"supported": True, "outcome": "cancel"}
        return {"supported": True, "outcome": "unexpected"}

    @server.tool(name="_probe_provider_video")
    async def _probe_provider_video(video_id: str) -> dict[str, object]:
        videos = await provider.get_videos([video_id])
        return {
            "found": len(videos),
            "title": videos[0].title if videos else "",
            "units_used": provider.total_quota_used.units,
        }


@pytest.mark.anyio
async def test_TQ_3_harness_initializes_real_server_temp_sqlite_and_fixtures(
    system_harness: SystemHarness,
    tmp_path: Path,
) -> None:
    assert system_harness.transport == "memory"
    assert system_harness.server is not None
    assert system_harness.initialize_result.server_info.name == SERVER_NAME
    assert system_harness.initialize_result.server_info.version == __version__

    assert system_harness.data_dir.is_relative_to(tmp_path)
    assert system_harness.config.provider_mode == "fixture"
    assert system_harness.config.fixture_dir == system_harness.fixtures_dir
    assert os.environ["YT_INTEL_PROVIDER"] == "fixture"
    assert os.environ["YT_INTEL_DATA_DIR"] == str(system_harness.data_dir)
    assert system_harness.provider.calls == []

    assert system_harness.sqlite_path.is_file()
    conn = system_harness.open_sqlite()
    try:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()
        assert journal_mode is not None
        assert str(journal_mode[0]).lower() == "wal"
        conn.execute("CREATE TABLE harness_probe (id INTEGER PRIMARY KEY, note TEXT NOT NULL);")
        conn.execute("INSERT INTO harness_probe (note) VALUES (?);", ("isolated",))
        conn.commit()
        row = conn.execute("SELECT note FROM harness_probe;").fetchone()
        assert row is not None and row["note"] == "isolated"
    finally:
        conn.close()


@pytest.mark.anyio
async def test_TQ_3_stdio_harness_runs_real_subprocess(
    stdio_system_harness: SystemHarness,
) -> None:
    assert stdio_system_harness.transport == "stdio"
    assert stdio_system_harness.server is None
    assert stdio_system_harness.initialize_result.server_info.name == SERVER_NAME
    assert stdio_system_harness.initialize_result.server_info.version == __version__
    assert stdio_system_harness.sqlite_path.is_file()
    assert await stdio_system_harness.list_tool_names() == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "expected_supported", "expected_calls"),
    [
        ("disabled", False, 0),
        ("accept", True, 1),
        ("decline", True, 1),
        ("cancel", True, 1),
    ],
)
async def test_TQ_3_harness_toggles_elicitation_and_simulates_outcomes(
    system_harness_factory: object,
    mode: Literal["disabled"] | ElicitationAction,
    expected_supported: bool,
    expected_calls: int,
) -> None:
    factory = system_harness_factory
    assert callable(factory)
    enabled = mode != "disabled"
    action: ElicitationAction = "accept" if mode == "disabled" else mode

    async with factory(
        transport="memory",
        enable_elicitation=enabled,
        elicitation_action=action,
        configure_server=_attach_probe_tools,
    ) as harness:
        assert harness.elicitation_enabled is enabled
        _, payload = await harness.call_tool_json(
            "_probe_elicitation",
            {"prompt": "Approve playlist Python Study?"},
        )
        assert payload is not None
        assert payload["supported"] is expected_supported
        assert harness.elicitation.call_count == expected_calls
        if not enabled:
            assert payload["outcome"] == "unavailable"
            assert harness.elicitation.messages == []
        else:
            assert payload["outcome"] == action
            assert harness.elicitation.messages == ["Approve playlist Python Study?"]
            assert harness.elicitation.actions == [action]
            if action == "accept":
                assert payload["confirmed"] is True


@pytest.mark.anyio
async def test_TQ_3_harness_supports_elicitation_sequence_and_fixture_calls(
    system_harness_factory: object,
) -> None:
    factory = system_harness_factory
    assert callable(factory)

    async with factory(
        transport="memory",
        enable_elicitation=True,
        elicitation_sequence=[
            "decline",
            {"action": "accept", "content": {"confirm": True}},
        ],
        configure_server=_attach_probe_tools,
    ) as harness:
        _, first = await harness.call_tool_json(
            "_probe_elicitation",
            {"prompt": "First draft prompt"},
        )
        _, second = await harness.call_tool_json(
            "_probe_elicitation",
            {"prompt": "Revised draft prompt"},
        )
        assert first == {"supported": True, "outcome": "decline"}
        assert second == {"supported": True, "outcome": "accept", "confirmed": True}
        assert harness.elicitation.actions == ["decline", "accept"]

        _, video_payload = await harness.call_tool_json(
            "_probe_provider_video",
            {"video_id": "vid_seed_py01"},
        )
        assert video_payload is not None
        assert video_payload["found"] == 1
        assert int(str(video_payload["units_used"])) >= 1
        assert [call.operation for call in harness.provider.calls] == ["videos.list"]
