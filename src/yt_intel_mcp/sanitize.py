"""Untrusted metadata sanitisation and HTML escaping helpers (MF-07, NFR-6, INV-22)."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import replace

from yt_intel_mcp.models import VideoMeta

__all__ = [
    "DEFAULT_MAX_DESCRIPTION_LENGTH",
    "DEFAULT_MAX_TAG_LENGTH",
    "DEFAULT_MAX_TITLE_LENGTH",
    "escape_html",
    "sanitize_single_line",
    "sanitize_text",
    "sanitize_video_meta",
]

DEFAULT_MAX_TITLE_LENGTH = 200
DEFAULT_MAX_DESCRIPTION_LENGTH = 1000
DEFAULT_MAX_TAG_LENGTH = 100

_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_MARKDOWN_REF_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*\S+.*$", re.MULTILINE)
_MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\((?:[^()]*|\([^()]*\))*\)")
_ANGLE_URL_RE = re.compile(
    r"<\s*(?:https?|ftp|file|javascript|data|vbscript|mailto):[^>]+>",
    re.IGNORECASE,
)
_RAW_URL_RE = re.compile(
    r"\b(?:https?|ftp|file|javascript|data|vbscript|mailto):[^\s<>()\[\]]+",
    re.IGNORECASE,
)
_WWW_URL_RE = re.compile(
    r"\bwww\.[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s<>()\[\]]*)?",
    re.IGNORECASE,
)
_EXTRA_INVISIBLE_CHARS = frozenset({"\u034f", "\u180e", "\u115f", "\u1160", "\u3164", "\uffa0"})
_DISALLOWED_UNICODE_CATEGORIES = frozenset({"Cf", "Cc", "Cs", "Co"})


def _strip_invisible_and_control_chars(text: str) -> str:
    """Remove invisible, bidi, format, surrogate, private use, and control characters."""
    cleaned = _ANSI_OSC_RE.sub("", text)
    cleaned = _ANSI_CSI_RE.sub("", cleaned)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\u2028", "\n").replace("\u2029", "\n")

    chars: list[str] = []
    for ch in cleaned:
        if ch == "\n":
            chars.append(ch)
            continue
        if ch == "\t":
            chars.append(" ")
            continue
        if ch in _EXTRA_INVISIBLE_CHARS:
            continue
        if unicodedata.category(ch) in _DISALLOWED_UNICODE_CATEGORIES:
            continue
        chars.append(ch)
    return "".join(chars)


def _strip_links_and_urls(text: str) -> str:
    """Remove Markdown link targets, reference link definitions, and raw URLs."""
    cleaned = _MARKDOWN_REF_DEF_RE.sub("", text)
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = _ANGLE_URL_RE.sub("", cleaned)
    cleaned = _RAW_URL_RE.sub("", cleaned)
    return _WWW_URL_RE.sub("", cleaned)


def _normalize_multiline_whitespace(text: str) -> str:
    """Collapse horizontal whitespace per line while preserving paragraph structure."""
    lines = [" ".join(line.split()) for line in text.split("\n")]
    normalized_lines: list[str] = []
    blank_pending = False
    for line in lines:
        if not line:
            if normalized_lines:
                blank_pending = True
            continue
        if blank_pending:
            normalized_lines.append("")
            blank_pending = False
        normalized_lines.append(line)
    return "\n".join(normalized_lines).strip()


def sanitize_text(
    text: str,
    *,
    max_length: int = DEFAULT_MAX_DESCRIPTION_LENGTH,
) -> str:
    """Sanitize untrusted YouTube metadata text against prompt injection (NFR-6, INV-22)."""
    if max_length < 0:
        raise ValueError("max_length must be non-negative.")
    if max_length == 0 or not text:
        return ""

    cleaned = _strip_invisible_and_control_chars(text)
    cleaned = _strip_links_and_urls(cleaned)
    cleaned = _normalize_multiline_whitespace(cleaned)
    if len(cleaned) > max_length:
        return cleaned[:max_length].rstrip()
    return cleaned


def sanitize_single_line(
    text: str,
    *,
    max_length: int = DEFAULT_MAX_TITLE_LENGTH,
) -> str:
    """Sanitize untrusted text and collapse all line breaks into single spaces."""
    cleaned = sanitize_text(text, max_length=max(max_length, len(text)))
    collapsed = " ".join(cleaned.split())
    if len(collapsed) > max_length:
        return collapsed[:max_length].rstrip()
    return collapsed


def escape_html(
    text: str,
    *,
    max_length: int = DEFAULT_MAX_DESCRIPTION_LENGTH,
) -> str:
    """Sanitize untrusted text and HTML-escape it for the 127.0.0.1 confirmation page."""
    sanitized = sanitize_text(text, max_length=max_length)
    return html.escape(sanitized, quote=True)


def sanitize_video_meta(video: VideoMeta) -> VideoMeta:
    """Return a VideoMeta instance with untrusted text fields sanitized (NFR-6, INV-22)."""
    clean_tags = tuple(
        cleaned
        for tag in video.tags
        if (cleaned := sanitize_single_line(tag, max_length=DEFAULT_MAX_TAG_LENGTH))
    )
    return replace(
        video,
        title=sanitize_single_line(video.title, max_length=DEFAULT_MAX_TITLE_LENGTH),
        description=sanitize_text(video.description, max_length=DEFAULT_MAX_DESCRIPTION_LENGTH),
        channel_title=sanitize_single_line(
            video.channel_title, max_length=DEFAULT_MAX_TITLE_LENGTH
        ),
        tags=clean_tags,
    )
