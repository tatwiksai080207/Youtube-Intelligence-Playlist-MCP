"""SK-2 and TQ-7 checks for the local verification runner (MF-16)."""

# ruff: noqa: N802
import asyncio
import importlib
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("local_check")


def test_SK_2_runner_uses_fixtures_and_reports_all_five_passes(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commands: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(
        args: list[str], *, env: dict[str, str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        commands.append((args, env))
        return subprocess.CompletedProcess(args, 0)

    async def fake_server_and_fetch() -> tuple[object, object]:
        server_res = runner.Result("Start MCP server", "PASS", "initialized over stdio")
        fetch_res = runner.Result(
            "Read-only fetch",
            "PASS",
            f"fetched {runner.SAMPLE_VIDEO_ID} details and verified quota status",
        )
        return server_res, fetch_res

    monkeypatch.setenv("YT_INTEL_PROVIDER", "live")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "check_stdio_server_and_fetch", fake_server_and_fetch)

    assert runner.main() == 0
    assert commands[0][0][1:5] == ["-m", "pip", "wheel", "--no-deps"]
    assert commands[1][0][1:] == ["-m", "pytest", "-m", "not live"]
    assert all(env["YT_INTEL_PROVIDER"] == "fixture" for _, env in commands)
    assert all(env["PYTHONPATH"] == str(runner.ROOT / "src") for _, env in commands)
    assert not Path(commands[0][0][-2]).exists()
    out = capsys.readouterr().out
    assert "1. Build project: PASS" in out
    assert "2. Run automated tests: PASS" in out
    assert "3. Start MCP server: PASS: initialized over stdio" in out
    expected_fetch = (
        f"4. Read-only fetch: PASS: fetched {runner.SAMPLE_VIDEO_ID} "
        "details and verified quota status"
    )
    assert expected_fetch in out
    assert "5. Summary: PASS: 4 passed, 0 failed, 0 not run" in out


def test_SK_2_runner_reports_fetch_failure(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args, 0)

    async def failed_fetch() -> tuple[object, object]:
        server_res = runner.Result("Start MCP server", "PASS", "initialized over stdio")
        fetch_res = runner.Result(
            "Read-only fetch", "FAIL", "get_video_details failed: video unavailable"
        )
        return server_res, fetch_res

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "check_stdio_server_and_fetch", failed_fetch)

    assert runner.main() == 1
    out = capsys.readouterr().out
    assert "3. Start MCP server: PASS: initialized over stdio" in out
    assert "4. Read-only fetch: FAIL: get_video_details failed: video unavailable" in out
    assert "5. Summary: FAIL: 3 passed, 1 failed, 0 not run" in out


def test_SK_2_runner_reports_failures_and_skips_fetch_after_failed_handshake(
    runner: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failed_process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args, 2 if args[2] == "pytest" else 0)

    async def failed_server() -> tuple[object, object]:
        raise TimeoutError("MCP handshake timed out")

    monkeypatch.setattr(runner.subprocess, "run", failed_process)
    monkeypatch.setattr(runner, "check_stdio_server_and_fetch", failed_server)
    assert runner.main() == 1
    captured = capsys.readouterr()
    assert "1. Build project: PASS" in captured.out
    assert "2. Run automated tests: FAIL: exit code 2" in captured.out
    assert "3. Start MCP server: FAIL: stdio startup or handshake failed" in captured.out
    assert "4. Read-only fetch: NOT RUN: server check failed" in captured.out
    assert "5. Summary: FAIL: 1 passed, 2 failed, 1 not run" in captured.out
    assert "MCP handshake timed out" in captured.err


def test_SK_2_server_initializes_and_fetches_over_stdio(runner: ModuleType) -> None:
    server_res, fetch_res = asyncio.run(runner.check_stdio_server_and_fetch())
    assert server_res.status == "PASS"
    assert fetch_res.status == "PASS"
    assert asyncio.run(runner.check_stdio_server()) is True
