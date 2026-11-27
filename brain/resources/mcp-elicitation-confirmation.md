---
title: Trusted Playlist Confirmation with MCP Elicitation
type: reference
status: distilled
authors:
  - Mohammed Farhan
created: 2026-11-25
updated: 2026-11-27
tags:
  - mcp
  - playlist
  - confirmation
requirements:
  - FR-5.3
  - FR-5.4
  - NFR-6
  - SB-1
  - SB-6
issues:
  - "#7"
  - "#19"
  - "#70"
  - "#72"
prs:
  - "#17"
  - "#20"
  - "#71"
  - "#73"
sources:
  - "Final_SRS_Submission.pdf v1.0, sections 3.3 and 4.5 (checked 2026-11-25)"
  - "MCP specification 2025-06-18, Elicitation: https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation (checked 2026-11-25)"
---

# Trusted Playlist Confirmation with MCP Elicitation

## Summary

`create_curated_playlist` accepts a draft ID and requires the authenticated user's approval through a trusted UI before any YouTube write. FR-5.4 permits an MCP elicitation dialog or a one-time server page bound to `127.0.0.1`.

## Trusted channels

- **MCP dialog.** The MCP specification cited by the SRS requires the client to advertise `elicitation` at initialization. A supporting host presents the server's `elicitation/create` request to the user and returns an explicit accept, decline, or cancel result. Only affirmative approval of the displayed draft authorizes token issuance. The dialog asks for a decision and requires no credentials.
- **Loopback page.** If elicitation is unavailable, the user can accept or decline on the one-time server confirmation page in their browser. The server binds it strictly to `127.0.0.1`. If neither trusted channel is available, return `CONFIRMATION_UNAVAILABLE` and block creation.
- Both channels show the authenticated account, playlist title, privacy, ordered video list, total duration, and expiry. The immutable draft expires after 10 minutes under FR-5.3.

## Approval and write checks

An explicit accept lets the server mint a single-use token bound to the channel ID, draft ID, ordered video IDs, title, privacy, and expiry. The server retains the token throughout the operation. It never sends the token to the model or accepts it as a tool argument. A decline or cancellation leaves the operation without approval.

Before dispatching any write, the server rejects an altered draft or binding with `CONFIRMATION_MISMATCH`, an expired draft with `DRAFT_EXPIRED`, a reused approval with `CONFIRMATION_REUSED`, and a declined approval with `CONFIRMATION_DECLINED`. Chat text, tool arguments, and video metadata cannot confer approval. The exact ordering of the remaining pre-write checks is tracked in G-02 for ADR-0004.

## Verification targets

- `NT_HITL` covers altered, expired, reused, and declined approvals and verifies that untrusted text cannot mint an approval.
- `NT_HITL_UNAVAIL` covers the absence of both trusted channels. `ST_FR5_CONFIRM` covers the successful trusted confirmation flow.

## Related notes

- [[brain/index|Second Brain Index]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
- [[brain/resources/mcp-protocol-specification|MCP Protocol Specification]]
- [[brain/projects/playlist-constraints|Playlist constraints]]
- [[brain/projects/partial-playlist-outcomes|Partial playlist outcomes]]
