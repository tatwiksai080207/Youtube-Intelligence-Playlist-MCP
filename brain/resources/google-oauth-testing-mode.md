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
  - security
  - authentication
  - tokens
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
  - "#5"
prs:
  - "#10"
sources:
  - "Google OAuth 2.0 for Mobile & Desktop Apps: https://developers.google.com/identity/protocols/oauth2/native-app (checked 2026-11-25)"
  - "Using OAuth 2.0 to Access Google APIs (Token Expiration): https://developers.google.com/identity/protocols/oauth2 (checked 2026-11-25)"
  - "YouTube Data API v3 playlists.insert Reference: https://developers.google.com/youtube/v3/docs/playlists/insert (checked 2026-11-25)"
  - "Final_SRS_Submission.pdf Section 2.4, 3.3, 4.7, 5 (checked 2026-11-25)"
---

# Google OAuth Lifecycle in Testing Publishing Status

## Summary
Google Cloud OAuth applications kept in **Testing** publishing status (`C-4`) enforce strict operational limits, most notably a 7-day lifetime on refresh tokens for sensitive/restricted scopes such as YouTube Data API access. `yt-intel-mcp` uses Authorization Code flow with PKCE over a `127.0.0.1` loopback redirect, stores tokens encrypted at rest (`FR-7.2`), separates read and write consents (`C-6`, `C-7`), and handles expired tokens and missing channels cleanly (`FR-7.3`).

## Key Operational Constraints
1. **Seven-Day Refresh Token Lifetime (`C-4`):** In Testing status, OAuth refresh tokens expire 7 days after issuance. Expired tokens fail with `invalid_grant` from Google's token endpoint and require explicit user re-authorisation (`AUTH_REAUTHORIZATION_REQUIRED`).
2. **Authorised Test Users Only:** Only Google accounts registered on the OAuth consent screen test user list (up to 100 accounts) can authorise the application (`SRS Section 2.4` assumption).
3. **Authorization Code Flow with PKCE (`SRS Section 3.3`):** Desktop/installed clients cannot protect a confidential secret and must use RFC 7636 PKCE (`S256` code challenge) with a local loopback redirect (`http://127.0.0.1:<port>/callback`).
4. **Least-Privilege Scopes and No Incremental Authorisation (`C-6`, `C-7`, `FR-7.1`):**
   - Initial read login requests only `https://www.googleapis.com/auth/youtube.readonly`.
   - Google does not support incremental authorisation for installed apps (`C-7`). When a user first creates a playlist, the server runs a separate full consent request for `https://www.googleapis.com/auth/youtube.force-ssl` (accepted by `playlists.insert`); without it, creation fails with `SCOPE_INSUFFICIENT`.
5. **Channel Requirement (`C-5`, `FR-7.3`):** A Google account without a YouTube channel triggers `youtubeSignupRequired` on write attempts; creation returns `CHANNEL_REQUIRED` with setup guidance while read tools keep working.

## Architectural Mitigations
- **Encrypted Storage (`FR-7.2`, `NFR-3`):** Store tokens in the OS keyring or an `AES-256-GCM` encrypted file; never log tokens or return them in MCP tool responses.
- **Silent Refresh & Expiry Visibility:** Refresh expired access tokens silently; map `invalid_grant` to `AUTH_REAUTHORIZATION_REQUIRED` (optionally surfacing an early re-auth warning as day 7 approaches).
- **Privacy Purge (`NFR-7`):** Delete stored tokens and locally cached personal data upon auth revocation.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/inbox/oauth-scopes-and-token-storage|OAuth Scopes, PKCE and Encrypted Token Storage]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
- [[brain/resources/youtube-quota-costs|YouTube Quota Costs]]
- [[brain/areas/second-brain|Second Brain Architecture]]
