---
title: Provider Interface Pattern and Dependency Inversion
type: architecture
created: 2026-11-09
tags:
  - architecture
  - testing
  - provider-pattern
  - dependency-inversion
requirements:
  - FR-8
  - SE-6
  - TQ-2
---

# Provider Interface Pattern and Dependency Inversion

## Summary
To decouple business logic from external Google network calls and guarantee deterministic test execution, all YouTube operations are mediated through a strict `YouTubeProvider` interface.

## Architecture
The hexagonal architecture pattern isolates external boundaries:

```text
Domain / Application Layer (Similarity, Knapsack, Quota Tracker)
                          │
                          ▼
            «interface» YouTubeProvider
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
LiveYouTubeProvider  FixtureYouTubeProvider  FakeYouTubeProvider
(Google REST API)   (Recorded Cassettes)    (In Memory Mocks)
```

## Provider Implementations
1. **LiveYouTubeProvider**:
   - Implements actual HTTPS requests to `googleapis.com`.
   - Handles network timeouts, exponential backoff, and bearer token attachment.
2. **FixtureYouTubeProvider**:
   - Reads recorded, scrubbed HTTP interaction cassettes from disk.
   - Used for integration and system tests in continuous integration pipelines.
   - Guarantees zero quota consumption during pull request validation.
3. **FakeYouTubeProvider**:
   - In memory dictionary backed mock.
   - Allows fault injection (for example simulating quota exhaustion or rate limits) during unit testing.

## Contract Integrity
All three implementations must satisfy the exact same provider contract test suite (`IT-PROV-*`). No domain service is permitted to import external HTTP libraries directly.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/fixture-testing-and-vcr|Fixture Testing and VCR]]
- [[brain/resources/youtube-quota-costs|YouTube Quota Costs]]

