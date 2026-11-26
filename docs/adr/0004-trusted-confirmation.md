# ADR-0004: Trusted Confirmation Design and Write Step Ordering

- **Status:** Accepted
- **Date:** 2026-11-26
- **Decision Makers:** Mohammed Farhan (owner), Madire Shiva Reddy, Molleti Tatwik Sai
- **Task:** `MF-04`
- **GitHub Issue:** `#34`
- **GitHub PR:** `#35`
- **Requirements:** `FR-5.4`, `FR-5.5`, `FR-6.2`, `FR-7.1`, `FR-7.3`, `NFR-5`, `NFR-6`, `NFR-8`, `NFR-9`, `SE-3`, `SB-3`
- **Distilled Brain Sources (`SB-3`):**
  - [[brain/resources/mcp-elicitation-confirmation|Trusted Playlist Confirmation with MCP Elicitation]]
  - [[brain/areas/security/prompt-injection-defence|Prompt Injection Defense and Human in the Loop Gates]]
  - [[brain/projects/partial-playlist-outcomes|Playlist Writes and Partial Outcomes]]
  - [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle]]
  - [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]

## Context

`create_curated_playlist` is the sole mutating MCP tool in `yt-intel-mcp`. Because third party YouTube titles and descriptions are untrusted input (`NFR-6`, `INV-22`), a prompt injection inside video metadata or chat conversation must never trigger or approve playlist writes (`FR-5.4`, `INV-13`). Furthermore, `create_curated_playlist` coordinates several failure sensitive boundaries before and during YouTube API mutation:

1. **Trusted confirmation (`FR-5.4`, `SRS Section 3.3`):** Approval must come through an out of band trusted channel (`MCP elicitation` or a one time local HTTP confirmation page bound strictly to `127.0.0.1`), minting a single use server held token (`INV-14`).
2. **Authorisation boundaries (`FR-7.1`, `FR-7.3`, `C-5`, `C-6`, `C-7`, `INV-20`):** Login uses `youtube.readonly` only. Installed desktop apps cannot perform incremental OAuth consent, so creating a playlist requires a separate full consent flow for `youtube.force-ssl` and requires an active YouTube channel on the Google account.
3. **Staleness and non retried ordered writes (`FR-5.5`, `NFR-8`, `INV-15`, `INV-16`, `INV-17`, `INV-24`):** Approved videos must be re checked immediately before writing (`DRAFT_STALE` if changed or unavailable), created in exact approved order with zero automatic write retries, and reported accurately as `COMPLETE` or `PARTIAL` without editing or deleting existing playlists.
4. **Open Gap `G-02`:** `docs/plan/development-plan.md` tracks the exact execution order of draft checks, trusted confirmation, token verification, stale video check, OAuth write consent, channel validation, and quota preflight inside `create_curated_playlist`.

## Decision

### 1. Draft Identifier Only Tool Schema (`create_curated_playlist.json`, `INV-13`, `INV-14`)

`src/yt_intel_mcp/schemas/create_curated_playlist.json` enforces `"additionalProperties": false` with `draft_id` as the sole accepted input parameter. Confirmation tokens, video lists, titles, privacy overrides, and boolean approval flags are rejected at schema validation (`INVALID_ARGUMENT` before quota).

### 2. Dual Trusted Confirmation Channels (`FR-5.4`, `INV-13`, `INV-22`)

Every displayed summary across either channel renders sanitized metadata (`yt_intel_mcp.sanitize`, NFKC normalized, invisible and bidi control characters stripped, URLs removed, length limited) and displays: authenticated account / channel identity, playlist title, privacy setting, ordered video list (title, channel, duration, audio language status), total duration versus target window, and draft expiry timestamp.

1. **Channel A: MCP Elicitation (`src/yt_intel_mcp/confirmation/elicit.py`):**
   - Selected whenever the active MCP client session advertised the `elicitation` capability during `initialize` (`R-4` MCP 2025-06-18).
   - Sends an `elicitation/create` request containing the sanitized draft summary and a boolean confirmation schema (`confirm`), accepting only an explicit `"accept"` response (`"decline"` and `"cancel"` map to `CONFIRMATION_DECLINED`).
2. **Channel B: One Time `127.0.0.1` Confirmation Page (`src/yt_intel_mcp/confirmation/local_page.py`):**
   - Used when the MCP host does not declare `elicitation` and a local loopback listener plus browser opening is available.
   - Binds strictly to host `127.0.0.1` on an ephemeral OS assigned port (explicitly rejecting non loopback bind addresses in configuration and tests).
   - Serves a single request path keyed by an unguessable CSPRNG secret (`secrets.token_urlsafe(32)`), requires a CSRF protected `POST` with explicit `accept` or `decline` action, escapes every HTML field, sets `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'`, and shuts down immediately after receiving one decision or reaching expiry timeout.
3. **Unavailable Channel Guard (`INV-13`):**
   - If neither MCP elicitation nor a loopback browser page is available, `create_curated_playlist` immediately returns `ToolError(ErrorCode.CONFIRMATION_UNAVAILABLE)` and performs zero API calls.

### 3. Single Use Server Held Bound Confirmation Tokens (`src/yt_intel_mcp/confirmation/tokens.py`, `INV-14`)

- A confirmation token is minted strictly server side inside `ConfirmationTokenStore` only after an explicit `accept` decision from Channel A or Channel B.
- The token never appears in MCP tool responses, logs, exceptions, or LLM prompts.
- Every token binds cryptographically or structurally to:
  - `channel_id` (authenticated channel identity)
  - `draft_id`
  - `ordered_video_ids` (exact immutable tuple)
  - `title`
  - `privacy_status`
  - `expires_at_utc`
- Verification enforces strict invariants before write dispatch:
  - Mismatch on any bound field -> `CONFIRMATION_MISMATCH`
  - Past `expires_at_utc` -> `DRAFT_EXPIRED`
  - Second verification or already consumed token -> `CONFIRMATION_REUSED`
  - User declined or cancelled -> `CONFIRMATION_DECLINED`

### 4. Resolution of `G-02`: Exact Step Order Inside `create_curated_playlist(draft_id)`

Freeze the following deterministic 9 step sequence across `tools/create_curated_playlist.py` (`MF-14`) and `playlist/writer.py`:

| Step | Action | Quota / Side Effect | Error / Outcome |
|---|---|---|---|
| 1 | Validate `draft_id` schema, look up immutable `Draft`, verify `now_utc < draft.expires_at_utc` | `0` calls | `INVALID_ARGUMENT` or `DRAFT_EXPIRED` |
| 2 | Read current local auth session identity (`channel_id` / account display from `TokenStore` or cached channel metadata) | `0` calls | `AUTH_REAUTHORIZATION_REQUIRED` if unauthenticated |
| 3 | Obtain trusted confirmation via Channel A (elicitation) or Channel B (`127.0.0.1` page) showing account, title, privacy, ordered items, duration, expiry | `0` calls | `CONFIRMATION_DECLINED` or `CONFIRMATION_UNAVAILABLE` |
| 4 | Mint and consume single use server held token bound to `(channel_id, draft_id, ordered_video_ids, title, privacy_status, expires_at_utc)` | `0` calls | `CONFIRMATION_MISMATCH`, `DRAFT_EXPIRED`, or `CONFIRMATION_REUSED` |
| 5 | Preflight combined workflow budget (`recheck_units + 50 + 50 * len(videos)`) and execute fresh uncached `get_videos(ordered_video_ids)` stale check (`FR-5.5(1)`) | `1 u` per `<= 50` videos (charged) | `QUOTA_BUDGET_INSUFFICIENT` (0 calls) or `DRAFT_STALE` (0 writes if missing, private, deleted, live, or constraint violating) |
| 6 | Ensure write scope `youtube.force-ssl` (`FR-7.1`, separate full PKCE consent if only `youtube.readonly` held) | OAuth consent only if needed | `SCOPE_INSUFFICIENT` or `AUTH_REAUTHORIZATION_REQUIRED` |
| 7 | Verify authenticated YouTube channel via `get_my_channel()` (if not already verified in session) and assert `channel_id` matches token binding | `0` or `1 u` (preflighted) | `CHANNEL_REQUIRED` (`youtubeSignupRequired`) or `CONFIRMATION_MISMATCH` if account changed |
| 8 | Run exact write preflight for `50 + 50 * len(videos)` units (`FR-6.2`, `INV-19`) | `0` calls | `QUOTA_BUDGET_INSUFFICIENT` (0 writes) |
| 9 | Dispatch `insert_playlist` (`50 u`, `0` retries), then ordered `insert_playlist_item` (`50 u` each, `0` retries); continue on item errors, stop at once on quota or auth errors | `50 + 50 * attempted` units (charged per call) | `COMPLETE` (all inserted and constraints hold) or `PARTIAL` report (`playlist_url`, inserted, failed, not attempted, actual duration, unmet constraints) |

**Why this order resolves `G-02` cleanly:**
- Steps 1 to 3 guarantee expired drafts never prompt the user, and declined confirmations never trigger OAuth write consent escalation or YouTube API calls (`FR-5.4`).
- Step 5 runs the combined quota gate (`QT_3`) before touching `YouTubeProvider` and detects stale or deleted videos (`FR-5.5(1)`) before asking for `youtube.force-ssl` write consent or performing any playlist write.
- Steps 6 to 8 enforce least privilege write scope (`C-6`, `C-7`), channel ownership (`C-5`), account consistency against the approved confirmation token (`INV-14`), and exact final write quota (`FR-6.2`).
- Step 9 honors zero write retries (`NFR-8`, `INV-24`), ordered insertion (`INV-16`), and full `COMPLETE` / `PARTIAL` reporting (`INV-17`) without ever modifying or deleting existing playlists (`SRS Section 1.2`).

## Alternatives Considered

- **Running `youtube.force-ssl` OAuth escalation before trusted confirmation:** Rejected because asking a user to grant destructive write consent before they have confirmed the playlist draft violates `FR-5.4` ("first obtains trusted confirmation") and wastes an interactive OAuth consent when the user declines the draft.
- **Accepting an LLM provided approval string or confirmation token argument:** Rejected because `NFR-6` and `FR-5.4` strictly forbid trusting chat text, tool arguments, or metadata as approval (`INV-13`, `INV-14`).
- **Retrying failed `playlistItems.insert` calls automatically:** Rejected because write requests are non idempotent and `NFR-8` / `FR-5.5` prohibit automatic write retries (`write_max_retries = 0`).

## Consequences

### Positive
- Resolves `G-02` unambiguously ahead of `MF-12`, `MF-13`, and `MF-14` implementation.
- Guarantees prompt injection payloads in titles or descriptions cannot bypass user confirmation (`INV-13`, `INV-22`).
- Preserves zero write side effects on `CONFIRMATION_DECLINED`, `CONFIRMATION_UNAVAILABLE`, `DRAFT_STALE`, `SCOPE_INSUFFICIENT`, `CHANNEL_REQUIRED`, and `QUOTA_BUDGET_INSUFFICIENT`.

### Trade Offs
- When a user only holds `youtube.readonly` and has a stale video in the draft, Step 5 fails with `DRAFT_STALE` after consuming `1` metadata unit without triggering a needless write scope OAuth flow.
- Binding `channel_id` before confirmation requires an authenticated read session prior to `create_curated_playlist`, aligning with `draft_curated_playlist` and `FR-7.1`.

## References

- `Final_SRS_Submission.pdf` (v1.0): Section 1.2, Section 3.1, Section 3.3, Section 4.5 (`FR-5.4`, `FR-5.5`), Section 4.7 (`FR-7.1`, `FR-7.3`), Section 5 (`NFR-5`, `NFR-6`, `NFR-8`).
- `docs/adr/0002-provider-and-errors.md` (frozen `YouTubeProvider`, `ErrorCode`, `QuotaGuard`).
- `docs/adr/0006-token-storage-and-persistence.md` (`TokenStore` and OAuth credential lifecycle).
- `docs/architecture/playlist.md` (draft state diagram and `create_curated_playlist` sequence diagram).
