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
QUOTA_TOOL = "get_quota_status"
SAMPLE_VIDEO_ID = "seedPy00001"


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


async def check_stdio_server_and_fetch() -> tuple[Result, Result]:
    """Start the normal entry point over stdio, verify handshake, and invoke read-only tools."""
    from anyio import fail_after
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.types import PaginatedRequestParams

    from yt_intel_mcp import SERVER_NAME

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "yt_intel_mcp"],
        cwd=ROOT,
        env={**os.environ, **CHECK_ENV},
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as session,
    ):
        with fail_after(15):
            initialized = await session.initialize()
            if initialized.server_info.name != SERVER_NAME:
                raise RuntimeError(f"unexpected MCP server: {initialized.server_info.name}")

            tool_names: set[str] = set()
            listed = await session.list_tools()
            while True:
                tool_names.update(tool.name for tool in listed.tools)
                if not listed.next_cursor:
                    break
                listed = await session.list_tools(
                    params=PaginatedRequestParams(cursor=listed.next_cursor)
                )

            server_res = Result("Start MCP server", "PASS", "initialized over stdio")

            if FETCH_TOOL not in tool_names:
                fetch_res = Result(
                    "Read-only fetch",
                    "FAIL",
                    f"required tool {FETCH_TOOL!r} not registered",
                )
                return server_res, fetch_res

            if QUOTA_TOOL not in tool_names:
                fetch_res = Result(
                    "Read-only fetch",
                    "FAIL",
                    f"required tool {QUOTA_TOOL!r} not registered",
                )
                return server_res, fetch_res

            # 1. Call get_video_details (read-only fetch per SDLC Section 3)
            details_result = await session.call_tool(
                FETCH_TOOL,
                {"video_id": SAMPLE_VIDEO_ID},
            )
            if details_result.is_error:
                error_msg = str(details_result.content)
                fetch_res = Result(
                    "Read-only fetch",
                    "FAIL",
                    f"{FETCH_TOOL} failed: {error_msg}",
                )
                return server_res, fetch_res

            # 2. Call get_quota_status (verifies quota ledger & 0 live usage)
            quota_result = await session.call_tool(
                QUOTA_TOOL,
                {},
            )
            if quota_result.is_error:
                error_msg = str(quota_result.content)
                fetch_res = Result(
                    "Read-only fetch",
                    "FAIL",
                    f"{QUOTA_TOOL} failed: {error_msg}",
                )
                return server_res, fetch_res

            fetch_res = Result(
                "Read-only fetch",
                "PASS",
                f"fetched {SAMPLE_VIDEO_ID} details and verified quota status",
            )
            return server_res, fetch_res


async def check_stdio_server() -> bool:
    """Start the normal entry point and report whether the server initialized cleanly."""
    server_res, _ = await check_stdio_server_and_fetch()
    return server_res.status == "PASS"


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
        server, fetch = asyncio.run(check_stdio_server_and_fetch())
    except Exception as error:
        traceback.print_exception(error)
        server = Result("Start MCP server", "FAIL", "stdio startup or handshake failed")
        fetch = Result("Read-only fetch", "NOT RUN", "server check failed")

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
