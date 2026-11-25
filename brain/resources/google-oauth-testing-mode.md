---
title: Google OAuth Lifecycle in Testing Publishing Status
type: reference
status: distilled
authors:
  - Molleti Tatwik Sai
  - Madire Shiva Reddy
created: 2026-11-09
updated: 2026-11-25
tags:
  - oauth
  - pkce
  - security
  - authentication
  - tokens
  - token-storage
  - youtube
requirements:
  - C-4
  - C-5
  - C-6
  - C-7
  - FR-7
  - FR-7.1
  - FR-7.2
  - FR-7.3
  - NFR-3
  - NFR-7
  - SB-1
  - SB-6
issues:
  - "#1"
  - "#3"
  - "#5"
  - "#19"
prs:
  - "#10"
  - "#13"
  - "#15"
sources:
  - "Google OAuth 2.0 for Mobile & Desktop Apps: https://developers.google.com/identity/protocols/oauth2/native-app (checked 2026-11-25)"
  - "Using OAuth 2.0 to Access Google APIs (Token Expiration): https://developers.google.com/identity/protocols/oauth2 (checked 2026-11-25)"
  - "YouTube Data API v3 playlists.insert Reference: https://developers.google.com/youtube/v3/docs/playlists/insert (checked 2026-11-25)"
  - "Final_SRS_Submission.pdf Section 2.4, 3.3, 4.7, 5 (checked 2026-11-25)"
---

# Google OAuth Lifecycle in Testing Publishing Status

## Summary
Google Cloud OAuth applications kept in **Testing** publishing status (`C-4`) enforce strict operational limits, most notably a 7 day lifetime on refresh tokens for sensitive and restricted scopes such as YouTube Data API access. `yt-intel-mcp` acts as an installed desktop client using OAuth 2.0 Authorization Code flow with PKCE (`S256`) over a `127.0.0.1` loopback redirect, stores tokens encrypted at rest (`FR-7.2`, `NFR-3`), separates read and write consents (`C-6`, `C-7`, `FR-7.1`), and handles expired tokens and missing channels cleanly (`FR-7.3`).

## Key Operational Constraints
1. **Seven Day Refresh Token Lifetime (`C-4`):** In Testing status, OAuth refresh tokens expire 7 days after issuance. Expired tokens fail with `invalid_grant` from Google's token endpoint and require explicit user re-authorisation (`AUTH_REAUTHORIZATION_REQUIRED`).
2. **Authorised Test Users Only:** Only Google accounts registered on the OAuth consent screen test user list (up to 100 accounts) can authorise the application (`SRS Section 2.4` assumption).
3. **Authorization Code Flow with PKCE (`SRS Section 3.3`):** Desktop and installed clients cannot protect a confidential secret and must generate a high entropy `code_verifier` with an `S256` `code_challenge` (RFC 7636), bind an ephemeral local HTTP callback listener strictly on `http://127.0.0.1:<port>/callback`, and open Google's consent URL in the user's desktop browser.
4. **Least Privilege Scopes and No Incremental Authorisation (`C-6`, `C-7`, `FR-7.1`):**
   - Initial read login requests only `https://www.googleapis.com/auth/youtube.readonly`. This suffices for `get_video_details`, `get_similar_videos`, `get_similar_channels`, `get_recommendations`, and `analyze_engagement`.
   - Google's OAuth 2.0 documentation for installed/desktop apps explicitly states that incremental authorisation (`include_granted_scopes`) is not supported for public installed clients (`C-7`). When a user first creates a playlist, the server runs a separate full consent request for `https://www.googleapis.com/auth/youtube.force-ssl` (accepted by `playlists.insert` alongside the broader `youtube` scope, with `youtube.force-ssl` preserving least privilege under `C-6`); without it, `create_curated_playlist` fails with `SCOPE_INSUFFICIENT`.
5. **Channel Presence Guard (`C-5`, `FR-7.3`):** A Google account without an associated YouTube channel triggers `youtubeSignupRequired` on write attempts; `create_curated_playlist` returns `CHANNEL_REQUIRED` with clear guidance to create a YouTube channel, while all read only discovery and metadata tools continue working normally.

## Architectural Mitigations
- **Encrypted Storage at Rest (`FR-7.2`, `NFR-3`):** Store access and refresh tokens in the OS keyring when available, falling back to an `AES-256-GCM` encrypted local file (detailed in `ADR-0006`). Never write tokens to `stderr`/`stdout` logs or return them in any MCP tool response (`get_auth_status` returns granted scopes, token state, and channel flag only).
- **Silent Refresh and Expiry Visibility:** Refresh expired access tokens silently; map `invalid_grant` to `AUTH_REAUTHORIZATION_REQUIRED` (optionally surfacing an early re-auth warning as day 7 approaches).
- **Privacy Purge (`NFR-7`):** Revoking authentication deletes stored OAuth tokens as well as any locally cached personal user lists (liked videos, subscriptions, and user playlists).

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
- [[brain/resources/mcp-protocol-specification|MCP Protocol Specification]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
- [[brain/resources/youtube-quota-costs|YouTube Quota Costs]]
- [[brain/areas/second-brain|Second Brain Architecture]]
