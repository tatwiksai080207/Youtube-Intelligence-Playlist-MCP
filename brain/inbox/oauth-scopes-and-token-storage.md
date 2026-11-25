---
title: OAuth Scopes, PKCE and Encrypted Token Storage
type: reference
status: inbox
authors:
  - Madire Shiva Reddy
created: 2026-11-25
updated: 2026-11-25
tags:
  - oauth
  - pkce
  - security
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
  - "#5"
prs:
  - "#15"
sources:
  - "Final_SRS_Submission.pdf Section 2.4, 3.3, 4.7, 5 (checked 2026-11-25)"
  - "Google OAuth 2.0 for Mobile & Desktop Apps: https://developers.google.com/identity/protocols/oauth2/native-app (checked 2026-11-25)"
  - "Using OAuth 2.0 to Access Google APIs (Token Expiration): https://developers.google.com/identity/protocols/oauth2 (checked 2026-11-25)"
  - "YouTube Data API v3 playlists.insert Reference: https://developers.google.com/youtube/v3/docs/playlists/insert (checked 2026-11-25)"
---

# OAuth Scopes, PKCE and Encrypted Token Storage

## Summary
`yt-intel-mcp` acts as a local installed desktop client using OAuth 2.0 Authorization Code flow with PKCE (`S256`) and a loopback redirect (`127.0.0.1`). Because Google does not support incremental authorisation for installed apps (`C-7`), read-only access and playlist-write access use two separate consent flows enforcing strict least privilege (`C-6`, `FR-7.1`), with tokens persisted encrypted at rest (`FR-7.2`, `NFR-3`).

## Least-Privilege Scopes and Separate Write Consent (`C-6`, `C-7`, `FR-7.1`)
1. **Initial Read-Only Login:** Standard sign-in requests `https://www.googleapis.com/auth/youtube.readonly` only. This suffices for `get_video_details`, `get_similar_videos`, `get_similar_channels`, `get_recommendations`, and `analyze_engagement`.
2. **No Incremental Authorisation (`C-7`):** Google's OAuth 2.0 documentation for installed/desktop apps explicitly states that incremental authorisation (`include_granted_scopes`) is not supported for public installed clients.
3. **Separate Full Consent for Playlist Creation:** Per YouTube Data API v3 documentation, `playlists.insert` accepts `https://www.googleapis.com/auth/youtube.force-ssl` (or broader `youtube` scope). To preserve least privilege (`C-6`), the server requests `youtube.force-ssl` only via a separate full consent request when the user first creates a playlist (`FR-7.1`). Without write consent, `create_curated_playlist` fails with `SCOPE_INSUFFICIENT`.

## PKCE Loopback Flow and Token Lifecycle (`FR-7.2`, `C-4`, `NFR-3`)
- **Authorization Code + PKCE:** The client generates a high-entropy `code_verifier` and `S256` `code_challenge`, binds an ephemeral HTTP callback listener strictly on `http://127.0.0.1:<port>/callback` (`SRS Section 3.3`), and opens Google's consent URL in the user's desktop browser.
- **Encrypted Storage at Rest:** Access and refresh tokens are stored in the OS keyring when available, falling back to an `AES-256-GCM` encrypted local file (`FR-7.2`, detailed in `ADR-0006`). Tokens are never written to logs (`stderr`/`stdout`) or returned by any MCP tool (`get_auth_status` returns granted scopes, token state, and channel flag only).
- **Silent Refresh and 7-Day Expiry (`C-4`):** Expired access tokens are refreshed silently. Because the OAuth consent screen remains in Testing publishing status, refresh tokens expire after 7 days; an `invalid_grant` response from Google's token endpoint maps cleanly to `AUTH_REAUTHORIZATION_REQUIRED`.
- **Revoke Purge (`NFR-7`):** Revoking authentication deletes stored OAuth tokens as well as any locally cached personal user lists (liked videos, subscriptions, user playlists).

## Channel Presence Guard (`C-5`, `FR-7.3`)
- A Google account without an associated YouTube channel cannot create playlists and triggers `youtubeSignupRequired`.
- `create_curated_playlist` maps this condition to `CHANNEL_REQUIRED` with clear guidance to create a YouTube channel, while all read-only discovery and metadata tools continue working normally.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/second-brain|Second Brain Architecture]]
- [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle in Testing Publishing Status]]
- [[brain/inbox/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
- [[brain/resources/mcp-protocol-specification|Model Context Protocol Architecture and Primitives]]
