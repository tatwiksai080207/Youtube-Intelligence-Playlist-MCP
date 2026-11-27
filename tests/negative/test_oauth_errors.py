"""Negative tests for OAuth error mapping, refresh expiry, and channel guards (NT_AUTH, NT_ACC)."""

# ruff: noqa: N802
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest

from yt_intel_mcp.auth import (
    DEFAULT_CALLBACK_PATH,
    DEFAULT_LOOPBACK_HOST,
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    LocalOAuthCallbackServer,
    OAuthFlow,
    TokenBundle,
    TokenStore,
    check_channel_presence,
    ensure_write_scope,
    exchange_code_for_tokens,
    refresh_access_token,
)
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import ChannelMeta
from yt_intel_mcp.provider.fixture import FixtureYouTubeProvider


class _MockHttpTransport:
    """Mock HTTP transport returning controlled status codes and payloads."""

    def __init__(
        self,
        status_code: int = 200,
        response_data: dict[str, Any] | None = None,
        *,
        fail_with_network_error: bool = False,
    ) -> None:
        self.status_code = status_code
        self.response_data = response_data if response_data is not None else {}
        self.fail_with_network_error = fail_with_network_error
        self.calls: list[tuple[str, dict[str, str]]] = []

    def post(
        self,
        url: str,
        data: Mapping[str, str],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, Any]]:
        self.calls.append((url, dict(data)))
        if self.fail_with_network_error:
            raise HTTPError(url, 503, "Service Unavailable", headers=None, fp=None)  # type: ignore[arg-type]
        return self.status_code, dict(self.response_data)


def _sample_bundle(*, write_scope: bool = False, has_channel: bool = True) -> TokenBundle:
    now = datetime(2026, 11, 27, 10, 0, tzinfo=UTC)
    scopes = (
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE)
        if write_scope
        else (YOUTUBE_READONLY_SCOPE,)
    )
    return TokenBundle(
        access_token="ya29.sample_access_token",
        refresh_token="1//0g_sample_refresh_token",
        scopes=scopes,
        expires_at_utc=now + timedelta(hours=1),
        issued_at_utc=now,
        channel_id="UC_TEST_CHANNEL_01" if has_channel else None,
        has_channel=has_channel,
    )


def test_NT_AUTH_refresh_invalid_grant_maps_to_reauthorization_required() -> None:
    """7-day Testing mode expiry or revoked refresh token returns invalid_grant (C-4)."""
    bundle = _sample_bundle()
    mock_transport = _MockHttpTransport(
        status_code=400,
        response_data={
            "error": "invalid_grant",
            "error_description": "Token has been expired or revoked.",
        },
    )
    with pytest.raises(ToolError) as exc_info:
        refresh_access_token(
            bundle,
            client_id="test-client-id",
            transport=mock_transport,
        )

    err = exc_info.value
    assert err.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED
    assert "invalid_grant" in err.message.lower() or "expired" in err.message.lower()
    assert err.details.get("error") == "invalid_grant"


def test_NT_AUTH_code_exchange_invalid_grant_maps_to_reauthorization_required() -> None:
    """Expired or invalid auth code returns invalid_grant on token exchange."""
    mock_transport = _MockHttpTransport(
        status_code=400,
        response_data={
            "error": "invalid_grant",
            "error_description": "Bad Request: code expired",
        },
    )
    with pytest.raises(ToolError) as exc_info:
        exchange_code_for_tokens(
            client_id="test-client-id",
            code="expired_auth_code",
            code_verifier="valid_code_verifier_1234567890123456789012345678901234567890",
            redirect_uri="http://127.0.0.1:8080/callback",
            transport=mock_transport,
        )

    err = exc_info.value
    assert err.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED
    assert err.details.get("error") == "invalid_grant"


def test_NT_AUTH_callback_state_mismatch_raises_permission_denied() -> None:
    """Callback with CSRF state mismatch raises PERMISSION_DENIED."""
    import threading
    import urllib.error
    import urllib.request

    server = LocalOAuthCallbackServer(expected_state="expected_csrf_secret_token_123")
    url = (
        f"http://{DEFAULT_LOOPBACK_HOST}:{server.server_port}"
        f"{DEFAULT_CALLBACK_PATH}?code=valid_code&state=wrong_state"
    )
    client_errors: list[Exception] = []

    def _client_request() -> None:
        try:
            with urllib.request.urlopen(url, timeout=5.0):
                pass
        except urllib.error.HTTPError as exc:
            client_errors.append(exc)

    client_thread = threading.Thread(target=_client_request)
    try:
        client_thread.start()
        with pytest.raises(ToolError) as exc_info:
            server.wait_for_code(timeout=5.0)
        assert exc_info.value.code is ErrorCode.PERMISSION_DENIED
        assert "mismatch" in exc_info.value.message.lower()
    finally:
        client_thread.join(timeout=2.0)
        server.server_close()
    assert len(client_errors) == 1
    assert isinstance(client_errors[0], urllib.error.HTTPError)
    assert client_errors[0].code == 400


def test_NT_AUTH_callback_access_denied_raises_permission_denied() -> None:
    """User declining consent on Google screen returns error=access_denied."""
    import threading
    import urllib.error
    import urllib.request

    server = LocalOAuthCallbackServer(expected_state="state_xyz")
    url = (
        f"http://{DEFAULT_LOOPBACK_HOST}:{server.server_port}"
        f"{DEFAULT_CALLBACK_PATH}?error=access_denied&state=state_xyz"
    )
    client_errors: list[Exception] = []

    def _client_request() -> None:
        try:
            with urllib.request.urlopen(url, timeout=5.0):
                pass
        except urllib.error.HTTPError as exc:
            client_errors.append(exc)

    client_thread = threading.Thread(target=_client_request)
    try:
        client_thread.start()
        with pytest.raises(ToolError) as exc_info:
            server.wait_for_code(timeout=5.0)
        assert exc_info.value.code is ErrorCode.PERMISSION_DENIED
        assert "access_denied" in exc_info.value.message
    finally:
        client_thread.join(timeout=2.0)
        server.server_close()
    assert len(client_errors) == 1
    assert isinstance(client_errors[0], urllib.error.HTTPError)
    assert client_errors[0].code == 400


def test_NT_AUTH_missing_write_scope_non_interactive_raises_scope_insufficient(
    tmp_path: Path,
) -> None:
    """Calling ensure_write_scope without write scope raises SCOPE_INSUFFICIENT (C-7, FR-7.1)."""
    store = TokenStore(tmp_path / "oauth_store", use_system_keyring=False)
    readonly_bundle = _sample_bundle(write_scope=False)
    store.save_bundle(readonly_bundle)

    with pytest.raises(ToolError) as exc_info:
        ensure_write_scope(store, interactive=False)

    err = exc_info.value
    assert err.code is ErrorCode.SCOPE_INSUFFICIENT
    assert "write scope" in err.message.lower()
    assert err.details.get("required_scope") == YOUTUBE_FORCE_SSL_SCOPE
    assert YOUTUBE_READONLY_SCOPE in err.details.get("granted_scopes", [])


@pytest.mark.anyio
async def test_NT_ACC_channel_required_on_writes_while_reads_continue(
    tmp_path: Path,
) -> None:
    """Accounts lacking a YouTube channel fail write checks but reads succeed (C-5, FR-7.3)."""
    store = TokenStore(tmp_path / "oauth_store", use_system_keyring=False)
    bundle = _sample_bundle(write_scope=True, has_channel=False)
    store.save_bundle(bundle)

    provider = FixtureYouTubeProvider(
        fixture_dir=Path("tests/fixtures"),
        persona="no_channel_user",
    )

    # 1. Read operations succeed normally without channel
    videos = await provider.get_videos(["vid_seed_py01"])
    assert len(videos) == 1
    categories = await provider.get_video_categories()
    assert len(categories) > 0

    # 2. Write channel verification fails with CHANNEL_REQUIRED
    with pytest.raises(ToolError) as exc_info:
        await check_channel_presence(provider, store)

    err = exc_info.value
    assert err.code is ErrorCode.CHANNEL_REQUIRED

    # 3. Token store metadata correctly updated to has_channel=False
    meta = store.read_metadata()
    assert meta.has_channel is False


@pytest.mark.anyio
async def test_NT_ACC_empty_channel_id_raises_channel_required(
    tmp_path: Path,
) -> None:
    """ChannelMeta with empty channel_id raises CHANNEL_REQUIRED."""
    store = TokenStore(tmp_path / "oauth_store", use_system_keyring=False)
    bundle = _sample_bundle(write_scope=True)
    store.save_bundle(bundle)

    class _EmptyChannelProvider:
        async def get_my_channel(self) -> ChannelMeta:
            return ChannelMeta(channel_id="", title="Empty Channel")

    with pytest.raises(ToolError) as exc_info:
        await check_channel_presence(_EmptyChannelProvider(), store)  # type: ignore[arg-type]

    assert exc_info.value.code is ErrorCode.CHANNEL_REQUIRED
    meta = store.read_metadata()
    assert meta.has_channel is False


def test_NT_AUTH_unauthenticated_flow_operations_raise_reauthorization_required(
    tmp_path: Path,
) -> None:
    """Operations on an empty TokenStore raise AUTH_REAUTHORIZATION_REQUIRED."""
    store = TokenStore(tmp_path / "empty_store", use_system_keyring=False)
    flow = OAuthFlow(store)

    with pytest.raises(ToolError) as exc_info:
        flow.refresh_token()
    assert exc_info.value.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED

    with pytest.raises(ToolError) as exc_info:
        flow.get_valid_access_token()
    assert exc_info.value.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED

    with pytest.raises(ToolError) as exc_info:
        flow.ensure_write(interactive=False)
    assert exc_info.value.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED
