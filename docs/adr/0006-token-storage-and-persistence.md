# ADR-0006: Encrypted OAuth Token Storage and Local SQLite Persistence

- **Status:** Accepted
- **Date:** 2026-11-26
- **Decision Makers:** Madire Shiva Reddy (owner), Molleti Tatwik Sai, Mohammed Farhan
- **Task:** `SR-05`
- **GitHub Issue:** `#30`
- **GitHub PR:** `pending`
- **Requirements:** `SE-3`, `FR-6`, `FR-7`, `FR-7.2`, `NFR-3`, `NFR-7`, `SB-3`
- **Distilled Brain Sources (`SB-3`):**
  - [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle in Testing Publishing Status]]
  - [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
  - [[brain/resources/youtube-quota-costs|YouTube Data API Quota Costs and Budgeting]]
  - [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern and Dependency Inversion]]

## Context

`yt-intel-mcp` runs as a single user local MCP server over `stdio` (`ADR-0001`, `SRS Section 2.3`) on Linux, macOS, and Windows. Two distinct local persistence problems must be solved cleanly before Stage 3 implementation (`SR-10` through `SR-13`):

1. **OAuth 2.0 Credential Protection (`FR-7.2`, `NFR-3`, `NFR-7`, `INV-20`, `INV-21`):**
   - Installed desktop PKCE flows store long lived refresh tokens (7 day expiry in Testing publishing status per `C-4`) and short lived access tokens.
   - `SRS Section 4.7` (`FR-7.2`) and `Section 5` (`NFR-3`) mandate encrypted storage at rest using the OS keyring or an `AES-256-GCM` encrypted local file. Tokens must never be written to logs (`stderr`/`stdout`), fixtures, or tool responses (`get_auth_status` returns granted scopes, expiry status, storage backend, and channel presence only).
   - Headless Linux environments, containers, and automated CI test runners frequently lack an unlocked OS keyring daemon, requiring a deterministic encrypted file fallback without silently downgrading to plaintext JSON.
2. **Quota Ledger, Cache, and Timestamp Provenance Persistence (`FR-6.1`, `FR-6.3`, `ADR-0007`, `NFR-7`):**
   - Dual daily quota counters (`10,000` units/day and `100` `search.list` calls/day resetting at `00:00` `America/Los_Angeles`), TTL metadata cache entries (`24 h` / `6 h` / `15 min`), and optional `first_observed` timestamps (`G-05`) must persist reliably across server restarts and concurrent tool invocations.
   - Revoking authentication (`NFR-7`) must delete stored OAuth tokens and all locally cached personal user lists immediately.

## Decision

### 1. Two Layer Encrypted Token Store (`src/yt_intel_mcp/auth/token_store.py`, `SR-12`)

Separate credential protection completely from SQLite metadata persistence behind a dedicated `TokenStore` abstraction:

1. **Primary Backend (OS Keyring):**
   - When an unlocked platform credential store (`Windows Credential Manager`, `macOS Keychain`, or `Linux Secret Service`) is available, `TokenStore` stores the serialized JSON token bundle (`access_token`, `refresh_token`, `scopes`, `expires_at_utc`, `issued_at_utc`, `channel_id`, `has_channel`) under service name `yt-intel-mcp` and profile account key.
   - Note on `pyproject.toml` dependencies: adding any optional keyring library in `SR-12` follows `[CONTRACT]` change control (`ADR-0001`, peer review by Tatwik and Farhan); `TokenStore` must also accept an injected backend or environment override so CI and headless hosts operate without requiring a live system daemon.
2. **Encrypted File Fallback (`AES-256-GCM` at `<data_dir>/tokens.enc`):**
   - When no OS keyring is accessible, `TokenStore` encrypts the JSON token bundle using `AES-256-GCM` (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`, already available in the Python environment).
   - Each write generates a fresh `96` bit CSPRNG nonce (`os.urandom(12)`), authenticates a versioned header plus profile identifier as Associated Authenticated Data (`AAD`), produces a `128` bit GCM authentication tag, and writes atomically (temp file + replace) with owner only permissions (`0600` on POSIX / current user ACL on Windows).
   - The `256` bit symmetric key is obtained from `YT_INTEL_TOKEN_KEY` (when configured by the user or test harness) or generated randomly on first use into `<data_dir>/.token_key` with owner only permissions (`0600`). Both `tokens.enc` and `.token_key` remain strictly outside Git inside `~/.yt-intel-mcp/` (`AppConfig.data_dir`).
   - Plaintext token files (`token.json`) are strictly prohibited in all environments (`NFR-3`).
3. **Non Secret Status Projection and Log Redaction (`NFR-3`, `INV-20`):**
   - `TokenStore.read_metadata()` projects only non secret fields (`authenticated`, `scopes`, `expires_at_utc`, `issued_at_utc`, `has_channel`, `storage_backend`) consumed by `get_auth_status`.
   - Credential dataclasses override `__repr__` to redact `access_token` and `refresh_token`, and security tests (`SEC_OAUTH`) assert zero plaintext token bytes on disk and zero token leakage in captured logs or tool payloads.

### 2. Local WAL SQLite Store (`src/yt_intel_mcp/store.py`, `SR-10`)

Persist non secret operational state in a single local SQLite database at `<data_dir>/yt_intel.db` using Python standard library `sqlite3` (as documented in `docs/architecture/overview.md` Section 4):

- Initialize every connection with `PRAGMA journal_mode=WAL;`, `PRAGMA synchronous=NORMAL;`, `PRAGMA foreign_keys=ON;`, and `PRAGMA busy_timeout=5000;`.
- Create three explicit tables:
  1. `quota_ledger`: Pacific Time `budget_date` primary key, `units_used`, `search_calls_used`, `upstream_exhausted`, `exhausted_until_utc`, and `updated_at_utc`.
  2. `cache_entries`: `cache_key` primary key, `entry_kind` (`videos` | `channels` | `searches` | `user_lists` | `categories`), `is_personal` flag, `payload_json` (objective metadata only), `created_at_utc`, and `expires_at_utc`.
  3. `first_observed`: composite primary key `(source, item_id)` and `first_observed_utc` (`ADR-0007` `G-05`).
- Execute quota preflight checks and ledger charges inside `BEGIN IMMEDIATE` transactions so concurrent async handlers cannot race past daily limits (`INV-19`).

### 3. Delete on Revoke Semantics (`NFR-7`, `INV-21`)

When the user revokes authorization (or explicitly resets local credentials):

1. Best effort HTTP revocation against Google's token revocation endpoint (when online and using `live` mode).
2. `TokenStore.revoke()` clears credentials from **both** the OS keyring entry and any `<data_dir>/tokens.enc` fallback file so no stale encrypted blob lingers after backend changes.
3. `SQLiteStore.purge_personal_data()` runs an atomic SQLite transaction deleting all `cache_entries` rows where `is_personal = 1` (covering all cached `user_lists` such as likes, subscriptions, and personal playlists) and all rows from `first_observed`.
4. `quota_ledger` rows are **preserved** across revocation so signing out or revoking OAuth tokens never clears or bypasses the Google Cloud project's active daily quota consumption (`FR-6.1`, `C-2`).

## Alternatives Considered

- **Storing OAuth tokens in SQLite (`tokens` table) instead of OS keyring + `tokens.enc`:** Rejected because placing secrets inside the same database file as metadata caches forces every database copy or inspection to handle secret ciphertext, precludes native OS keyring protection (`FR-7.2`), and complicates clean credential revocation.
- **Using `Fernet` (`AES-128-CBC` + HMAC) instead of `AES-256-GCM`:** Rejected because `SRS Section 4.7` (`FR-7.2`) and `SDLC` explicitly specify `AES-256-GCM` for the encrypted file fallback, providing 256 bit authenticated encryption natively via `cryptography`.
- **Requiring OS keyring unconditionally with no file fallback:** Rejected because headless Linux servers, containers, and CI environments often run without a Secret Service / D-Bus session; `AES-256-GCM` fallback keeps encrypted storage deterministic everywhere.
- **Clearing `quota_ledger` on auth revoke:** Rejected because YouTube API daily quota belongs to the single Google Cloud project (`C-2`), not solely to one local session token; wiping quota history on revoke would let preflight checks misreport remaining budget.

## Consequences

### Positive
- Gives `SR-10` (`store.py`, `quota/ledger.py`), `SR-11` (`cache.py`), `SR-12` (`auth/token_store.py`, `get_auth_status`), and `SR-13` (`auth/oauth.py`) a clean, frozen persistence contract matching `docs/architecture/overview.md`.
- Enforces `NFR-3` (OS keyring or `AES-256-GCM` encryption, zero plaintext tokens) and `NFR-7` (complete personal data deletion on revoke) without introducing external services or daemons.
- Preserves strict zero quota deterministic testing (`TQ-5`) by allowing tests to point `AppConfig.data_dir` at temporary directories with injected or fallback token storage.

### Trade Offs
- When OS keyring is unavailable and `YT_INTEL_TOKEN_KEY` is not externally managed, security of `tokens.enc` depends on OS file permissions protecting `<data_dir>/.token_key` against other local accounts, though it still eliminates plaintext token exposure in backups, text searches, or accidental copies of `tokens.enc`.
- Any optional third party `keyring` dependency added to `pyproject.toml` in `SR-12` will require dual reviewer sign off (`Tatwik` and `Farhan`) per repository policy (`docs/developer/branching.md`).

## References

- `Final_SRS_Submission.pdf` (v1.0): Section 2.3 (Operating Environment), Section 4.6 (`FR-6`), Section 4.7 (`FR-7`), Section 5 (`NFR-3`, `NFR-7`).
- `docs/architecture/overview.md` (`SE-2` component, deployment, SQLite ER, and OAuth/quota sequence diagrams).
- `docs/adr/0002-provider-and-errors.md` (`YouTubeProvider` and `QuotaGuard` contracts).
- `docs/adr/0007-interest-profile.md` (`G-05` `first_observed` policy).
- Distilled Second Brain notes (`SB-3`):
  - [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle in Testing Publishing Status]]
  - [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
  - [[brain/resources/youtube-quota-costs|YouTube Data API Quota Costs and Budgeting]]
  - [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern and Dependency Inversion]]
