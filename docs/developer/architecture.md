# Developer Architecture Guide (SE-2, SE-7, NFR-9)

This document describes the architectural design, component topology, and critical invariants of the YouTube Video Intelligence MCP Server (`yt-intel-mcp`).

## 1. Architectural Baseline and Invariants

The implementation is bound by the system requirements in `Final_SRS_Submission.pdf` (version 1.0) and architectural decisions recorded under `docs/adr/`.

### Core Architectural Invariants
- **Provider Interface Isolation (SE-6, FR-8.1):** All external YouTube Data API v3 calls are strictly mediated by the abstract `YouTubeProvider` interface (`src/yt_intel_mcp/provider/base.py`). Domain modules (similarity scoring, recommendations, engagement analysis, playlist curation, quota management, and MCP tool handlers) never import HTTP client packages or Google client libraries directly.
- **Deterministic Server:** The server executes local metadata ranking, TF IDF scoring, and constraint satisfaction solving locally. It never invokes upstream LLMs or nondeterministic external AI services.
- **Objective Metadata Only (FR-1.3, FR-2.2, INV-01):** Popularity metrics (view counts, like counts, subscriber counts, and comment counts) never influence similarity scoring, recommendation ranking, or channel discovery. The server never requests the YouTube `statistics` part.
- **Trusted Confirmation for Side Effects (FR-5.4, NFR-6):** Creating a YouTube playlist requires explicit, out of band human approval. Approval is gathered via MCP elicitation (Channel A) or a local loopback `127.0.0.1` confirmation page (Channel B). Chat text, tool arguments, or video metadata can never authorize writes.
- **Persistent Dual Quota Enforcement (FR-6, C-01):** The server tracks both daily units (10,000 units per day) and daily search calls (100 `search.list` calls per day) in a persistent SQLite ledger, resetting daily at 00:00 Pacific Time. Every live tool preflights budget before dispatching calls.

## 2. Component Dependency Topology

The server follows a layered architecture with explicit, unidirectional dependencies:

```text
+--------------------------------------------------------------------------+
|                            MCP Server Layer                              |
|   src/yt_intel_mcp/server.py, __main__.py, tools/*, resources/*           |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                           Domain Modules                                 |
|   similarity/  analysis/  playlist/  confirmation/  validation/  quota/  |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                    Cached YouTube Provider Layer                         |
|   src/yt_intel_mcp/provider/cache.py (TTL In Memory / SQLite Cache)      |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                  YouTubeProvider Interface (SE-6)                        |
|   src/yt_intel_mcp/provider/base.py                                      |
+------------------+-----------------------------------+-------------------+
                   |                                   |
                   v                                   v
+-------------------------------------+ +----------------------------------+
|      Fixture Provider               | |        Live Provider             |
|  src/yt_intel_mcp/provider/         | |  src/yt_intel_mcp/provider/      |
|  fixture.py                         | |  live.py (Google API Client)     |
+-------------------------------------+ +----------------------------------+
```

## 3. Runtime Lifecycle and Assembly (`server.py`)

The server runtime is assembled in `src/yt_intel_mcp/server.py` via `build_server_runtime(...)`:

1. **Configuration Loading:** `AppConfig.from_env()` loads settings from environment variables with safe defaults.
2. **Persistent Store Initialization:** `SQLiteStore.from_config(config)` connects to the local SQLite database in WAL mode and runs necessary table migrations.
3. **Quota Ledger Creation:** `PersistentQuotaLedger(store, config.quota)` initializes the dual budget tracking mechanism.
4. **Token and Draft Stores:** `EncryptedTokenStore` (AES 256 GCM / keyring), `SQLitePlaylistDraftStore`, and `SQLiteConfirmationStore` are wired to the SQLite database.
5. **Base Provider Selection:** Either `LiveYouTubeProvider` or `FixtureYouTubeProvider` is instantiated based on `config.provider_mode`.
6. **Metadata Caching:** `CachedYouTubeProvider` wraps the base provider with TTL caching for video details and channel metadata (`FR-6.3`, `NFR-1`).
7. **Tool and Resource Registration:** All 8 MCP tools and 2 static resources (`youtube://metrics/quota`, `youtube://user/context`) are registered onto the `MCPServer` instance.

## 4. Subsystem Details

### Similarity and Recommendation Engine (`similarity/`, `analysis/`)
- Uses TF IDF vectorization over objective textual fields (title, tags, description) combined with duration proximity and category matching.
- Personal recommendations aggregate explicit user signals (subscriptions, playlists, liked videos) with exponential half life decay based on observation age (`FR-3.2`, `ADR-0007`).
- Zero popularity bias is enforced: candidate pool selection and ranking never query or use view or like metrics.

### Constraint Satisfaction Playlist Solver (`playlist/`)
- Draft creation solves a multi dimensional subset sum problem to fit candidate videos within the target duration window `[T * (1 - tolerance), T]` without exceeding target minutes `T`.
- Filters candidates by language (checking BCP 47 primary subtag against `snippet.defaultAudioLanguage`), duration bounds, live stream exclusion, and privacy status.
- Yields immutable drafts stored in SQLite with unique identifiers, valid for 1 hour.

### Trusted Human Confirmation Architecture (`confirmation/`)
- Playlist write execution strictly requires a valid confirmation token issued through trusted human interaction (`ADR-0004`).
- **Channel A (MCP Elicitation):** When the host client supports the MCP elicitation capability, an interactive confirmation dialog prompts the user with playlist title, video count, total duration, and quota cost.
- **Channel B (Loopback Page):** Fallback mechanism binds a temporary one time HTTP server to `127.0.0.1` and displays an out of band review page. The user approves by clicking a confirmation button, generating an HMAC SHA 256 token.
- Confirmation tokens are single use, valid for 10 minutes, and strictly bound to the specific draft ID and session.

### OAuth and Token Management (`auth/`)
- Employs Authorization Code flow with Proof Key for Code Exchange (PKCE) per RFC 7636.
- Least privilege scope progression: initial authentication requests read only scope (`youtube.readonly`); write scope (`youtube.force-ssl`) is requested separately only when the user confirms creating a playlist.
- Stored credentials are encrypted at rest using OS keyring (primary) with AES 256 GCM fallback (`ADR-0006`).

## 5. Storage Schema and Data Model

The SQLite database (`yt_intel.db`) contains the following tables:
- `quota_daily_ledger`: Tracks date, units used, search calls used, and last update timestamp.
- `oauth_tokens`: Stores encrypted token bundles with AES 256 GCM ciphertext, IV, and auth tag.
- `playlist_drafts`: Holds serialized JSON candidate items, topic, target duration, language, and expiration timestamp.
- `confirmation_tokens`: Stores single use confirmation tokens, bound draft ID, channel ID, and consumed status.
- `event_observations`: Tracks explicit library items and their `first_observed` timestamps for half life weighting.
- `metadata_cache`: Stores cached video and channel responses with expiration timestamps.
