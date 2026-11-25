---
title: Google OAuth Lifecycle in Testing Publishing Status
type: reference
status: distilled
authors:
  - Molleti Tatwik Sai
created: 2026-11-09
updated: 2026-11-23
tags:
  - oauth
  - security
  - authentication
  - tokens
requirements:
  - FR-7
  - FR-7.1
  - FR-7.2
  - C-4
  - C-6
  - NFR-3
issues:
  - "#1"
prs:
  - "#10"
sources:
  - "Google OAuth 2.0 Documentation (checked 2026-11-12)"
  - "Final_SRS_Submission.pdf Section 2.4 and 4.7 (checked 2026-11-12)"
---

# Google OAuth Lifecycle in Testing Publishing Status

## Summary
Google Cloud OAuth applications in Testing publishing status have critical operational restrictions. Most notably, refresh tokens expire after exactly seven days. The server must handle token expiration gracefully, support silent token refreshes, and alert users before expiration.

## Key Operational Constraints
1. **Seven Day Token Lifetime**: In Testing mode, OAuth refresh tokens expire seven days from issuance. Once expired, calls return `invalid_grant` and require explicit user reauthorization.
2. **Authorized Test Users Only**: Only Google accounts explicitly added to the OAuth consent screen test user list can authorize the application. Up to 100 test users are allowed.
3. **Authorization Code Flow with PKCE**: For desktop and local applications, RFC 7636 Proof Key for Code Exchange (PKCE) with S256 code challenge must be used over loopback redirect (`http://127.0.0.1:<port>/callback`).
4. **Least Privilege Scopes**:
   - Initial read operations request only `https://www.googleapis.com/auth/youtube.readonly`.
   - Playlist write operations require separate consent for `https://www.googleapis.com/auth/youtube.force-ssl`.

## Architectural Mitigations
- The server records the refresh token creation timestamp.
- On day 6 of token validity, the server sets a warning flag indicating that reauthorization will soon be required.
- If an access token expires, the server attempts a silent refresh. If `invalid_grant` is received, it returns error code `AUTH_REAUTHORIZATION_REQUIRED` with instructions for running the authentication login command.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
- [[brain/resources/youtube-quota-costs|YouTube Quota Costs]]
- [[brain/areas/second-brain|Second Brain Architecture]]
