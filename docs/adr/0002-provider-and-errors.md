# ADR-0002: Provider Boundary, Direct HTTP Client, and Shared Error Contracts

- **Status:** Accepted
- **Date:** 2026-11-25
- **Decision Makers:** Madire Shiva Reddy (owner), Molleti Tatwik Sai, Mohammed Farhan
- **Task:** `SR-04`
- **GitHub Issue:** `#25`
- **GitHub PR:** `#26`
- **Requirements:** `FR-8.1`, `SE-3`, `SE-6`, `FR-6.2`, `NFR-8`, `NFR-9`, `NFR-10`, `SB-3`
- **Brain Sources:**
  - [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]
  - [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
  - [[brain/resources/youtube-quota-costs|YouTube API Quota Costs]]
  - [[brain/resources/fixture-testing-and-vcr|Fixture Testing and VCR]]
  - [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]
  - [[brain/areas/security/prompt-injection-defence|Prompt Injection Defense]]

## Context

Stage 2 parallel development across Tatwik (`FR-1`..`FR-4`, validation), Farhan (`FR-5` constraints, sanitization, HITL confirmation), and Shiva (`FR-6`..`FR-8`, SQLite cache/quota ledger, OAuth, live HTTP provider) requires a frozen shared contract boundary (`CT-1`) before domain or provider PRs merge.

Key architectural constraints from `Final_SRS_Submission.pdf` (v1.0):
- **Provider isolation (`SE-6`, `FR-8.1`):** Domain modules must never import HTTP clients or Google client libraries (`INV-19`). All YouTube Data API v3 access passes through `YouTubeProvider` so deterministic fixture execution in CI (`YT_INTEL_PROVIDER=fixture`) and live execution (`YT_INTEL_PROVIDER=live`) share identical behavior.
- **Objective metadata only (`FR-1.3`, `FR-2.2`, `INV-01`):** Provider methods and domain dataclasses must never request `statistics` or store popularity fields (`view_count`, `like_count`, `subscriber_count`).
- **Exclusions (`SRS Section 1.2`):** The server must not edit or delete existing YouTube playlists or call unofficial APIs.
- **Retry & quota discipline (`NFR-8`, `FR-6.2`):** Read-only calls retry up to `3` times on transient faults; non-idempotent playlist/item writes retry `0` times (`write_max_retries=0`); every dispatch runs a dual daily quota preflight (`units` and `search_calls` in Pacific Time).
- **Consistent MCP envelopes (`SRS Section 4.1`, `Section 5`):** Every tool emits either `{summary, data, quota_used}` or `{code, message, details, quota_used}` using the 17 frozen `ErrorCode` values.

## Decision

### 1. Async `YouTubeProvider` Protocol Boundary (`SE-6`, `FR-8.1`)
Freeze `YouTubeProvider` as a `@runtime_checkable` `typing.Protocol` in `src/yt_intel_mcp/provider/base.py` with 13 async methods:
- Reads: `get_videos`, `search_videos`, `search_channels`, `get_channels`, `get_channel_by_handle`, `get_my_channel`, `list_subscriptions_mine`, `list_playlists_mine`, `list_playlist_items`, `list_liked_videos_rated`, `get_video_categories`.
- Confirmed writes: `insert_playlist`, `insert_playlist_item`.
- Intentionally absent: playlist update/delete methods (`SRS Section 1.2`) and `statistics` fields (`INV-01`).

Making `YouTubeProvider` methods `async def` aligns directly with `MCPServer` async tool handlers (`mcp 2.3.0`), `anyio` (`anyio 4.16.0`), async retry backoff in `SR-14`, and async `ctx.elicit()` confirmation flows (`MF-12`) without blocking the stdio event loop.

### 2. Direct REST HTTP Client in `SR-14` (Not `google-api-python-client`)
Implement the live provider (`src/yt_intel_mcp/provider/live.py`, task `SR-14`) using direct REST HTTP calls to `https://www.googleapis.com/youtube/v3/...` endpoints rather than `google-api-python-client`.
- Verified environment state in `.venv`: `pyproject.toml` currently declares `dependencies = ["mcp>=2.3,<3"]`, which pulls `anyio 4.16.0`, `httpx2 2.16.2`, and `httpcore2 2.16.2`; `google-api-python-client` is not installed.
- Using direct REST JSON requests inside `SR-14` (either declaring an explicit HTTP client dependency in `pyproject.toml` during `SR-14` or using an async-wrapped transport encapsulated in `provider/live.py`) avoids API discovery document overhead, guarantees explicit timeout/retry separation between reads (`3` retries) and writes (`0` retries), and keeps `httpx`/HTTP types strictly behind `YouTubeProvider`.

### 3. Synchronous `QuotaGuard` Protocol and Frozen `AppConfig`
- Freeze `QuotaGuard` (`estimate`, `preflight`, `charge`, `mark_upstream_exhausted`, `status`) and `QuotaStatus` in `src/yt_intel_mcp/quota/guard.py` using synchronous signatures so SQLite ledger operations work cleanly in both async handlers and synchronous unit helpers.
- Freeze `AppConfig` and nested section dataclasses in `src/yt_intel_mcp/config.py` with all binding defaults from `SRS Section 5` (`10,000` units/day, `100` search calls/day, `America/Los_Angeles` reset, `search_unit_cost=0` by default per `C-2`/`NFR-2` so 10-video workflows stay `<= 600` units while keeping `0` or `100` configurable for the R-1 model, TTLs `86400`/`21600`/`900`, `draft.ttl_seconds=600`, `5%` tolerance, `max_videos=25`, `private` default, `90`-day half-life, `min_dated_events=5`, duration cutoffs `240s`/`1200s`, retries `3`/`0`, live smoke budget `300` units / `10` search calls).

### 4. Frozen Models, 17 `ErrorCode`s, Upstream Mapping, and Stage 2 Stubs
- Freeze `QuotaUsed`, `CostEstimate`, `VideoMeta`, `ChannelMeta` (including `keywords` for `FR-2.2` and excluding all popularity/statistics fields), `SearchHit`, `PlaylistSummary`, `CreatedPlaylist`, `EventSource`, `EventTimeKind`, and `UserEvent` in `src/yt_intel_mcp/models.py`.
- Freeze configurable objective similarity weights in `SimilarityConfig` (`title_weight`, `tags_weight`, `description_weight`, `category_weight`, `duration_weight`, `topics_weight`, `keywords_weight` pending `ADR-0003` in `TS-04`).
- Freeze all 17 `ErrorCode`s, `OutcomeStatus` (`COMPLETE`, `PARTIAL`), `ToolError`, `success_response`, `error_response`, and `map_upstream_error` in `src/yt_intel_mcp/errors.py`.
- Freeze stub function signatures (`NotImplementedError`) in `src/yt_intel_mcp/sanitize.py` (`MF-07`) and `src/yt_intel_mcp/validation/ids.py` (`TS-06`).

## Alternatives Considered

- **`google-api-python-client`:** Rejected because it relies on dynamic discovery JSON documents, provides synchronous-only execution with implicit HTTP retry behavior risky for non-idempotent `playlists.insert`/`playlistItems.insert` calls (`INV-21`), and introduces heavy transitive dependencies.
- **Synchronous `YouTubeProvider` methods:** Rejected because blocking I/O and retry sleeps inside async MCP stdio handlers stall concurrent event-loop tasks (`anyio`).
- **Untyped `dict[str, Any]` payloads across domain modules:** Rejected because schema drift between Tatwik, Farhan, and Shiva's parallel branches would bypass `mypy --strict` checks.

## Consequences

### Positive
- Tatwik (`TS-06`..`TS-15`), Farhan (`MF-07`..`MF-14`), and Shiva (`SR-08`..`SR-15`) can implement independent vertical slices concurrently against stable frozen contracts and strict types (`mypy src`).
- Objective metadata invariance (`INV-01`) and playlist-mutation exclusion (`SRS Section 1.2`) are enforced structurally at the type/protocol boundary.
- Upstream error mapping (`SRS Section 5`) is centralized once and verified deterministically in unit tests.

### Trade-offs
- Any future contract signature addition requires a reviewed ADR amendment (`CT-1` change control).
- Downstream implementers of `TS-06` and `MF-07` must preserve the frozen stub function signatures (or extend via backward-compatible optional parameters).

