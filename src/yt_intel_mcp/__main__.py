"""stdio entry point: ``python -m yt_intel_mcp`` (SRS §3.3, MCP over stdio)."""

from yt_intel_mcp.server import create_server


def main() -> None:
    """Run the MCP server over stdio until the client disconnects."""
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
