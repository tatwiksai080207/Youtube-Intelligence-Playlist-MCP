---
title: Provider Interface Pattern and Dependency Inversion
type: architecture
status: distilled
authors:
  - Molleti Tatwik Sai
  - Madire Shiva Reddy
created: 2026-11-09
updated: 2026-11-25
tags:
  - architecture
  - testing
  - provider-pattern
  - dependency-inversion
requirements:
  - FR-8
  - FR-8.1
  - FR-8.2
  - SE-6
  - TQ-2
  - TQ-5
  - NFR-7
  - NFR-8
  - NFR-10
  - C-1
  - SB-1
  - SB-6
issues:
  - "#1"
  - "#5"
prs:
  - "#10"
  - "#15"
sources:
  - "Final_SRS_Submission.pdf Section 2.1, 2.4, 4.8, 5, 6.1 (checked 2026-11-25)"
  - "SDLC_and_Workflow.pdf Section 2 SE-6 (checked 2026-11-25)"
---

# Provider Interface Pattern and Dependency Inversion

## Summary
To decouple deterministic domain logic from external Google HTTP calls and guarantee zero-quota deterministic testing (`TQ-5`), all YouTube Data API v3 operations pass exclusively through the `YouTubeProvider` Protocol (`SE-6`, `FR-8.1`, `NFR-10`).

## Architecture
The hexagonal boundary isolates external network I/O behind one configuration-selected interface (`YT_INTEL_PROVIDER=fixture|live`):

```text
Domain / Application Layer (Similarity, Solver, Engagement, Quota Guard, Cache)
                                  │
                                  ▼
                    «Protocol» YouTubeProvider
                ┌─────────────────┴─────────────────┐
                ▼                                   ▼
       LiveYouTubeProvider                FixtureYouTubeProvider
   (Official YouTube Data API v3)     (Scrubbed Cassettes & Synthetic Mocks)
```

## Provider Responsibilities and Invariants
1. **LiveYouTubeProvider (`C-1`, `NFR-8`):**
   - Calls official YouTube Data API v3 HTTPS endpoints only; no scraping or unofficial APIs (`C-1`).
   - Strictly omits the `statistics` part (`FR-1.3`, `FR-2.2`) and exposes **no** update or delete playlist methods (`Section 1.2`).
   - Retries read operations up to 3 times with exponential backoff on `rateLimitExceeded` / HTTP `429` / server errors; **never** auto-retries write operations (`FR-5.5`, `NFR-8`).
   - Maps all upstream HTTP/API errors to the deterministic MCP error codes defined in `SRS Section 5`.
2. **FixtureYouTubeProvider (`FR-8.2`, `NFR-7`, `TQ-5`):**
   - Replays recorded public fixtures scrubbed of all tokens, credentials, and personal identifiers, alongside strictly synthetic user-data fixtures (`FR-8.2`).
   - Supports fault injection (rate limits, `quotaExceeded`, `youtubeSignupRequired`, partial write failures) for integration, negative, and end-to-end MCP tests (`IT_PROV`, `IT_CACHE`, `IT_DRAFT`, `IT_DRAFT_PARTIAL`).

## Contract Integrity (`NFR-10`)
An AST/import-lint test enforces that no domain, validation, similarity, analysis, playlist, or tool module imports HTTP or Google API client libraries outside `provider/live.py` and `auth/oauth.py`.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/fixture-testing-and-vcr|Fixture Testing and VCR]]
- [[brain/resources/youtube-quota-costs|YouTube Quota Costs]]
- [[brain/inbox/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
- [[brain/areas/second-brain|Second Brain Architecture]]
