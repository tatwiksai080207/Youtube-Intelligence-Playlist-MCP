"""Formatting helpers for trusted confirmation summaries (FR-5.4, INV-13, INV-22)."""

from __future__ import annotations

import html

from yt_intel_mcp.durations import format_duration
from yt_intel_mcp.playlist.drafts import PlaylistDraft
from yt_intel_mcp.sanitize import escape_html, sanitize_single_line

__all__ = [
    "format_confirmation_summary_html",
    "format_confirmation_summary_text",
]


def format_confirmation_summary_text(
    draft: PlaylistDraft,
    channel_id: str,
    *,
    account_name: str | None = None,
) -> str:
    """Format a clear, sanitized text summary for MCP elicitation dialogs (INV-13, INV-22)."""
    clean_channel = sanitize_single_line(channel_id, max_length=100) or channel_id
    account_display = f"{account_name} ({clean_channel})" if account_name else clean_channel
    min_human = format_duration(draft.target_min_seconds)
    max_human = format_duration(draft.target_max_seconds)

    lines: list[str] = [
        "YouTube Curated Playlist Confirmation",
        "=" * 38,
        f"Target Account: {account_display}",
        f"Playlist Title: {draft.title}",
        f"Privacy Status: {draft.privacy_status}",
        (
            f"Total Duration: {draft.total_duration_human} "
            f"(target window: {min_human} - {max_human})"
        ),
        f"Draft Expiration: {draft.expires_at_utc.isoformat()}",
        f"Selected Videos: {len(draft.videos)} items",
        "",
        "Ordered Video Items:",
    ]

    for idx, video in enumerate(draft.videos, start=1):
        lines.append(
            f"  {idx}. {video.title} | {video.channel_title} | "
            f"{video.duration_human} [{video.audio_language_label}]"
        )

    lines.extend(
        [
            "",
            "Please review the above playlist details. "
            "Approving authorizes creating this playlist in your YouTube library.",
        ]
    )
    return "\n".join(lines)


def format_confirmation_summary_html(
    draft: PlaylistDraft,
    channel_id: str,
    *,
    csrf_token: str,
    secret_path: str,
    account_name: str | None = None,
) -> str:
    """Format a sanitized, secure HTML page for the 127.0.0.1 loopback confirmation (SRS §3.3)."""
    clean_channel = escape_html(channel_id, max_length=100)
    clean_account = escape_html(account_name, max_length=100) if account_name else ""
    account_display = f"{clean_account} ({clean_channel})" if clean_account else clean_channel
    clean_title = escape_html(draft.title, max_length=200)
    clean_privacy = escape_html(draft.privacy_status, max_length=20)
    clean_duration = escape_html(draft.total_duration_human, max_length=30)
    min_human = escape_html(format_duration(draft.target_min_seconds), max_length=30)
    max_human = escape_html(format_duration(draft.target_max_seconds), max_length=30)
    clean_expiry = escape_html(draft.expires_at_utc.isoformat(), max_length=40)
    safe_path = html.escape(secret_path, quote=True)
    safe_csrf = html.escape(csrf_token, quote=True)

    rows: list[str] = []
    for idx, video in enumerate(draft.videos, start=1):
        v_title = escape_html(video.title, max_length=200)
        v_channel = escape_html(video.channel_title, max_length=100)
        v_dur = escape_html(video.duration_human, max_length=30)
        v_lang = escape_html(video.audio_language_label, max_length=50)
        rows.append(
            f"      <tr>\n"
            f"        <td>{idx}</td>\n"
            f"        <td><strong>{v_title}</strong><br><small>{v_channel}</small></td>\n"
            f"        <td>{v_dur}</td>\n"
            f"        <td>{v_lang}</td>\n"
            f"      </tr>"
        )
    video_rows = "\n".join(rows)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'\">\n"
        "  <title>Confirm Playlist Creation - YouTube Video Intelligence</title>\n"
        "  <style>\n"
        "    body { font-family: -apple-system, BlinkMacSystemFont, "
        '"Segoe UI", Roboto, sans-serif; '
        "margin: 24px; line-height: 1.5; color: #1f2937; background: #f9fafb; }\n"
        "    .container { max-width: 800px; margin: 0 auto; background: #ffffff; padding: 24px; "
        "border-radius: 8px; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }\n"
        "    h1 { font-size: 20px; margin-top: 0; color: #111827; "
        "border-bottom: 2px solid #e5e7eb; padding-bottom: 12px; }\n"
        "    .meta-grid { display: grid; grid-template-columns: 160px 1fr; "
        "gap: 8px 16px; margin: 16px 0; font-size: 14px; }\n"
        "    .meta-label { font-weight: 600; color: #4b5563; }\n"
        "    table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; }\n"
        "    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; }\n"
        "    th { background: #f3f4f6; color: #374151; font-weight: 600; }\n"
        "    .actions { margin-top: 24px; display: flex; gap: 12px; }\n"
        "    button { padding: 10px 24px; font-size: 14px; font-weight: 600; border-radius: 6px; "
        "border: none; cursor: pointer; }\n"
        "    .btn-accept { background: #059669; color: #ffffff; }\n"
        "    .btn-accept:hover { background: #047857; }\n"
        "    .btn-decline { background: #dc2626; color: #ffffff; }\n"
        "    .btn-decline:hover { background: #b91c1c; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <div class="container">\n'
        "    <h1>YouTube Curated Playlist Confirmation</h1>\n"
        '    <div class="meta-grid">\n'
        '      <div class="meta-label">Target Account:</div><div>' + account_display + "</div>\n"
        '      <div class="meta-label">Playlist Title:</div><div><strong>'
        + clean_title
        + "</strong></div>\n"
        '      <div class="meta-label">Privacy:</div><div>' + clean_privacy + "</div>\n"
        '      <div class="meta-label">Total Duration:</div><div>'
        + clean_duration
        + " (target: "
        + min_human
        + " - "
        + max_human
        + ")</div>\n"
        '      <div class="meta-label">Draft Expires:</div><div>' + clean_expiry + "</div>\n"
        '      <div class="meta-label">Item Count:</div><div>'
        + str(len(draft.videos))
        + " videos</div>\n"
        "    </div>\n"
        "    <table>\n"
        "      <thead>\n"
        "        <tr>\n"
        '          <th style="width: 40px;">#</th>\n'
        "          <th>Video Title & Channel</th>\n"
        '          <th style="width: 90px;">Duration</th>\n'
        '          <th style="width: 140px;">Audio Language</th>\n'
        "        </tr>\n"
        "      </thead>\n"
        "      <tbody>\n" + video_rows + "\n      </tbody>\n"
        "    </table>\n"
        '    <form method="POST" action="' + safe_path + '">\n'
        '      <input type="hidden" name="csrf_token" value="' + safe_csrf + '">\n'
        '      <div class="actions">\n'
        '        <button type="submit" name="action" value="accept" class="btn-accept">'
        "Approve Playlist Creation</button>\n"
        '        <button type="submit" name="action" value="decline" class="btn-decline">'
        "Decline</button>\n"
        "      </div>\n"
        "    </form>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )
