"""Channel B: One-time 127.0.0.1 loopback confirmation page (FR-5.4, NFR-6, SRS §3.3)."""

from __future__ import annotations

import http.server
import logging
import secrets
import threading
import time
import urllib.parse
from collections.abc import Callable
from typing import Any

import anyio

from yt_intel_mcp.confirmation.summary import format_confirmation_summary_html
from yt_intel_mcp.confirmation.tokens import (
    ConfirmationDecision,
    ConfirmationToken,
    ConfirmationTokenStore,
)
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.playlist.drafts import PlaylistDraft

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_LOOPBACK_HOST",
    "LocalConfirmationPageServer",
    "serve_local_confirmation_page",
]

DEFAULT_LOOPBACK_HOST = "127.0.0.1"


class _ConfirmationHandler(http.server.BaseHTTPRequestHandler):
    """One shot HTTP request handler for loopback playlist confirmation."""

    server: LocalConfirmationPageServer

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path != self.server.secret_path:
            self._send_response_text(404, "Not Found")
            return

        html_body = format_confirmation_summary_html(
            self.server.draft,
            self.server.channel_id,
            csrf_token=self.server.csrf_token,
            secret_path=self.server.secret_path,
            account_name=self.server.account_name,
        )
        self._send_html_response(200, html_body)

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path != self.server.secret_path:
            self._send_response_text(404, "Not Found")
            return

        content_length_header = self.headers.get("Content-Length")
        if not content_length_header:
            self._send_response_text(400, "Missing Content-Length")
            return

        try:
            content_length = int(content_length_header)
            if content_length > 8192:
                self._send_response_text(413, "Payload Too Large")
                return
            post_bytes = self.rfile.read(content_length)
            body_str = post_bytes.decode("utf-8", errors="replace")
            form_data = urllib.parse.parse_qs(body_str)
        except Exception as exc:
            logger.warning("Failed parsing POST body: %s", exc)
            self._send_response_text(400, "Bad Request")
            return

        submitted_csrf = form_data.get("csrf_token", [""])[0]
        if not submitted_csrf or not secrets.compare_digest(submitted_csrf, self.server.csrf_token):
            self.server.received_error = "csrf_mismatch"
            self._send_response_text(403, "CSRF verification failed")
            return

        action_val = form_data.get("action", [""])[0].strip().lower()
        if action_val == "accept":
            self.server.decision = ConfirmationDecision.ACCEPT
            title = "Playlist Creation Approved"
            msg = (
                "Confirmation received. The server will now proceed with creating the playlist. "
                "You can close this window."
            )
        elif action_val in ("decline", "cancel"):
            self.server.decision = ConfirmationDecision.DECLINE
            title = "Playlist Creation Declined"
            msg = "Creation declined. No playlist will be created. You can close this window."
        else:
            self._send_response_text(400, "Unknown action")
            return

        resp_html = (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="utf-8">\n'
            f"  <title>{title}</title>\n"
            "  <style>body {{ font-family: sans-serif; margin: 40px; "
            "line-height: 1.5; color: #111827; }}</style>\n"
            "</head>\n"
            "<body>\n"
            f"  <h2>{title}</h2>\n"
            f"  <p>{msg}</p>\n"
            "</body>\n"
            "</html>\n"
        )
        self._send_html_response(200, resp_html)
        self.server.received_event.set()

    def _send_html_response(self, status: int, html_content: str) -> None:
        encoded = html_content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_response_text(self, status: int, text: str) -> None:
        encoded = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP request logging to stderr."""


class LocalConfirmationPageServer(http.server.HTTPServer):
    """Ephemeral confirmation page server binding strictly to 127.0.0.1 (FR-5.4, SRS §3.3)."""

    def __init__(
        self,
        host: str = DEFAULT_LOOPBACK_HOST,
        port: int = 0,
        *,
        draft: PlaylistDraft,
        channel_id: str,
        secret_path: str,
        csrf_token: str,
        account_name: str | None = None,
    ) -> None:
        if host != DEFAULT_LOOPBACK_HOST:
            raise ValueError(
                f"Confirmation page listener must bind strictly to "
                f"{DEFAULT_LOOPBACK_HOST}, got {host!r}."
            )
        self.draft = draft
        self.channel_id = channel_id
        self.secret_path = secret_path
        self.csrf_token = csrf_token
        self.account_name = account_name
        self.decision: ConfirmationDecision | None = None
        self.received_error: str | None = None
        self.received_event = threading.Event()
        super().__init__((host, port), _ConfirmationHandler)

    @property
    def confirmation_url(self) -> str:
        """Return unguessable loopback URL."""
        return f"http://{DEFAULT_LOOPBACK_HOST}:{self.server_port}{self.secret_path}"

    def wait_for_decision(self, timeout: float = 120.0) -> ConfirmationDecision:
        """Poll incoming requests until decision received or timeout expires."""
        self.timeout = 0.5
        start_time = time.monotonic()
        while not self.received_event.is_set():
            remaining = timeout - (time.monotonic() - start_time)
            if remaining <= 0:
                break
            self.handle_request()

        if self.decision is not None:
            return self.decision
        return ConfirmationDecision.DECLINE


async def serve_local_confirmation_page(
    draft: PlaylistDraft,
    channel_id: str,
    token_store: ConfirmationTokenStore,
    *,
    host: str = DEFAULT_LOOPBACK_HOST,
    port: int = 0,
    browser_opener: Callable[[str], None] | None = None,
    timeout_seconds: float = 120.0,
    account_name: str | None = None,
) -> ConfirmationToken:
    """Run the ephemeral loopback confirmation listener and mint the resulting token."""
    secret_path = f"/confirm_{secrets.token_urlsafe(32)}"
    csrf_token = secrets.token_urlsafe(32)

    server = LocalConfirmationPageServer(
        host=host,
        port=port,
        draft=draft,
        channel_id=channel_id,
        secret_path=secret_path,
        csrf_token=csrf_token,
        account_name=account_name,
    )

    try:
        url = server.confirmation_url
        if browser_opener is not None:
            browser_opener(url)
        else:
            logger.info("Open this URL in your browser to confirm playlist creation: %s", url)

        decision = await anyio.to_thread.run_sync(server.wait_for_decision, timeout_seconds)
    finally:
        server.server_close()

    if decision is ConfirmationDecision.ACCEPT:
        return token_store.mint_for_draft(draft, channel_id, decision=ConfirmationDecision.ACCEPT)

    token_store.mint_for_draft(draft, channel_id, decision=ConfirmationDecision.DECLINE)
    raise ToolError(
        ErrorCode.CONFIRMATION_DECLINED,
        f"Playlist creation confirmation for draft {draft.draft_id!r} was declined or timed out.",
        details={"draft_id": draft.draft_id, "decision": decision.value},
    )
