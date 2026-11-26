"""Encrypted OAuth token storage (OS keyring + AES-256-GCM fallback) per ADR-0006."""

from __future__ import annotations

import base64
import contextlib
import importlib
import json
import logging
import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from yt_intel_mcp.config import AppConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.store import SQLiteStore

__all__ = [
    "DEFAULT_ACCOUNT_KEY",
    "DEFAULT_SERVICE_NAME",
    "YOUTUBE_FORCE_SSL_SCOPE",
    "YOUTUBE_READONLY_SCOPE",
    "KeyringBackend",
    "RevokeResult",
    "StorageBackend",
    "TokenBundle",
    "TokenMetadata",
    "TokenStore",
    "load_system_keyring",
]

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_NAME = "yt-intel-mcp"
DEFAULT_ACCOUNT_KEY = "default"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
YOUTUBE_FORCE_SSL_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"

_FILE_MAGIC = b"YTIMTOK1"
_NONCE_BYTES = 12
_KEY_BYTES = 32
_TOKENS_FILENAME = "tokens.enc"
_KEY_FILENAME = ".token_key"

StorageBackend = Literal["keyring", "aes-256-gcm", "none"]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class TokenBundle:
    """OAuth 2.0 credential bundle stored encrypted at rest (never logged or returned)."""

    access_token: str
    refresh_token: str
    scopes: tuple[str, ...]
    expires_at_utc: datetime
    issued_at_utc: datetime
    channel_id: str | None = None
    has_channel: bool = True

    def __post_init__(self) -> None:
        if not self.access_token or not self.refresh_token:
            raise ValueError("TokenBundle requires non-empty access_token and refresh_token.")

    def __repr__(self) -> str:
        return (
            "TokenBundle("
            "access_token='[REDACTED]', "
            "refresh_token='[REDACTED]', "
            f"scopes={self.scopes!r}, "
            f"expires_at_utc={self.expires_at_utc!r}, "
            f"issued_at_utc={self.issued_at_utc!r}, "
            f"channel_id={self.channel_id!r}, "
            f"has_channel={self.has_channel!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    def to_metadata(self, storage_backend: StorageBackend) -> TokenMetadata:
        """Project only non-secret status fields for get_auth_status (NFR-3)."""
        return TokenMetadata(
            authenticated=True,
            scopes=self.scopes,
            expires_at_utc=_ensure_utc(self.expires_at_utc),
            issued_at_utc=_ensure_utc(self.issued_at_utc),
            has_channel=self.has_channel,
            channel_id=self.channel_id,
            storage_backend=storage_backend,
        )


@dataclass(frozen=True, slots=True)
class TokenMetadata:
    """Non-secret authentication status projection safe for MCP tool responses."""

    authenticated: bool
    scopes: tuple[str, ...]
    expires_at_utc: datetime | None
    issued_at_utc: datetime | None
    has_channel: bool | None
    channel_id: str | None
    storage_backend: StorageBackend


@dataclass(frozen=True, slots=True)
class RevokeResult:
    """Summary of local token deletion and personal data purge during auth revocation."""

    keyring_cleared: bool
    encrypted_file_deleted: bool
    personal_cache_deleted: int
    first_observed_deleted: int


@runtime_checkable
class KeyringBackend(Protocol):
    """Minimal OS keyring credential store interface."""

    def get_password(self, service_name: str, username: str) -> str | None:
        """Fetch stored credential string or None."""
        ...

    def set_password(self, service_name: str, username: str, password: str) -> None:
        """Persist credential string in the OS keyring."""
        ...

    def delete_password(self, service_name: str, username: str) -> None:
        """Delete credential string from the OS keyring."""
        ...


def load_system_keyring() -> KeyringBackend | None:
    """Return the optional ``keyring`` module when installed and backed by a usable store."""
    try:
        module = importlib.import_module("keyring")
        get_kr = getattr(module, "get_keyring", None)
        if callable(get_kr):
            backend = get_kr()
            if isinstance(backend, KeyringBackend):
                return backend
        if isinstance(module, KeyringBackend):
            return module
    except Exception:
        return None
    return None


def _encode_bundle(bundle: TokenBundle) -> str:
    payload = {
        "access_token": bundle.access_token,
        "refresh_token": bundle.refresh_token,
        "scopes": list(bundle.scopes),
        "expires_at_utc": _ensure_utc(bundle.expires_at_utc).isoformat(),
        "issued_at_utc": _ensure_utc(bundle.issued_at_utc).isoformat(),
        "channel_id": bundle.channel_id,
        "has_channel": bundle.has_channel,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def _decode_bundle(raw_json: str) -> TokenBundle:
    decoded = json.loads(raw_json)
    if not isinstance(decoded, dict):
        raise ValueError("Stored token payload must be a JSON object.")
    channel_raw = decoded.get("channel_id")
    return TokenBundle(
        access_token=str(decoded["access_token"]),
        refresh_token=str(decoded["refresh_token"]),
        scopes=tuple(str(scope) for scope in decoded.get("scopes", ())),
        expires_at_utc=_ensure_utc(datetime.fromisoformat(str(decoded["expires_at_utc"]))),
        issued_at_utc=_ensure_utc(datetime.fromisoformat(str(decoded["issued_at_utc"]))),
        channel_id=str(channel_raw) if channel_raw is not None else None,
        has_channel=bool(decoded.get("has_channel", True)),
    )


def _decode_key_material(raw_value: str) -> bytes:
    cleaned = raw_value.strip()
    if len(cleaned) == _KEY_BYTES * 2:
        try:
            decoded = bytes.fromhex(cleaned)
            if len(decoded) == _KEY_BYTES:
                return decoded
        except ValueError:
            pass
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            padded = cleaned + ("=" * (-len(cleaned) % 4))
            decoded = decoder(padded.encode("ascii"))
            if len(decoded) == _KEY_BYTES:
                return decoded
        except Exception:
            continue
    raise ValueError("YT_INTEL_TOKEN_KEY must decode to exactly 32 bytes (hex or base64).")


def _chmod_owner_only(path: Path) -> None:
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _chmod_owner_only(tmp_path)
        os.replace(tmp_path, target)
        _chmod_owner_only(target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _secure_delete_file(path: Path) -> bool:
    if not path.is_file():
        return False
    size = path.stat().st_size
    if size > 0:
        with path.open("r+b") as handle:
            handle.write(b"\x00" * size)
            handle.flush()
            os.fsync(handle.fileno())
    path.unlink(missing_ok=True)
    return True


class TokenStore:
    """Two layer encrypted credential store (OS keyring + AES-256-GCM tokens.enc)."""

    def __init__(
        self,
        data_dir: Path | str | None = None,
        *,
        config: AppConfig | None = None,
        keyring_backend: KeyringBackend | None = None,
        use_system_keyring: bool = True,
        service_name: str = DEFAULT_SERVICE_NAME,
        account_key: str = DEFAULT_ACCOUNT_KEY,
        encryption_key: bytes | None = None,
        environ: Mapping[str, str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        base_config = config or AppConfig()
        self.data_dir = Path(data_dir) if data_dir is not None else base_config.data_dir
        self.tokens_path = self.data_dir / _TOKENS_FILENAME
        self.key_path = self.data_dir / _KEY_FILENAME
        self.service_name = service_name
        self.account_key = account_key
        self._environ = os.environ if environ is None else environ
        self._explicit_key = encryption_key
        if self._explicit_key is not None and len(self._explicit_key) != _KEY_BYTES:
            raise ValueError(f"encryption_key must be {_KEY_BYTES} bytes.")
        self._keyring: KeyringBackend | None = (
            keyring_backend
            if keyring_backend is not None
            else (load_system_keyring() if use_system_keyring else None)
        )
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        keyring_backend: KeyringBackend | None = None,
        use_system_keyring: bool = True,
    ) -> TokenStore:
        """Create a TokenStore rooted at ``config.data_dir``."""
        return cls(
            config.data_dir,
            config=config,
            keyring_backend=keyring_backend,
            use_system_keyring=use_system_keyring,
        )

    def _aad(self) -> bytes:
        return f"yt-intel-mcp:v1:{self.service_name}:{self.account_key}".encode()

    def _resolve_aes_key(self, *, create_if_missing: bool) -> bytes | None:
        if self._explicit_key is not None:
            return self._explicit_key
        env_key = self._environ.get("YT_INTEL_TOKEN_KEY")
        if env_key:
            return _decode_key_material(env_key)
        if self.key_path.is_file():
            raw = self.key_path.read_bytes()
            if len(raw) != _KEY_BYTES:
                raise ToolError(
                    ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                    "Local token encryption key is invalid; re-authorisation is required.",
                )
            return raw
        if not create_if_missing:
            return None
        generated = os.urandom(_KEY_BYTES)
        _atomic_write_bytes(self.key_path, generated)
        return generated

    def _write_encrypted_file(self, bundle: TokenBundle) -> None:
        key = self._resolve_aes_key(create_if_missing=True)
        assert key is not None
        nonce = os.urandom(_NONCE_BYTES)
        plaintext = _encode_bundle(bundle).encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, self._aad())
        _atomic_write_bytes(self.tokens_path, _FILE_MAGIC + nonce + ciphertext)

    def _read_encrypted_file(self) -> TokenBundle | None:
        if not self.tokens_path.is_file():
            return None
        raw = self.tokens_path.read_bytes()
        header_len = len(_FILE_MAGIC) + _NONCE_BYTES
        if len(raw) <= header_len or not raw.startswith(_FILE_MAGIC):
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "Encrypted token store is corrupted; please sign in again.",
            )
        key = self._resolve_aes_key(create_if_missing=False)
        if key is None:
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "Local encryption key missing for tokens.enc; please sign in again.",
            )
        nonce = raw[len(_FILE_MAGIC) : header_len]
        ciphertext = raw[header_len:]
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, self._aad())
            return _decode_bundle(plaintext.decode("utf-8"))
        except (InvalidTag, ValueError, KeyError, UnicodeDecodeError) as exc:
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "Stored OAuth credentials could not be decrypted; please re-authorise.",
            ) from exc

    def save_bundle(self, bundle: TokenBundle) -> StorageBackend:
        """Persist OAuth tokens via OS keyring or AES-256-GCM fallback (never plaintext)."""
        serialized = _encode_bundle(bundle)
        if self._keyring is not None:
            try:
                self._keyring.set_password(self.service_name, self.account_key, serialized)
                _secure_delete_file(self.tokens_path)
                logger.info("Saved OAuth credentials to OS keyring backend.")
                return "keyring"
            except Exception:
                logger.warning("OS keyring unavailable; falling back to AES-256-GCM file store.")

        self._write_encrypted_file(bundle)
        logger.info("Saved OAuth credentials to AES-256-GCM encrypted file store.")
        return "aes-256-gcm"

    def load_bundle(self) -> tuple[TokenBundle, StorageBackend] | None:
        """Load decrypted OAuth bundle and active backend, or None if unauthenticated."""
        if self._keyring is not None:
            try:
                raw_secret = self._keyring.get_password(self.service_name, self.account_key)
                if raw_secret:
                    return _decode_bundle(raw_secret), "keyring"
            except Exception:
                logger.warning("OS keyring read failed; checking AES-256-GCM file store.")

        file_bundle = self._read_encrypted_file()
        if file_bundle is not None:
            return file_bundle, "aes-256-gcm"
        return None

    def read_metadata(self) -> TokenMetadata:
        """Return non-secret auth status metadata safe for MCP tool outputs (NFR-3)."""
        loaded = self.load_bundle()
        if loaded is None:
            return TokenMetadata(
                authenticated=False,
                scopes=(),
                expires_at_utc=None,
                issued_at_utc=None,
                has_channel=None,
                channel_id=None,
                storage_backend="none",
            )
        bundle, backend = loaded
        return bundle.to_metadata(backend)

    def update_access_token(
        self,
        access_token: str,
        expires_at_utc: datetime,
        *,
        scopes: tuple[str, ...] | None = None,
        channel_id: str | None = None,
        has_channel: bool | None = None,
    ) -> TokenBundle:
        """Update access token after silent refresh while preserving refresh_token."""
        loaded = self.load_bundle()
        if loaded is None:
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "No stored OAuth credentials found; please sign in.",
            )
        existing, _ = loaded
        updated = TokenBundle(
            access_token=access_token,
            refresh_token=existing.refresh_token,
            scopes=scopes if scopes is not None else existing.scopes,
            expires_at_utc=_ensure_utc(expires_at_utc),
            issued_at_utc=existing.issued_at_utc,
            channel_id=channel_id if channel_id is not None else existing.channel_id,
            has_channel=has_channel if has_channel is not None else existing.has_channel,
        )
        self.save_bundle(updated)
        return updated

    def revoke(self, *, store: SQLiteStore | None = None) -> RevokeResult:
        """Delete stored tokens from keyring and disk and purge personal SQLite cache (NFR-7)."""
        keyring_cleared = False
        if self._keyring is not None:
            try:
                self._keyring.delete_password(self.service_name, self.account_key)
                keyring_cleared = True
            except Exception:
                keyring_cleared = False

        file_deleted = _secure_delete_file(self.tokens_path)

        target_store = store
        if target_store is None:
            default_db = self.data_dir / "yt_intel.db"
            if default_db.is_file():
                target_store = SQLiteStore(default_db)

        cache_deleted = 0
        observed_deleted = 0
        if target_store is not None:
            cache_deleted, observed_deleted = target_store.purge_personal_data()

        logger.info(
            "Revoked local OAuth credentials and purged personal cache (cache=%d, observed=%d).",
            cache_deleted,
            observed_deleted,
        )
        return RevokeResult(
            keyring_cleared=keyring_cleared,
            encrypted_file_deleted=file_deleted,
            personal_cache_deleted=cache_deleted,
            first_observed_deleted=observed_deleted,
        )
