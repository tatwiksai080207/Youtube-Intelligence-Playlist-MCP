---
title: Prompt Injection Defense and Human in the Loop Gates
type: security
status: distilled
authors:
  - Molleti Tatwik Sai
  - Mohammed Farhan
created: 2026-11-09
updated: 2026-11-25
tags:
  - security
  - prompt-injection
  - hitl
  - authorization
requirements:
  - FR-5
  - FR-5.4
  - NFR-5
  - NFR-6
issues:
  - "#1"
  - "#7"
prs:
  - "#10"
sources:
  - "Final_SRS_Submission.pdf v1.0, sections 4.5 and 5 (checked 2026-11-25)"
  - "MCP specification 2025-06-18, Elicitation: https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation (checked 2026-11-25)"
---

# Prompt Injection Defense and Human in the Loop Gates

## Summary
Third-party video titles and descriptions are untrusted data. Metadata sanitization reduces what reaches the model and the confirmation page. The server grants approval only through the trusted paths in FR-5.4.

## Defensive Mechanisms
- **Sanitize metadata (NFR-6, INV-22).** Apply NFKC normalization to titles and descriptions, strip invisible and bidirectional control characters, remove links and URLs, and enforce length limits. Render metadata as text in the browser confirmation page.
- **Use a trusted confirmation channel (FR-5.4, INV-13).** A client that declares MCP elicitation can present the confirmation dialog. The fallback is a one-time server page bound strictly to `127.0.0.1`. The UI shows the authenticated account, title, privacy, ordered video list, total duration, and expiry. Return `CONFIRMATION_UNAVAILABLE` and block the write when neither channel is available.
- **Keep approval on the server (FR-5.4, INV-14).** Mint a single-use token only after the user's explicit acceptance. Bind it to the channel ID, draft ID, ordered video IDs, title, privacy, and expiry. Keep it on the server after approval as well. Reject mismatched, expired, reused, or declined approvals before dispatching a write.

## Invariant
Chat messages, tool arguments, and metadata cannot initiate or fulfill approval or bypass the confirmation checks. An MCP tool call can request creation for a draft ID, and the trusted UI collects the user's decision separately. `NT_HITL` and `NT_HITL_UNAVAIL` cover these failure cases.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/mcp-protocol-specification|MCP Protocol Specification]]
- [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle]]
- [[brain/areas/second-brain|Second Brain Architecture]]
- [[brain/inbox/mcp-elicitation-confirmation|Trusted Playlist Confirmation with MCP Elicitation]]
