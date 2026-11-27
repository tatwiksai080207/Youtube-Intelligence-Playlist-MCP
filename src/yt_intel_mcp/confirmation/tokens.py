"""Single use server held confirmation tokens bound to playlist drafts (MF-12, FR-5.4, INV-14)."""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.playlist.drafts import PlaylistDraft

__all__ = [
    "CONFIRMATION_TOKEN_ID_RE",
    "ConfirmationDecision",
    "ConfirmationToken",
    "ConfirmationTokenStore",
]

CONFIRMATION_TOKEN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ConfirmationDecision(StrEnum):
    """Explicit human in the loop confirmation decision (FR-5.4, INV-13, INV-14)."""

    ACCEPT = "accept"
    DECLINE = "decline"
    CANCEL = "cancel"


@dataclass(slots=True)
class ConfirmationToken:
    """Server side confirmation token bound to an immutable draft and user channel.

    Enforces strict binding invariants under FR-5.4 and INV-14.
    """

    token_id: str
    channel_id: str
    draft_id: str
    ordered_video_ids: tuple[str, ...]
    title: str
    privacy_status: Literal["private", "unlisted", "public"] | str
    expires_at_utc: datetime
    decision: ConfirmationDecision
    created_at_utc: datetime
    consumed: bool = False
    consumed_at_utc: datetime | None = None

    def __repr__(self) -> str:
        """Never expose secret token id in debug representations (INV-14)."""
        return (
            f"<ConfirmationToken draft_id={self.draft_id!r} "
            f"channel_id={self.channel_id!r} decision={self.decision.value!r} "
            f"consumed={self.consumed}>"
        )

    def __str__(self) -> str:
        """Never expose secret token id in string conversion (INV-14)."""
        return self.__repr__()

    @property
    def is_accepted(self) -> bool:
        """Return True if decision was affirmative approval."""
        return self.decision is ConfirmationDecision.ACCEPT

    def is_expired(self, now_utc: datetime | None = None) -> bool:
        """Return True if the token expiration threshold has elapsed."""
        now = _ensure_utc(now_utc) if now_utc is not None else datetime.now(UTC)
        return now >= self.expires_at_utc

    def to_safe_dict(self) -> dict[str, Any]:
        """Return audit view without secret token id (never returned to LLM)."""
        return {
            "channel_id": self.channel_id,
            "draft_id": self.draft_id,
            "video_count": len(self.ordered_video_ids),
            "ordered_video_ids": list(self.ordered_video_ids),
            "title": self.title,
            "privacy_status": self.privacy_status,
            "decision": self.decision.value,
            "consumed": self.consumed,
            "created_at_utc": self.created_at_utc.isoformat(),
            "expires_at_utc": self.expires_at_utc.isoformat(),
            "consumed_at_utc": self.consumed_at_utc.isoformat() if self.consumed_at_utc else None,
        }


class ConfirmationTokenStore:
    """Server side store managing single use draft bound confirmation tokens (FR-5.4, INV-14)."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))
        self._tokens_by_draft: dict[str, ConfirmationToken] = {}
        self._tokens_by_id: dict[str, ConfirmationToken] = {}

    def _now_utc(self) -> datetime:
        return _ensure_utc(self._clock())

    def mint(
        self,
        *,
        channel_id: str,
        draft_id: str,
        ordered_video_ids: Sequence[str],
        title: str,
        privacy_status: Literal["private", "unlisted", "public"] | str,
        expires_at_utc: datetime,
        decision: ConfirmationDecision | str = ConfirmationDecision.ACCEPT,
    ) -> ConfirmationToken:
        """Mint a server side single use confirmation token bound to draft parameters."""
        if not isinstance(channel_id, str) or not channel_id.strip():
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "Parameter 'channel_id' must be a non empty string.",
                details={"field": "channel_id"},
            )
        if not isinstance(draft_id, str) or not draft_id.strip():
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "Parameter 'draft_id' must be a non empty string.",
                details={"field": "draft_id"},
            )
        if not isinstance(title, str):
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "Parameter 'title' must be a string.",
                details={"field": "title"},
            )
        if not isinstance(privacy_status, str) or not privacy_status.strip():
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "Parameter 'privacy_status' must be a non empty string.",
                details={"field": "privacy_status"},
            )

        parsed_decision: ConfirmationDecision
        if isinstance(decision, ConfirmationDecision):
            parsed_decision = decision
        else:
            try:
                parsed_decision = ConfirmationDecision(str(decision).strip().lower())
            except ValueError as exc:
                raise ToolError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"Invalid confirmation decision {decision!r}.",
                    details={"field": "decision"},
                ) from exc

        now = self._now_utc()
        utc_expiry = _ensure_utc(expires_at_utc)
        clean_channel_id = channel_id.strip()
        clean_draft_id = draft_id.strip()
        immutable_videos = tuple(str(vid) for vid in ordered_video_ids)

        token_id = f"tok_{secrets.token_urlsafe(32)}"
        while token_id in self._tokens_by_id:  # pragma: no cover
            token_id = f"tok_{secrets.token_urlsafe(32)}"

        token = ConfirmationToken(
            token_id=token_id,
            channel_id=clean_channel_id,
            draft_id=clean_draft_id,
            ordered_video_ids=immutable_videos,
            title=title,
            privacy_status=privacy_status,
            expires_at_utc=utc_expiry,
            decision=parsed_decision,
            created_at_utc=now,
        )

        self._tokens_by_id[token_id] = token
        self._tokens_by_draft[clean_draft_id] = token
        return token

    def mint_for_draft(
        self,
        draft: PlaylistDraft,
        channel_id: str,
        *,
        decision: ConfirmationDecision | str = ConfirmationDecision.ACCEPT,
    ) -> ConfirmationToken:
        """Mint a single use confirmation token bound directly to a PlaylistDraft instance."""
        if not isinstance(draft, PlaylistDraft):
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "Expected a PlaylistDraft instance to bind confirmation token.",
                details={"field": "draft"},
            )
        return self.mint(
            channel_id=channel_id,
            draft_id=draft.draft_id,
            ordered_video_ids=draft.ordered_video_ids,
            title=draft.title,
            privacy_status=draft.privacy_status,
            expires_at_utc=draft.expires_at_utc,
            decision=decision,
        )

    def get_for_draft(self, draft_id: object) -> ConfirmationToken | None:
        """Look up the most recent confirmation token bound to the given draft id."""
        if not isinstance(draft_id, str):
            return None
        return self._tokens_by_draft.get(draft_id.strip())

    def get(self, token_id: object) -> ConfirmationToken | None:
        """Look up a confirmation token by its internal server token id."""
        if not isinstance(token_id, str):
            return None
        return self._tokens_by_id.get(token_id.strip())

    def consume(
        self,
        token: ConfirmationToken,
        *,
        draft: PlaylistDraft,
        channel_id: str,
        now_utc: datetime | None = None,
    ) -> ConfirmationToken:
        """Verify strict invariants and consume a single use token (FR-5.4, INV-14)."""
        if not isinstance(token, ConfirmationToken) or token.token_id not in self._tokens_by_id:
            raise ToolError(
                ErrorCode.CONFIRMATION_MISMATCH,
                "Unknown or invalid confirmation token.",
                details={"draft_id": getattr(draft, "draft_id", "unknown")},
            )

        if not isinstance(draft, PlaylistDraft):
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "Parameter 'draft' must be a PlaylistDraft instance.",
                details={"field": "draft"},
            )

        now = _ensure_utc(now_utc if now_utc is not None else self._now_utc())

        if token.decision in (ConfirmationDecision.DECLINE, ConfirmationDecision.CANCEL):
            raise ToolError(
                ErrorCode.CONFIRMATION_DECLINED,
                f"Playlist creation confirmation for draft {token.draft_id!r} was declined.",
                details={"draft_id": token.draft_id, "decision": token.decision.value},
            )

        if token.consumed:
            raise ToolError(
                ErrorCode.CONFIRMATION_REUSED,
                f"Confirmation token for draft {token.draft_id!r} has already been consumed.",
                details={"draft_id": token.draft_id},
            )

        if token.is_expired(now) or draft.is_expired(now):
            raise ToolError(
                ErrorCode.DRAFT_EXPIRED,
                (
                    f"Confirmation token for draft {token.draft_id!r} expired at "
                    f"{token.expires_at_utc.isoformat()}."
                ),
                details={
                    "draft_id": token.draft_id,
                    "expires_at_utc": token.expires_at_utc.isoformat(),
                },
            )

        clean_channel_id = channel_id.strip() if isinstance(channel_id, str) else ""
        if token.channel_id != clean_channel_id:
            raise ToolError(
                ErrorCode.CONFIRMATION_MISMATCH,
                "Authenticated channel ID does not match confirmation binding.",
                details={"field": "channel_id", "draft_id": token.draft_id},
            )

        if token.draft_id != draft.draft_id:
            raise ToolError(
                ErrorCode.CONFIRMATION_MISMATCH,
                "Draft ID does not match confirmation binding.",
                details={"field": "draft_id", "draft_id": token.draft_id},
            )

        if token.ordered_video_ids != draft.ordered_video_ids:
            raise ToolError(
                ErrorCode.CONFIRMATION_MISMATCH,
                "Ordered video IDs do not match confirmation binding.",
                details={"field": "ordered_video_ids", "draft_id": token.draft_id},
            )

        if token.title != draft.title:
            raise ToolError(
                ErrorCode.CONFIRMATION_MISMATCH,
                "Playlist title does not match confirmation binding.",
                details={"field": "title", "draft_id": token.draft_id},
            )

        if token.privacy_status != draft.privacy_status:
            raise ToolError(
                ErrorCode.CONFIRMATION_MISMATCH,
                "Playlist privacy status does not match confirmation binding.",
                details={"field": "privacy_status", "draft_id": token.draft_id},
            )

        if token.expires_at_utc != draft.expires_at_utc:
            raise ToolError(
                ErrorCode.CONFIRMATION_MISMATCH,
                "Draft expiry timestamp does not match confirmation binding.",
                details={"field": "expires_at_utc", "draft_id": token.draft_id},
            )

        token.consumed = True
        token.consumed_at_utc = now
        return token

    def consume_for_draft(
        self,
        draft_id: object,
        *,
        draft: PlaylistDraft,
        channel_id: str,
        now_utc: datetime | None = None,
    ) -> ConfirmationToken:
        """Look up the confirmation token for draft id, verify invariants, and consume it."""
        if not isinstance(draft_id, str):
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                "Parameter 'draft_id' must be a string.",
                details={"field": "draft_id"},
            )
        clean_id = draft_id.strip()
        token = self.get_for_draft(clean_id)
        if token is None:
            raise ToolError(
                ErrorCode.CONFIRMATION_MISMATCH,
                f"No confirmation token found for playlist draft {clean_id!r}.",
                details={"field": "draft_id", "draft_id": clean_id},
            )
        return self.consume(token, draft=draft, channel_id=channel_id, now_utc=now_utc)

    def purge_expired(self, now_utc: datetime | None = None) -> int:
        """Delete expired confirmation tokens from memory and return the count removed."""
        now = _ensure_utc(now_utc if now_utc is not None else self._now_utc())
        expired_ids = [tid for tid, tok in self._tokens_by_id.items() if tok.is_expired(now)]
        for tid in expired_ids:
            tok = self._tokens_by_id.pop(tid)
            if self._tokens_by_draft.get(tok.draft_id) is tok:
                self._tokens_by_draft.pop(tok.draft_id, None)
        return len(expired_ids)

    def list_active_draft_ids(self, now_utc: datetime | None = None) -> tuple[str, ...]:
        """Return tuple of draft IDs with active unexpired unconsumed approval tokens."""
        now = _ensure_utc(now_utc if now_utc is not None else self._now_utc())
        active: list[str] = []
        for did, tok in self._tokens_by_draft.items():
            if tok.is_accepted and not tok.consumed and not tok.is_expired(now):
                active.append(did)
        return tuple(active)

    def clear(self) -> None:
        """Clear all stored confirmation tokens."""
        self._tokens_by_draft.clear()
        self._tokens_by_id.clear()
