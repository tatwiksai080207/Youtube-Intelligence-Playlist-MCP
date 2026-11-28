"""stdio entry point: ``python -m yt_intel_mcp`` (SRS §3.3, MCP over stdio)."""

from __future__ import annotations

import logging
import sys

from yt_intel_mcp.server import create_server


def main() -> None:
    """Run the MCP server over stdio until the client disconnects."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
