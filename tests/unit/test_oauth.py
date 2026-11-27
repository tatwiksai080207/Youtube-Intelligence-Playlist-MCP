"""Unit tests for OAuth PKCE flow, loopback server, and token lifecycle."""

from __future__ import annotations

import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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
    UrllibHttpTransport,
    ensure_write_scope,
    exchange_code_for_tokens,
    login_with_pkce,
    refresh_access_token,
)
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import ChannelMeta


class _MockTransport:
    def __init__(
        self,
        status_code: int = 200,
        response_data: dict[str, Any] | None = None,
        *,
        fail_network: bool = False,
    ) -> None:
        self.status_code = status_code
        self.response_data = response_data if response_data is not None else {}
        self.fail_network = fail_network
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
        if self.fail_network:
            raise urllib.error.URLError("Simulated connection reset")
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
        channel_id="UC_TEST_01" if has_channel else None,
        has_channel=has_channel,
    )


def test_callback_server_404_on_non_callback_path() -> None:
    """Non-callback paths return 404 Not Found."""
    server = LocalOAuthCallbackServer(expected_state="state123")
    url = f"http://{DEFAULT_LOOPBACK_HOST}:{server.server_port}/not_callback"

    def _client() -> None:
        try:
            with urllib.request.urlopen(url, timeout=3.0):
                pass
        except urllib.error.HTTPError as err:
            assert err.code == 404

    t = threading.Thread(target=_client)
    try:
        t.start()
        server.timeout = 3.0
        server.handle_request()
    finally:
        t.join(timeout=2.0)
        server.server_close()


def test_callback_server_missing_code_query_param() -> None:
    """Missing code in query parameters results in missing_code error."""
    server = LocalOAuthCallbackServer(expected_state="valid_state")
    url = f"http://{DEFAULT_LOOPBACK_HOST}:{server.server_port}{DEFAULT_CALLBACK_PATH}?state=valid_state"

    def _client() -> None:
        try:
            with urllib.request.urlopen(url, timeout=3.0):
                pass
        except urllib.error.HTTPError as err:
            assert err.code == 400

    t = threading.Thread(target=_client)
    try:
        t.start()
        with pytest.raises(ToolError) as exc:
            server.wait_for_code(timeout=3.0)
        assert exc.value.code is ErrorCode.PERMISSION_DENIED
    finally:
        t.join(timeout=2.0)
        server.server_close()


def test_callback_server_timeout_raises_permission_denied() -> None:
    """Server timing out with no request raises PERMISSION_DENIED."""
    server = LocalOAuthCallbackServer(expected_state="valid_state")
    try:
        with pytest.raises(ToolError) as exc:
            server.wait_for_code(timeout=0.1)
        assert exc.value.code is ErrorCode.PERMISSION_DENIED
        assert "timed out" in exc.value.message.lower()
    finally:
        server.server_close()


def test_callback_server_successful_code_retrieval() -> None:
    """Valid code and matching state returns code cleanly."""
    server = LocalOAuthCallbackServer(expected_state="match_state")
    url = f"http://{DEFAULT_LOOPBACK_HOST}:{server.server_port}{DEFAULT_CALLBACK_PATH}?code=secret_auth_code&state=match_state"

    def _client() -> None:
        with urllib.request.urlopen(url, timeout=3.0) as resp:
            assert resp.status == 200
            body = resp.read().decode("utf-8")
            assert "authentication complete" in body.lower()
            assert resp.headers.get("Content-Security-Policy") is not None

    t = threading.Thread(target=_client)
    try:
        t.start()
        code = server.wait_for_code(timeout=3.0)
        assert code == "secret_auth_code"
    finally:
        t.join(timeout=2.0)
        server.server_close()


def test_exchange_code_missing_tokens_raises() -> None:
    """Token exchange missing access_token or refresh_token raises ToolError."""
    mock = _MockTransport(status_code=200, response_data={"access_token": ""})
    with pytest.raises(ToolError) as exc:
        exchange_code_for_tokens(
            client_id="c1",
            code="code1",
            code_verifier="verifier",
            redirect_uri="http://127.0.0.1:8080/callback",
            transport=mock,
        )
    assert exc.value.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED


def test_exchange_code_generic_error_raises_permission_denied() -> None:
    """Non-invalid_grant error raises PERMISSION_DENIED."""
    mock = _MockTransport(
        status_code=400,
        response_data={"error": "unauthorized_client", "error_description": "Client unauthorized"},
    )
    with pytest.raises(ToolError) as exc:
        exchange_code_for_tokens(
            client_id="c1",
            code="code1",
            code_verifier="verifier",
            redirect_uri="http://127.0.0.1:8080/callback",
            transport=mock,
        )
    assert exc.value.code is ErrorCode.PERMISSION_DENIED


def test_refresh_missing_access_token_raises() -> None:
    """Refresh response missing access_token raises AUTH_REAUTHORIZATION_REQUIRED."""
    bundle = _sample_bundle()
    mock = _MockTransport(status_code=200, response_data={"access_token": ""})
    with pytest.raises(ToolError) as exc:
        refresh_access_token(bundle, client_id="c1", transport=mock)
    assert exc.value.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED


def test_refresh_generic_error_raises_reauthorization_required() -> None:
    """Generic error on refresh raises AUTH_REAUTHORIZATION_REQUIRED."""
    bundle = _sample_bundle()
    mock = _MockTransport(
        status_code=500,
        response_data={"error": "server_error", "error_description": "Internal error"},
    )
    with pytest.raises(ToolError) as exc:
        refresh_access_token(bundle, client_id="c1", transport=mock)
    assert exc.value.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED


def test_login_with_pkce_end_to_end_with_browser_opener(tmp_path: Path) -> None:
    """login_with_pkce with real loopback server and mock browser opener."""
    store = TokenStore(tmp_path / "pkce_e2e_store", use_system_keyring=False)
    mock_transport = _MockTransport(
        status_code=200,
        response_data={
            "access_token": "ya29.pkce_e2e_token",
            "refresh_token": "1//0g_pkce_e2e_refresh",
            "expires_in": 7200,
            "scope": YOUTUBE_READONLY_SCOPE,
        },
    )

    def _mock_browser(auth_url: str) -> None:
        # Simulate browser following redirect to callback server
        parsed = urllib.parse.urlparse(auth_url)
        params = urllib.parse.parse_qs(parsed.query)
        redirect_uri = params["redirect_uri"][0]
        state = params["state"][0]
        callback_url = f"{redirect_uri}?code=e2e_code&state={state}"

        def _hit() -> None:
            with urllib.request.urlopen(callback_url, timeout=3.0) as resp:
                assert resp.status == 200

        t = threading.Thread(target=_hit)
        t.start()

    bundle = login_with_pkce(
        store,
        client_id="e2e-client",
        transport=mock_transport,
        browser_opener=_mock_browser,
    )
    assert bundle.access_token == "ya29.pkce_e2e_token"
    assert bundle.refresh_token == "1//0g_pkce_e2e_refresh"
    assert store.load_bundle() is not None


def test_ensure_write_scope_interactive_from_unauthenticated_and_readonly(
    tmp_path: Path,
) -> None:
    """ensure_write_scope interactive handles both unauthenticated and upgrade paths."""
    store = TokenStore(tmp_path / "write_store", use_system_keyring=False)
    mock_transport = _MockTransport(
        status_code=200,
        response_data={
            "access_token": "ya29.write_token_1",
            "refresh_token": "1//0g_write_refresh_1",
            "expires_in": 3600,
            "scope": f"{YOUTUBE_READONLY_SCOPE} {YOUTUBE_FORCE_SSL_SCOPE}",
        },
    )

    # 1. Unauthenticated with auth code override
    bundle1 = ensure_write_scope(
        store,
        client_id="c1",
        interactive=True,
        transport=mock_transport,
        auth_code_override="auth_code_1",
    )
    assert YOUTUBE_FORCE_SSL_SCOPE in bundle1.scopes

    # 2. Scope already granted returns bundle immediately without network call
    call_count = len(mock_transport.calls)
    bundle2 = ensure_write_scope(store, client_id="c1", interactive=False)
    assert bundle2 == bundle1
    assert len(mock_transport.calls) == call_count

    # 3. Readonly bundle upgrade with auth code override
    readonly_bundle = _sample_bundle(write_scope=False)
    store.save_bundle(readonly_bundle)
    bundle3 = ensure_write_scope(
        store,
        client_id="c1",
        interactive=True,
        transport=mock_transport,
        auth_code_override="auth_code_upgrade",
    )
    assert YOUTUBE_FORCE_SSL_SCOPE in bundle3.scopes


def test_oauth_flow_methods_and_valid_access_token(tmp_path: Path) -> None:
    """OAuthFlow methods: login_write, login_readonly, near expiry refresh, and revoke."""
    store = TokenStore(tmp_path / "flow_store", use_system_keyring=False)
    mock_transport = _MockTransport(
        status_code=200,
        response_data={
            "access_token": "ya29.flow_token",
            "refresh_token": "1//0g_flow_refresh",
            "expires_in": 3600,
            "scope": YOUTUBE_FORCE_SSL_SCOPE,
        },
    )
    flow = OAuthFlow(
        store,
        client_id="flow-client",
        transport=mock_transport,
        clock=lambda: datetime(2026, 11, 27, 10, 0, tzinfo=UTC),
    )

    # login_write with override
    w_bundle = flow.login_write(auth_code_override="w_code")
    assert YOUTUBE_FORCE_SSL_SCOPE in w_bundle.scopes

    # login_readonly with override
    mock_transport.response_data = {
        "access_token": "ya29.readonly_token",
        "refresh_token": "1//0g_readonly_refresh",
        "expires_in": 3600,
        "scope": YOUTUBE_READONLY_SCOPE,
    }
    r_bundle = flow.login_readonly(auth_code_override="r_code")
    assert YOUTUBE_READONLY_SCOPE in r_bundle.scopes

    # get_valid_access_token when token is fresh returns directly
    tok1 = flow.get_valid_access_token(skew_seconds=60)
    assert tok1 == "ya29.readonly_token"

    # get_valid_access_token when token is near expiry triggers refresh
    flow.clock = lambda: datetime(2026, 11, 27, 11, 59, 30, tzinfo=UTC)  # 30s left < 60s skew
    mock_transport.response_data = {
        "access_token": "ya29.refreshed_near_expiry",
        "expires_in": 3600,
        "scope": YOUTUBE_READONLY_SCOPE,
    }
    tok2 = flow.get_valid_access_token(skew_seconds=60)
    assert tok2 == "ya29.refreshed_near_expiry"

    # check verify_channel
    class _DummyProvider:
        async def get_my_channel(self) -> ChannelMeta:
            return ChannelMeta(channel_id="UC_FLOW_01", title="Flow Channel")

    import anyio

    async def _test_channel() -> None:
        chan = await flow.verify_channel(_DummyProvider())  # type: ignore[arg-type]
        assert chan.channel_id == "UC_FLOW_01"

    anyio.run(_test_channel)

    # revoke clears tokens remotely and locally
    res = flow.revoke()
    assert res.encrypted_file_deleted is True
    assert store.load_bundle() is None


def test_urllib_http_transport_network_failure_raises_tool_error() -> None:
    """UrllibHttpTransport network failure raises ToolError(AUTH_REAUTHORIZATION_REQUIRED)."""
    transport = UrllibHttpTransport()
    with pytest.raises(ToolError) as exc:
        # Non-routable IP to guarantee immediate connection failure
        transport.post("http://192.0.2.1:1/token", {"test": "val"}, timeout=0.5)
    assert exc.value.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED
