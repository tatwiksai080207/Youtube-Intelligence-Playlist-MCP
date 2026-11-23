"""MCP server construction.

SR-01 skeleton: the server only answers the MCP handshake. No tools or
resources are registered yet; they arrive with their owning tasks (SRS §3.1).
Logs must go to stderr only, because stdout carries the JSON-RPC stream.
"""

from mcp.server.mcpserver import MCPServer

from yt_intel_mcp import SERVER_NAME, __version__

INSTRUCTIONS = (
    "YouTube Video Intelligence server. Ranks videos and channels by objective "
    "metadata only and never creates a playlist without trusted user confirmation."
)


def create_server() -> MCPServer:
    """Build the yt-intel-mcp MCP server (no tools registered yet)."""
    return MCPServer(
        name=SERVER_NAME,
        version=__version__,
        instructions=INSTRUCTIONS,
    )
