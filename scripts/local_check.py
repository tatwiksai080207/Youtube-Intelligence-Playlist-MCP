"""Build and check the local MCP server with the fixture provider."""

import asyncio
import os
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
CHECK_ENV = {"YT_INTEL_PROVIDER": "fixture", "PYTHONPATH": str(ROOT / "src")}
FETCH_TOOL = "get_video_details"


@dataclass(frozen=True)
class Result:
    name: str
    status: Literal["PASS", "FAIL", "NOT RUN"]
    detail: str = ""

    def line(self, step: int) -> str:
        detail = f": {self.detail}" if self.detail else ""
        return f"{step}. {self.name}: {self.status}{detail}"


def run_command(name: str, args: list[str]) -> Result:
    print(f"{name}...", flush=True)
    try:
        completed = subprocess.run(
            [sys.executable, "-m", *args],
            cwd=ROOT,
            env={**os.environ, **CHECK_ENV},
            check=False,
        )
    except OSError as error:
        return Result(name, "FAIL", str(error))
    if completed.returncode:
        return Result(name, "FAIL", f"exit code {completed.returncode}")
    return Result(name, "PASS")


async def check_stdio_server() -> bool:
    """Start the normal entry point and report whether the fetch tool is registered."""
    from anyio import fail_after
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.types import PaginatedRequestParams

    from yt_intel_mcp import SERVER_NAME

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "yt_intel_mcp"],
        cwd=ROOT,
        env=CHECK_ENV,
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as session,
    ):
        with fail_after(15):
            initialized = await session.initialize()
            if initialized.server_info.name != SERVER_NAME:
                raise RuntimeError(f"unexpected MCP server: {initialized.server_info.name}")
            listed = await session.list_tools()
            while True:
                if any(tool.name == FETCH_TOOL for tool in listed.tools):
                    return True
                if not listed.next_cursor:
                    return False
                listed = await session.list_tools(
                    params=PaginatedRequestParams(cursor=listed.next_cursor)
                )


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="yt-intel-wheel-") as wheels:
            build = run_command(
                "Build project", ["pip", "wheel", "--no-deps", "--wheel-dir", wheels, "."]
            )
    except OSError as error:
        build = Result("Build project", "FAIL", str(error))

    tests = run_command("Run automated tests", ["pytest", "-m", "not live"])
    try:
        fetch_registered = asyncio.run(check_stdio_server())
    except Exception as error:
        traceback.print_exception(error)
        server = Result("Start MCP server", "FAIL", "stdio startup or handshake failed")
        fetch = Result("Read-only fetch", "NOT RUN", "server check failed")
    else:
        server = Result("Start MCP server", "PASS", "initialized over stdio")
        if fetch_registered:
            fetch = Result("Read-only fetch", "NOT RUN", "fixture fetch check is pending MF-16")
        else:
            fetch = Result("Read-only fetch", "NOT RUN", "no read-only fetch tool registered yet")

    checks = (build, tests, server, fetch)
    failed = sum(check.status == "FAIL" for check in checks)
    passed = sum(check.status == "PASS" for check in checks)
    summary = Result(
        "Summary",
        "FAIL" if failed else "PASS",
        f"{passed} passed, {failed} failed, {len(checks) - passed - failed} not run",
    )
    for step, result in enumerate((*checks, summary), start=1):
        print(result.line(step))
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
