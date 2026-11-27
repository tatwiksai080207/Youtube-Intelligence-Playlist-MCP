"""OAuth 2.0 PKCE authentication flow, silent token refresh, and channel verification.

Implements FR-7.1, FR-7.2, FR-7.3, C-4, C-5, C-6, C-7, and INV-20.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import http.server
import json
import logging
import secrets
import string
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from yt_intel_mcp.auth.token_store import (
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    RevokeResult,
    TokenBundle,
    TokenStore,
)
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import ChannelMeta
from yt_intel_mcp.provider.base import YouTubeProvider
from yt_intel_mcp.store import SQLiteStore

__all__ = [
    "DEFAULT_CALLBACK_PATH",
    "DEFAULT_CLIENT_ID",
    "DEFAULT_LOOPBACK_HOST",
    "DEFAULT_TIMEOUT_SECONDS",
    "GOOGLE_AUTH_URL",
    "GOOGLE_REVOKE_URL",
    "GOOGLE_TOKEN_URL",
    "HttpTransport",
    "LocalOAuthCallbackServer",
    "OAuthFlow",
    "UrllibHttpTransport",
    "build_authorization_url",
    "check_channel_presence",
    "ensure_write_scope",
    "exchange_code_for_tokens",
    "generate_code_challenge",
    "generate_code_verifier",
    "login_with_pkce",
    "refresh_access_token",
    "revoke_tokens",
]

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

DEFAULT_LOOPBACK_HOST = "127.0.0.1"
DEFAULT_CALLBACK_PATH = "/callback"
DEFAULT_CLIENT_ID = "yt-intel-mcp-desktop-client"
DEFAULT_TIMEOUT_SECONDS = 120.0

_PKCE_CHARSET = string.ascii_letters + string.digits + "-._~"


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def generate_code_verifier(length: int = 64) -> str:
    """Generate high entropy PKCE code verifier per RFC 7636 (43 to 128 characters)."""
    if not (43 <= length <= 128):
        raise ValueError("PKCE code verifier length must be between 43 and 128 characters.")
    return "".join(secrets.choice(_PKCE_CHARSET) for _ in range(length))


def generate_code_challenge(verifier: str) -> str:
    """Generate RFC 7636 S256 code challenge from code verifier."""
    if not (43 <= len(verifier) <= 128):
        raise ValueError("PKCE code verifier length must be between 43 and 128 characters.")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: Sequence[str],
    code_challenge: str,
    state: str,
    access_type: str = "offline",
    prompt: str = "consent",
) -> str:
    """Construct Google OAuth 2.0 authorization URL for desktop PKCE flow."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "access_type": access_type,
        "prompt": prompt,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


@runtime_checkable
class HttpTransport(Protocol):
    """Transport protocol for OAuth token HTTP endpoints enabling deterministic mocking."""

    def post(
        self,
        url: str,
        data: Mapping[str, str],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, Any]]:
        """Perform HTTP POST request returning status code and decoded response body."""
        ...


class UrllibHttpTransport:
    """Standard library HTTP transport using urllib.request."""

    def post(
        self,
        url: str,
        data: Mapping[str, str],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, Any]]:
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")
        req_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)
        request = urllib.request.Request(
            url,
            data=encoded_data,
            headers=req_headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status_code = response.status
                body = response.read().decode("utf-8")
                try:
                    parsed: dict[str, Any] = json.loads(body)
                except Exception:
                    parsed = {"raw": body}
                return status_code, parsed
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = {"raw": body}
            return exc.code, parsed
        except Exception as exc:
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                f"OAuth network connection failed: {exc}",
            ) from exc


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """One shot HTTP request handler for OAuth loopback redirect."""

    server: LocalOAuthCallbackServer

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path != self.server.callback_path:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        query_params = urllib.parse.parse_qs(parsed_url.query)
        error_val = query_params.get("error", [None])[0]
        state_val = query_params.get("state", [None])[0]
        code_val = query_params.get("code", [None])[0]

        if error_val:
            self.server.received_error = error_val
            self._send_html_response(
                400,
                "Authentication Cancelled",
                f"OAuth authorization was not completed ({error_val}). You can close this window.",
            )
            return

        if state_val != self.server.expected_state:
            self.server.received_error = "state_mismatch"
            self._send_html_response(
                400,
                "Authentication Failed",
                "OAuth CSRF state parameter mismatch. You can close this window.",
            )
            return

        if not code_val:
            self.server.received_error = "missing_code"
            self._send_html_response(
                400,
                "Authentication Incomplete",
                "No authorization code returned. You can close this window.",
            )
            return

        self.server.received_code = code_val
        self._send_html_response(
            200,
            "Authentication Successful",
            "YouTube Video Intelligence Server authentication complete. You can close this window.",
        )

    def _send_html_response(self, status: int, title: str, message: str) -> None:
        html = (
            "<!DOCTYPE html>\n"
            "<html lang='en'>\n"
            "<head>\n"
            "  <meta charset='utf-8'>\n"
            f"  <title>{title}</title>\n"
            "  <style>body { font-family: sans-serif; margin: 40px; line-height: 1.5; }</style>\n"
            "</head>\n"
            "<body>\n"
            f"  <h2>{title}</h2>\n"
            f"  <p>{message}</p>\n"
            "</body>\n"
            "</html>\n"
        )
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP request logging to stderr."""


class LocalOAuthCallbackServer(http.server.HTTPServer):
    """Ephemeral loopback redirect server binding strictly to 127.0.0.1 (SRS Section 3.3)."""

    def __init__(
        self,
        host: str = DEFAULT_LOOPBACK_HOST,
        port: int = 0,
        *,
        expected_state: str = "",
        callback_path: str = DEFAULT_CALLBACK_PATH,
    ) -> None:
        if host != DEFAULT_LOOPBACK_HOST:
            raise ValueError(
                f"Loopback listener must bind strictly to {DEFAULT_LOOPBACK_HOST}, got {host!r}."
            )
        self.expected_state = expected_state
        self.callback_path = callback_path
        self.received_code: str | None = None
        self.received_error: str | None = None
        super().__init__((host, port), _CallbackHandler)

    @property
    def redirect_uri(self) -> str:
        """Return the loopback redirect URI configured for Google OAuth."""
        port = self.server_port
        return f"http://{DEFAULT_LOOPBACK_HOST}:{port}{self.callback_path}"

    def wait_for_code(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
        """Handle a single HTTP request on the loopback port and return the auth code."""
        self.timeout = timeout
        self.handle_request()
        if self.received_error:
            if self.received_error == "state_mismatch":
                raise ToolError(
                    ErrorCode.PERMISSION_DENIED,
                    "OAuth state mismatch detected (potential CSRF).",
                    details={"error": self.received_error},
                )
            raise ToolError(
                ErrorCode.PERMISSION_DENIED,
                f"OAuth authorization was denied or failed ({self.received_error}).",
                details={"error": self.received_error},
            )
        if not self.received_code:
            raise ToolError(
                ErrorCode.PERMISSION_DENIED,
                "OAuth authorization timed out or received no code.",
            )
        return self.received_code


def exchange_code_for_tokens(
    *,
    client_id: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    client_secret: str | None = None,
    transport: HttpTransport | None = None,
    now_utc: datetime | None = None,
) -> TokenBundle:
    """Exchange authorization code and PKCE verifier for OAuth tokens."""
    http = transport or UrllibHttpTransport()
    data = {
        "client_id": client_id,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    if client_secret:
        data["client_secret"] = client_secret

    status_code, response_data = http.post(GOOGLE_TOKEN_URL, data)
    now = _ensure_utc(now_utc or datetime.now(UTC))

    if status_code != 200:
        error_val = str(response_data.get("error", "unknown_error"))
        description = str(response_data.get("error_description", error_val))
        if error_val == "invalid_grant":
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                f"OAuth authorization code rejected ({description}); please re-authorise.",
                details={"error": error_val, "upstream_reason": "invalid_grant"},
            )
        raise ToolError(
            ErrorCode.PERMISSION_DENIED,
            f"OAuth token exchange failed ({description}).",
            details={"error": error_val, "http_status": status_code},
        )

    access_token = str(response_data.get("access_token", ""))
    refresh_token = str(response_data.get("refresh_token", ""))
    if not access_token or not refresh_token:
        raise ToolError(
            ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
            "OAuth token endpoint did not return required access_token and refresh_token.",
        )

    expires_in = int(response_data.get("expires_in", 3600))
    raw_scope = str(response_data.get("scope", ""))
    scopes = tuple(raw_scope.split()) if raw_scope else (YOUTUBE_READONLY_SCOPE,)

    return TokenBundle(
        access_token=access_token,
        refresh_token=refresh_token,
        scopes=scopes,
        expires_at_utc=now + timedelta(seconds=expires_in),
        issued_at_utc=now,
        has_channel=True,
    )


def refresh_access_token(
    bundle: TokenBundle,
    *,
    client_id: str,
    client_secret: str | None = None,
    transport: HttpTransport | None = None,
    now_utc: datetime | None = None,
) -> TokenBundle:
    """Silently refresh expired access token using stored refresh token (C-4)."""
    http = transport or UrllibHttpTransport()
    data = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": bundle.refresh_token,
    }
    if client_secret:
        data["client_secret"] = client_secret

    status_code, response_data = http.post(GOOGLE_TOKEN_URL, data)
    now = _ensure_utc(now_utc or datetime.now(UTC))

    if status_code != 200:
        error_val = str(response_data.get("error", "unknown_error"))
        description = str(response_data.get("error_description", error_val))
        if error_val == "invalid_grant":
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "OAuth refresh token expired or was revoked (invalid_grant); please sign in again.",
                details={"error": error_val, "upstream_reason": "invalid_grant"},
            )
        raise ToolError(
            ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
            f"OAuth token refresh failed ({description}).",
            details={"error": error_val, "http_status": status_code},
        )

    new_access_token = str(response_data.get("access_token", ""))
    if not new_access_token:
        raise ToolError(
            ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
            "OAuth refresh response missing fresh access_token.",
        )

    expires_in = int(response_data.get("expires_in", 3600))
    raw_scope = response_data.get("scope")
    scopes = tuple(str(raw_scope).split()) if raw_scope else bundle.scopes
    new_refresh = response_data.get("refresh_token")
    effective_refresh = str(new_refresh) if new_refresh else bundle.refresh_token

    return TokenBundle(
        access_token=new_access_token,
        refresh_token=effective_refresh,
        scopes=scopes,
        expires_at_utc=now + timedelta(seconds=expires_in),
        issued_at_utc=bundle.issued_at_utc,
        channel_id=bundle.channel_id,
        has_channel=bundle.has_channel,
    )


def login_with_pkce(
    token_store: TokenStore,
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    client_secret: str | None = None,
    scopes: Sequence[str] = (YOUTUBE_READONLY_SCOPE,),
    transport: HttpTransport | None = None,
    browser_opener: Callable[[str], None] | None = None,
    loopback_host: str = DEFAULT_LOOPBACK_HOST,
    loopback_port: int = 0,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    now_utc: datetime | None = None,
    auth_code_override: str | None = None,
) -> TokenBundle:
    """Execute OAuth 2.0 PKCE login over loopback listener and save credential bundle."""
    code_verifier = generate_code_verifier(64)
    code_challenge = generate_code_challenge(code_verifier)
    state = secrets.token_urlsafe(32)

    if auth_code_override is not None:
        redirect_uri = f"http://{DEFAULT_LOOPBACK_HOST}:8080{DEFAULT_CALLBACK_PATH}"
        bundle = exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            code=auth_code_override,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            transport=transport,
            now_utc=now_utc,
        )
        token_store.save_bundle(bundle)
        return bundle

    server = LocalOAuthCallbackServer(
        host=loopback_host,
        port=loopback_port,
        expected_state=state,
    )
    try:
        redirect_uri = server.redirect_uri
        auth_url = build_authorization_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            code_challenge=code_challenge,
            state=state,
        )
        if browser_opener is not None:
            browser_opener(auth_url)
        else:
            logger.info("Open this URL in your browser to authorise: %s", auth_url)

        code = server.wait_for_code(timeout=timeout)
        bundle = exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            transport=transport,
            now_utc=now_utc,
        )
        token_store.save_bundle(bundle)
        return bundle
    finally:
        server.server_close()


def ensure_write_scope(
    token_store: TokenStore,
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    client_secret: str | None = None,
    interactive: bool = False,
    transport: HttpTransport | None = None,
    browser_opener: Callable[[str], None] | None = None,
    loopback_host: str = DEFAULT_LOOPBACK_HOST,
    loopback_port: int = 0,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    now_utc: datetime | None = None,
    auth_code_override: str | None = None,
) -> TokenBundle:
    """Ensure write scope is granted; desktop apps require full consent (C-7, FR-7.1)."""
    loaded = token_store.load_bundle()
    if loaded is None:
        if not interactive and auth_code_override is None:
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "Authentication required before verifying write scope.",
            )
        return login_with_pkce(
            token_store,
            client_id=client_id,
            client_secret=client_secret,
            scopes=(YOUTUBE_FORCE_SSL_SCOPE,),
            transport=transport,
            browser_opener=browser_opener,
            loopback_host=loopback_host,
            loopback_port=loopback_port,
            timeout=timeout,
            now_utc=now_utc,
            auth_code_override=auth_code_override,
        )

    bundle, _ = loaded
    if YOUTUBE_FORCE_SSL_SCOPE in bundle.scopes:
        return bundle

    # Desktop clients do not support incremental authorization (C-7).
    if not interactive and auth_code_override is None:
        scope_msg = (
            "Playlist creation requires write scope "
            f"({YOUTUBE_FORCE_SSL_SCOPE}). "
            "Installed desktop applications do not support incremental authorization; "
            "please complete full authorization for write access."
        )
        raise ToolError(
            ErrorCode.SCOPE_INSUFFICIENT,
            scope_msg,
            details={
                "required_scope": YOUTUBE_FORCE_SSL_SCOPE,
                "granted_scopes": list(bundle.scopes),
            },
        )

    return login_with_pkce(
        token_store,
        client_id=client_id,
        client_secret=client_secret,
        scopes=(YOUTUBE_FORCE_SSL_SCOPE,),
        transport=transport,
        browser_opener=browser_opener,
        loopback_host=loopback_host,
        loopback_port=loopback_port,
        timeout=timeout,
        now_utc=now_utc,
        auth_code_override=auth_code_override,
    )


async def check_channel_presence(
    provider: YouTubeProvider,
    token_store: TokenStore | None = None,
) -> ChannelMeta:
    """Verify authenticated account has an active YouTube channel (C-5, FR-7.3)."""
    try:
        channel = await provider.get_my_channel()
    except ToolError as exc:
        if exc.code is ErrorCode.CHANNEL_REQUIRED:
            if token_store is not None:
                with contextlib.suppress(Exception):
                    loaded = token_store.load_bundle()
                    if loaded is not None:
                        token_store.update_access_token(
                            loaded[0].access_token,
                            loaded[0].expires_at_utc,
                            has_channel=False,
                            channel_id=None,
                        )
            raise
        raise

    if not channel.channel_id:
        if token_store is not None:
            with contextlib.suppress(Exception):
                loaded = token_store.load_bundle()
                if loaded is not None:
                    token_store.update_access_token(
                        loaded[0].access_token,
                        loaded[0].expires_at_utc,
                        has_channel=False,
                        channel_id=None,
                    )
        raise ToolError(
            ErrorCode.CHANNEL_REQUIRED,
            "The authenticated Google account does not have an active YouTube channel.",
            details={"has_channel": False},
        )

    if token_store is not None:
        with contextlib.suppress(Exception):
            loaded = token_store.load_bundle()
            if loaded is not None:
                token_store.update_access_token(
                    loaded[0].access_token,
                    loaded[0].expires_at_utc,
                    has_channel=True,
                    channel_id=channel.channel_id,
                )
    return channel


def revoke_tokens(
    token_store: TokenStore,
    *,
    transport: HttpTransport | None = None,
    sqlite_store: SQLiteStore | None = None,
) -> RevokeResult:
    """Revoke tokens remotely (best effort) and purge local encrypted store (NFR-7)."""
    loaded = token_store.load_bundle()
    if loaded is not None:
        bundle, _ = loaded
        http = transport or UrllibHttpTransport()
        for token_value in (bundle.refresh_token, bundle.access_token):
            if token_value:
                with contextlib.suppress(Exception):
                    http.post(GOOGLE_REVOKE_URL, {"token": token_value})
    return token_store.revoke(store=sqlite_store)


class OAuthFlow:
    """High level OAuth 2.0 PKCE lifecycle coordinator."""

    def __init__(
        self,
        token_store: TokenStore,
        *,
        client_id: str = DEFAULT_CLIENT_ID,
        client_secret: str | None = None,
        transport: HttpTransport | None = None,
        loopback_host: str = DEFAULT_LOOPBACK_HOST,
        loopback_port: int = 0,
        clock: Callable[[], datetime] | None = None,
        browser_opener: Callable[[str], None] | None = None,
    ) -> None:
        self.token_store = token_store
        self.client_id = client_id
        self.client_secret = client_secret
        self.transport = transport or UrllibHttpTransport()
        self.loopback_host = loopback_host
        self.loopback_port = loopback_port
        self.clock = clock or (lambda: datetime.now(UTC))
        self.browser_opener = browser_opener

    def login_readonly(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        auth_code_override: str | None = None,
    ) -> TokenBundle:
        """Execute initial read only login requesting youtube.readonly only (C-6)."""
        return login_with_pkce(
            self.token_store,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=(YOUTUBE_READONLY_SCOPE,),
            transport=self.transport,
            browser_opener=self.browser_opener,
            loopback_host=self.loopback_host,
            loopback_port=self.loopback_port,
            timeout=timeout,
            now_utc=self.clock(),
            auth_code_override=auth_code_override,
        )

    def login_write(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        auth_code_override: str | None = None,
    ) -> TokenBundle:
        """Execute write consent login requesting youtube.force-ssl (C-7, FR-7.1)."""
        return login_with_pkce(
            self.token_store,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=(YOUTUBE_FORCE_SSL_SCOPE,),
            transport=self.transport,
            browser_opener=self.browser_opener,
            loopback_host=self.loopback_host,
            loopback_port=self.loopback_port,
            timeout=timeout,
            now_utc=self.clock(),
            auth_code_override=auth_code_override,
        )

    def ensure_write(
        self,
        *,
        interactive: bool = False,
        auth_code_override: str | None = None,
    ) -> TokenBundle:
        """Ensure write scope is held or perform full write consent flow."""
        return ensure_write_scope(
            self.token_store,
            client_id=self.client_id,
            client_secret=self.client_secret,
            interactive=interactive,
            transport=self.transport,
            browser_opener=self.browser_opener,
            loopback_host=self.loopback_host,
            loopback_port=self.loopback_port,
            now_utc=self.clock(),
            auth_code_override=auth_code_override,
        )

    def refresh_token(self) -> TokenBundle:
        """Silently refresh stored access token using refresh_token."""
        loaded = self.token_store.load_bundle()
        if loaded is None:
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "No stored credentials to refresh; please sign in.",
            )
        bundle, _ = loaded
        refreshed = refresh_access_token(
            bundle,
            client_id=self.client_id,
            client_secret=self.client_secret,
            transport=self.transport,
            now_utc=self.clock(),
        )
        self.token_store.save_bundle(refreshed)
        return refreshed

    def get_valid_access_token(self, *, skew_seconds: int = 60) -> str:
        """Return a valid access token, performing silent refresh if near expiry."""
        loaded = self.token_store.load_bundle()
        if loaded is None:
            raise ToolError(
                ErrorCode.AUTH_REAUTHORIZATION_REQUIRED,
                "No active authentication credentials found; please sign in.",
            )
        bundle, _ = loaded
        now = self.clock()
        if now >= bundle.expires_at_utc - timedelta(seconds=skew_seconds):
            bundle = self.refresh_token()
        return bundle.access_token

    async def verify_channel(self, provider: YouTubeProvider) -> ChannelMeta:
        """Verify that the authenticated account has an active YouTube channel."""
        return await check_channel_presence(provider, self.token_store)

    def revoke(self, *, sqlite_store: SQLiteStore | None = None) -> RevokeResult:
        """Revoke remote token and purge local credentials and cache (NFR-7)."""
        return revoke_tokens(
            self.token_store,
            transport=self.transport,
            sqlite_store=sqlite_store,
        )
