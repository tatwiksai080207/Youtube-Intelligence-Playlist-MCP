---
title: Non-Functional Requirements Targets and Error Mapping
type: reference
status: inbox
authors:
  - Madire Shiva Reddy
created: 2026-11-25
updated: 2026-11-25
tags:
  - nfr
  - performance
  - security
  - reliability
  - error-handling
requirements:
  - NFR-1
  - NFR-2
  - NFR-3
  - NFR-4
  - NFR-5
  - NFR-6
  - NFR-7
  - NFR-8
  - NFR-9
  - NFR-10
  - C-2
  - C-6
  - FR-5.4
  - FR-5.5
  - FR-6.2
  - SE-6
  - SB-1
  - SB-6
issues:
  - "#5"
prs: []
sources:
  - "Final_SRS_Submission.pdf Section 5 (checked 2026-11-25)"
  - "Final_SRS_Submission.pdf Section 3.2, 4.5, 4.6, 4.7, 6.1 (checked 2026-11-25)"
---

# Non-Functional Requirements Targets and Error Mapping

## Summary
This note records the binding quantitative targets, security controls, reliability rules, and upstream-to-MCP error code mappings specified in `Final_SRS_Submission.pdf` Section 5 (`NFR-1` through `NFR-10`). Every runtime component and verification test suite enforces these boundaries alongside the `YouTubeProvider` isolation contract.

## Quantitative Performance, Quota, and Quality Targets

| ID | Category | Binding SRS v1.0 Target | Primary Verification |
|---|---|---|---|
| `NFR-1` | Performance | Similarity scoring of 150 candidates `<= 150 ms`; playlist selection for 200 candidates `<= 500 ms`; cached tool responses `<= 500 ms` | `X_PERF_SCORE`, `X_PERF_SELECT`, `IT_CACHE` |
| `NFR-2` | Quota | Full `video-to-playlist` run (10 videos) `<= 600` units and `<= 4` `search.list` calls; PR CI uses `0` live quota; scheduled live tests `<= 300` units and `<= 10` search calls per run | `QT_1`–`QT_3`, `SK-1`, `TQ-5` |
| `NFR-3` | Security — OAuth | Minimum scopes only (`youtube.readonly` for reads, `youtube.force-ssl` for playlist writes per `C-6`); tokens encrypted at rest; never logged or returned in tool output | `SEC_OAUTH` |
| `NFR-4` | Security — Secrets | No secrets, tokens, or OAuth client files in the repository; secret scanning (`gitleaks`) on every PR | CI `gitleaks` gate |
| `NFR-5` | Security — Input Validation | Every tool parameter validated (ID formats, URL allow-list hosts, numeric/enum ranges) before use or quota spend | `UT_ID`, `NT_VAL` |
| `NFR-6` | Security — Prompt Injection | Untrusted titles/descriptions sanitised (Unicode NFKC normalisation, invisible/bidi chars and links removed, length-limited) and never able to trigger, satisfy, or bypass trusted confirmation (`FR-5.4`) | `NT_HITL` |
| `NFR-7` | Privacy | No real user data in fixtures or logs; personal data cached locally only and deleted on auth revoke | `SEC_PII`, `FR-4.3` |
| `NFR-8` | Reliability | Retry read requests on rate-limit and server errors with backoff (max 3 attempts); never auto-retry writes (`FR-5.5`); map API errors to deterministic MCP error codes | `IT_PROV`, `IT_DRAFT_PARTIAL` |
| `NFR-9` | Usability | Tool descriptions state purpose, side effects, and quota cost; outputs include human-readable durations | Schema/tool reference CI check |
| `NFR-10` | Maintainability | All YouTube access through `YouTubeProvider` (`SE-6`); `>= 85%` test coverage; `ruff` lint and strict `mypy` pass | CI suite & import-lint |

## Mandatory Upstream-to-MCP Error Mapping (`NFR-8`)
All YouTube Data API v3 and OAuth token endpoint errors caught inside the provider and auth layers map deterministically to the 17 frozen `ErrorCode` values:

| Upstream YouTube / OAuth Error | MCP Error Code Returned | Operational Behaviour |
|---|---|---|
| `quotaExceeded` | `QUOTA_EXHAUSTED_UPSTREAM` | Mark daily quota ledger exhausted until `00:00` Pacific Time reset (`FR-6.3`) |
| `rateLimitExceeded` / HTTP `429` | `RATE_LIMITED` | Retry read requests up to 3 times with exponential backoff; never retry writes |
| `videoNotFound`, private, or deleted video | `VIDEO_UNAVAILABLE` | During `FR-1`/`get_video_details` fail item/seed; during `FR-5.5` write, report item as `failed` and continue remaining items |
| `youtubeSignupRequired` | `CHANNEL_REQUIRED` | Block playlist creation with channel setup guidance while keeping read tools functional (`FR-7.3`) |
| `insufficientPermissions` | `SCOPE_INSUFFICIENT` | Require separate `youtube.force-ssl` consent before playlist creation (`FR-7.1`) |
| `invalid_grant` (OAuth token endpoint) | `AUTH_REAUTHORIZATION_REQUIRED` | Prompt user re-authorisation (common after 7-day Testing-mode refresh token expiry, `C-4`) |
| `forbidden` | `PERMISSION_DENIED` | Fail operation cleanly without retrying writes |

The complete 17-code vocabulary also includes domain and confirmation errors: `INVALID_ARGUMENT`, `INSUFFICIENT_USER_SIGNAL`, `CONSTRAINTS_UNSATISFIABLE`, `CONFIRMATION_MISMATCH`, `DRAFT_EXPIRED`, `CONFIRMATION_REUSED`, `CONFIRMATION_DECLINED`, `CONFIRMATION_UNAVAILABLE`, `DRAFT_STALE`, and `QUOTA_BUDGET_INSUFFICIENT`.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/second-brain|Second Brain Architecture]]
- [[brain/resources/youtube-quota-costs|YouTube Data API Quota Costs and Budgeting]]
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern and Dependency Inversion]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
- [[brain/inbox/oauth-scopes-and-token-storage|OAuth Scopes, PKCE and Encrypted Token Storage]]
