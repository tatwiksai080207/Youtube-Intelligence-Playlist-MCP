"""Security tests for encrypted token storage, log redaction, and get_auth_status (SEC_OAUTH)."""

# ruff: noqa: N802
from __future__ import annotations

import ast
import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from yt_intel_mcp.auth import (
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    TokenBundle,
    TokenStore,
)
from yt_intel_mcp.config import AppConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.schemas import list_schema_names, load_schema
from yt_intel_mcp.server import create_server
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

    server = create_server()
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
