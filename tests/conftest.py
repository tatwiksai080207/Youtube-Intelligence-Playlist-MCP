import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio only (the MCP SDK's default backend)."""
    return "asyncio"
