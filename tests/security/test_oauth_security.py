"""Security tests for encrypted token storage, log redaction, and get_auth_status (SEC_OAUTH)."""

# ruff: noqa: N802
from __future__ import annotations

import ast
import base64
import json
import logging
import urllib.parse
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from yt_intel_mcp.auth import (
    GOOGLE_AUTH_URL,
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    LocalOAuthCallbackServer,
    OAuthFlow,
    TokenBundle,
    TokenStore,
    build_authorization_url,
    generate_code_challenge,
    generate_code_verifier,
)
from yt_intel_mcp.config import AppConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.schemas import list_schema_names, load_schema
from yt_intel_mcp.server import create_base_server
from yt_intel_mcp.tools import execute_get_auth_status, register_auth_status

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_HTTP_IMPORTS = {
    "httpx",
    "httpx2",
    "httpcore",
    "httpcore2",
    "requests",
    "aiohttp",
    "google",
}


class _FakeKeyring:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.items: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, username: str) -> str | None:
        if self.fail:
            raise RuntimeError("No keyring daemon")
        return self.items.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        if self.fail:
            raise RuntimeError("No keyring daemon")
        self.items[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        if self.fail:
            raise RuntimeError("No keyring daemon")
        self.items.pop((service_name, username), None)


def _sample_bundle(*, write_scope: bool = False, has_channel: bool = True) -> TokenBundle:
    now = datetime(2026, 11, 26, 15, 0, tzinfo=UTC)
    scopes = (
        (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE)
        if write_scope
        else (YOUTUBE_READONLY_SCOPE,)
    )
    return TokenBundle(
        access_token="ya29." + "synthetic_access_token_do_not_expose",
        refresh_token="1//0g" + "synthetic_refresh_token_do_not_expose",
        scopes=scopes,
        expires_at_utc=now + timedelta(hours=1),
        issued_at_utc=now,
        channel_id="UC_SYNTH_USER_001" if has_channel else None,
        has_channel=has_channel,
    )


def test_SEC_OAUTH_bundle_redacts_tokens_and_aes_gcm_has_zero_plaintext_on_disk(
    tmp_path: Path,
) -> None:
    bundle = _sample_bundle()
    assert bundle.access_token not in repr(bundle)
    assert bundle.refresh_token not in repr(bundle)
    assert bundle.access_token not in str(bundle)
    assert bundle.refresh_token not in str(bundle)
    assert "[REDACTED]" in repr(bundle)

    cfg = AppConfig(data_dir=tmp_path / "secure_data")
    token_store = TokenStore.from_config(cfg, use_system_keyring=False)
    backend = token_store.save_bundle(bundle)
    assert backend == "aes-256-gcm"
    assert token_store.tokens_path.is_file()
    assert token_store.key_path.is_file()
    assert not (cfg.data_dir / "token.json").exists()

    # Zero plaintext token bytes anywhere in data_dir.
    for file_path in cfg.data_dir.rglob("*"):
        if file_path.is_file():
            raw_bytes = file_path.read_bytes()
            assert bundle.access_token.encode("utf-8") not in raw_bytes
            assert bundle.refresh_token.encode("utf-8") not in raw_bytes

    loaded = token_store.load_bundle()
    assert loaded is not None
    loaded_bundle, loaded_backend = loaded
    assert loaded_backend == "aes-256-gcm"
    assert loaded_bundle == bundle

    # Tampered ciphertext fails authentication tag verification cleanly.
    tampered = bytearray(token_store.tokens_path.read_bytes())
    tampered[-1] ^= 0xFF
    token_store.tokens_path.write_bytes(bytes(tampered))
    with pytest.raises(ToolError) as err:
        token_store.load_bundle()
    assert err.value.code is ErrorCode.AUTH_REAUTHORIZATION_REQUIRED


def test_SEC_OAUTH_env_key_and_keyring_primary_with_fallback(tmp_path: Path) -> None:
    raw_key = b"K" * 32
    b64_key = base64.urlsafe_b64encode(raw_key).decode("ascii")
    failing_kr = _FakeKeyring(fail=True)
    fallback_store = TokenStore(
        tmp_path / "env_key_dir",
        keyring_backend=failing_kr,
        environ={"YT_INTEL_TOKEN_KEY": b64_key},
    )
    bundle = _sample_bundle(write_scope=True)
    assert fallback_store.save_bundle(bundle) == "aes-256-gcm"
    assert not fallback_store.key_path.exists()
    loaded = fallback_store.load_bundle()
    assert loaded is not None and loaded[0] == bundle

    # Working keyring takes precedence and removes stale tokens.enc file.
    working_kr = _FakeKeyring(fail=False)
    kr_store = TokenStore(
        tmp_path / "env_key_dir",
        keyring_backend=working_kr,
        environ={"YT_INTEL_TOKEN_KEY": b64_key},
    )
    assert kr_store.save_bundle(bundle) == "keyring"
    assert not kr_store.tokens_path.exists()
    kr_loaded = kr_store.load_bundle()
    assert kr_loaded is not None and kr_loaded[1] == "keyring"

    refreshed = kr_store.update_access_token(
        "ya29." + "refreshed_access_token_value",
        datetime(2026, 11, 26, 18, 0, tzinfo=UTC),
    )
    assert refreshed.refresh_token == bundle.refresh_token


@pytest.mark.anyio
async def test_SEC_OAUTH_get_auth_status_exposes_only_metadata_and_never_logs_tokens(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert "get_auth_status" in list_schema_names()
    schema = load_schema("get_auth_status")
    assert schema["additionalProperties"] is False
    assert schema["properties"] == {}

    token_store = TokenStore(tmp_path / "auth_tool", use_system_keyring=False)
    unauth = execute_get_auth_status(token_store)
    assert unauth["quota_used"] == {"units": 0, "search_calls": 0}
    assert unauth["data"]["authenticated"] is False
    assert unauth["data"]["storage_backend"] == "none"

    bundle = _sample_bundle(write_scope=True, has_channel=False)
    with caplog.at_level(logging.DEBUG):
        token_store.save_bundle(bundle)
        direct = execute_get_auth_status(
            token_store,
            now_utc=datetime(2026, 11, 26, 15, 30, tzinfo=UTC),
        )

    assert direct["quota_used"] == {"units": 0, "search_calls": 0}
    assert direct["data"]["authenticated"] is True
    assert direct["data"]["scopes"] == [YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE]
    assert direct["data"]["write_scope_granted"] is True
    assert direct["data"]["has_channel"] is False
    assert direct["data"]["access_token_expired"] is False
    assert bundle.access_token not in json.dumps(direct)
    assert bundle.refresh_token not in json.dumps(direct)
    assert bundle.access_token not in caplog.text
    assert bundle.refresh_token not in caplog.text

    server = create_base_server()
    register_auth_status(
        server, token_store, clock=lambda: datetime(2026, 11, 26, 15, 30, tzinfo=UTC)
    )
    async with (
        create_client_server_memory_streams() as (client_streams, server_streams),
        anyio.create_task_group() as task_group,
    ):

        async def _serve() -> None:
            await server._lowlevel_server.run(
                server_streams[0],
                server_streams[1],
                server._lowlevel_server.create_initialization_options(),
            )

        task_group.start_soon(_serve)
        async with ClientSession(client_streams[0], client_streams[1]) as session:
            await session.initialize()
            res = await session.call_tool("get_auth_status", {})
            assert res.structured_content is not None
            serialized = json.dumps(res.structured_content)
            assert bundle.access_token not in serialized
            assert bundle.refresh_token not in serialized
            assert res.structured_content["data"]["storage_backend"] == "aes-256-gcm"
        task_group.cancel_scope.cancel()


def test_SE_6_auth_modules_have_no_http_or_google_imports() -> None:
    targets = [
        ROOT / "src" / "yt_intel_mcp" / "auth" / "token_store.py",
        ROOT / "src" / "yt_intel_mcp" / "auth" / "oauth.py",
        ROOT / "src" / "yt_intel_mcp" / "tools" / "get_auth_status.py",
    ]
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(FORBIDDEN_HTTP_IMPORTS), f"Disallowed import in {path}"


def test_SEC_OAUTH_pkce_verifier_and_rfc7636_test_vector() -> None:
    """Validate RFC 7636 Appendix B test vector and verifier character constraints."""
    # RFC 7636 Appendix B official test vector
    rfc_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    expected_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    assert generate_code_challenge(rfc_verifier) == expected_challenge

    # Length constraints
    with pytest.raises(ValueError, match="between 43 and 128"):
        generate_code_verifier(42)
    with pytest.raises(ValueError, match="between 43 and 128"):
        generate_code_verifier(129)
    with pytest.raises(ValueError, match="between 43 and 128"):
        generate_code_challenge("too_short")

    # Character set unreserved chars check: [A-Za-z0-9-._~]
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~")
    for length in (43, 64, 128):
        verifier = generate_code_verifier(length)
        assert len(verifier) == length
        assert set(verifier).issubset(allowed_chars)
        challenge = generate_code_challenge(verifier)
        assert "=" not in challenge  # base64url unpadded


def test_SEC_OAUTH_initial_login_requests_readonly_scope_only() -> None:
    """Initial login URL requests youtube.readonly only (C-6 least privilege)."""
    auth_url = build_authorization_url(
        client_id="yt-test-client",
        redirect_uri="http://127.0.0.1:8080/callback",
        scopes=(YOUTUBE_READONLY_SCOPE,),
        code_challenge="dummy_challenge",
        state="csrf_state",
    )
    assert auth_url.startswith(GOOGLE_AUTH_URL)
    assert f"scope={urllib.parse.quote(YOUTUBE_READONLY_SCOPE, safe='')}" in auth_url
    assert urllib.parse.quote(YOUTUBE_FORCE_SSL_SCOPE, safe="") not in auth_url
    assert "code_challenge_method=S256" in auth_url
    assert "access_type=offline" in auth_url


def test_SEC_OAUTH_separate_full_write_consent_requests_force_ssl() -> None:
    """Write consent requests youtube.force-ssl; no incremental auth on desktop (C-7, FR-7.1)."""
    write_url = build_authorization_url(
        client_id="yt-test-client",
        redirect_uri="http://127.0.0.1:8080/callback",
        scopes=(YOUTUBE_FORCE_SSL_SCOPE,),
        code_challenge="dummy_challenge",
        state="csrf_state",
    )
    assert f"scope={urllib.parse.quote(YOUTUBE_FORCE_SSL_SCOPE, safe='')}" in write_url


def test_SEC_OAUTH_loopback_rejects_non_loopback_bind_address() -> None:
    """Loopback listener strictly rejects non-127.0.0.1 hosts (SRS Section 3.3)."""
    for forbidden_host in ("0.0.0.0", "192.168.1.1", "example.com", "localhost"):
        with pytest.raises(ValueError, match=r"strictly to 127\.0\.0\.1"):
            LocalOAuthCallbackServer(host=forbidden_host)


def test_SEC_OAUTH_mock_transport_executes_full_flow_with_zero_live_network(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test full login, silent refresh, and ensure_write with mock transport and zero leaks."""

    class _MockTransport:
        def __init__(self) -> None:
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
            grant_type = data.get("grant_type")
            if grant_type == "authorization_code":
                return 200, {
                    "access_token": "ya29.synthetic_initial_token",
                    "refresh_token": "1//0g_synthetic_refresh_token",
                    "expires_in": 3600,
                    "scope": YOUTUBE_READONLY_SCOPE,
                    "token_type": "Bearer",
                }
            if grant_type == "refresh_token":
                return 200, {
                    "access_token": "ya29.synthetic_refreshed_token",
                    "expires_in": 3600,
                    "scope": YOUTUBE_READONLY_SCOPE,
                    "token_type": "Bearer",
                }
            return 200, {}

    transport = _MockTransport()
    store = TokenStore(tmp_path / "mock_oauth_dir", use_system_keyring=False)
    flow = OAuthFlow(
        store,
        client_id="mock-client-id",
        transport=transport,
        clock=lambda: datetime(2026, 11, 27, 10, 0, tzinfo=UTC),
    )

    with caplog.at_level(logging.DEBUG):
        # 1. Login with auth code override (bypasses browser, exercises full exchange and save)
        bundle = flow.login_readonly(auth_code_override="mock_auth_code_123")
        assert bundle.access_token == "ya29.synthetic_initial_token"
        assert bundle.refresh_token == "1//0g_synthetic_refresh_token"
        assert bundle.scopes == (YOUTUBE_READONLY_SCOPE,)

        # 2. Silent refresh
        refreshed = flow.refresh_token()
        assert refreshed.access_token == "ya29.synthetic_refreshed_token"
        assert refreshed.refresh_token == "1//0g_synthetic_refresh_token"

        # 3. Ensure write with auth code override completes separate consent
        def _write_post(
            url: str,
            data: Mapping[str, str],
            *,
            headers: Mapping[str, str] | None = None,
            timeout: float = 30.0,
        ) -> tuple[int, dict[str, Any]]:
            return 200, {
                "access_token": "ya29.synthetic_write_token",
                "refresh_token": "1//0g_synthetic_write_refresh_token",
                "expires_in": 3600,
                "scope": f"{YOUTUBE_READONLY_SCOPE} {YOUTUBE_FORCE_SSL_SCOPE}",
                "token_type": "Bearer",
            }

        transport.post = _write_post  # type: ignore[assignment]
        write_bundle = flow.ensure_write(
            interactive=True,
            auth_code_override="mock_write_auth_code_456",
        )
        assert YOUTUBE_FORCE_SSL_SCOPE in write_bundle.scopes

    # Assert zero plaintext token leakage in logs
    assert "ya29.synthetic_initial_token" not in caplog.text
    assert "ya29.synthetic_refreshed_token" not in caplog.text
    assert "1//0g_synthetic_refresh_token" not in caplog.text
    assert "1//0g_synthetic_write_refresh_token" not in caplog.text
