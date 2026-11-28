# Agent Skill Evaluations (`TQ-7`)

This document records formal evaluations of every Agent Skill before each stage submission, satisfying requirement `TQ-7` and `SDLC` Section 5.

## Evaluation Summary

| Stage | Skill ID | Skill Name | Evaluation Date | Evaluator | Result | Evidence |
|---|---|---|---|---|---|---|
| Stage 1 | `SK-3` | `brain-ingest` | 2026-11-25 | Molleti Tatwik Sai | **PASS** | `scripts/validate_skills.py`, `scripts/validate_brain.py`, CI run `45619944133` |
| Stage 2 | `SK-4` | `brain-refine` | 2026-11-25 | Molleti Tatwik Sai | **PASS** | `scripts/validate_skills.py`, `scripts/validate_brain.py`, Issue `#19`, PR `#20` |
| Stage 2 | `SK-2` | `local-check` v1 | 2026-11-25 | Mohammed Farhan | **PASS** for v1 | `scripts/local_check.py`, `tests/unit/test_local_check.py`, Issue `#23`, PR `#24`, CI run `45660229608` |
| Stage 2 | `SK-5` | `brain-query` | 2026-11-26 | Madire Shiva Reddy | **PASS** | `skills/brain-query/SKILL.md`, `brain/areas/skill-brain-query.md`, Issue `#32`, PR `#33`, CI run `45698759114` |
| Stage 3 | `SK-1` | `video-to-playlist` | 2026-11-28 | Mohammed Farhan | **PASS** | `skills/video-to-playlist/SKILL.md`, `tests/unit/test_skill_video_to_playlist.py`, Issue `#88`, PR `#89` |

---

## Stage 1 Evaluation: `brain-ingest` (`SK-3`)

**Skill Path:** `skills/brain-ingest/SKILL.md`  
**Distilled Brain Citation (`SB-3`):** `[[brain/areas/second-brain|Second Brain Architecture]]`  
**Tasks Exercising Skill:** `TS-01` (`#3`, PR `#13`), `TS-02` (`#6`, PR `#14`), `SR-02` (`#5`, PR `#15`), `MF-03` (`#7`, PR `#17`), `TS-03` (`#9`, PR `#18`)

### Test Cases and Observed Results

| Case ID | Scenario | Expected Behaviour | Observed Result | Status |
|---|---|---|---|---|
| `SE-ING-01` | Skill frontmatter and `SB-3` citation check | `name` matches folder (`brain-ingest`), `description` is 1 to 1,024 chars, and body cites a `status: distilled` brain note | `python scripts/validate_skills.py` printed `Skill validation passed.` | **PASS** |
| `SE-ING-02` | Multi member ingestion into `brain/inbox/` (`SB-6`) | All 3 members ingest research notes into `brain/inbox/` with `status: inbox`, valid SRS v1.0 IDs, dated sources, `[[wikilinks]]`, and `index.md` links | Tatwik (`TS-02`: 3 research notes), Shiva (`SR-02`: 2 research notes), and Farhan (`MF-03`: 3 research notes) plus 7 AI session notes all merged and validated | **PASS** |
| `SE-ING-03` | Vault integrity across all notes (`SB-1`) | Every note passes YAML frontmatter schema, `scripts/srs_ids.txt` allow list, zero broken `[[wikilinks]]`, and direct indexing in `brain/index.md` | `python scripts/validate_brain.py` printed `Brain validation passed.` across all 31 vault markdown files | **PASS** |
| `SE-ING-04` | Rejection of invalid metadata and missing citations (`TQ-4`) | Malformed frontmatter, draft requirement IDs, missing `sources`/`authors`, unindexed notes, and non distilled citations fail validation | Verified by `tests/unit/test_validators.py` (`55 passed` in CI `ubuntu-latest` run `45619944133`) | **PASS** |
| `SE-ING-05` | Secret and PII hygiene (`NFR-4`, `NFR-7`) | Zero tokens, client secrets, credentials, or real personal identifiers in ingested notes | `gitleaks/gitleaks-action@v2` passed on all Stage 1 PRs (`#10` through `#17`) | **PASS** |

### Observations and Adjustments from Stage 1 Evaluation
1. **Log Format Alignment (`SKILL.md` vs `brain/log.md`):** During `TS-02` and `SR-02`, `skills/brain-ingest/SKILL.md` step 6 documented a 5 column log example starting with `brain-ingest` before `<Full Member Name>`, whereas `brain/log.md` defines 4 columns (`| Timestamp | Actor | Action | Output / Notes |`). In `TS-03`, `skills/brain-ingest/SKILL.md` step 6 was updated to match the 4 column table, and `brain/log.md` entries were normalized so the team member appears under `Actor` and the `brain-ingest` task appears under `Action`.
2. **Windows Local Validator Unit Tests (`tests/unit/test_validators.py`):** Running `pytest` directly on Windows reports 28 path separator assertion mismatches in `test_validators.py` because test fixtures compare `brain/...` with forward slashes against Windows `Path.relative_to` backslashes in stderr, whereas Linux CI (`ubuntu-latest`) runs and passes all 55 tests with 100 percent coverage. CLI execution of `validate_brain.py` and `validate_skills.py` passes cleanly on both Windows and Linux.

---

## Stage 2 Evaluation: `brain-refine` (`SK-4`)

**Skill Path:** `skills/brain-refine/SKILL.md`  
**Distilled Brain Citations (`SB-3`):** `[[brain/areas/second-brain|Second Brain Architecture]]`, `[[brain/areas/skill-brain-refine|Skill Note: brain-refine]]`  
**Tasks Exercising Skill:** `TS-05` (`#19`, PR `#20`)

### Test Cases and Observed Results

| Case ID | Scenario | Expected Behaviour | Observed Result | Status |
|---|---|---|---|---|
| `SE-REF-01` | Skill schema and `SB-3` distilled citation | `name` matches folder (`brain-refine`), `description` within 1 to 1,024 chars, and body cites `status: distilled` notes | `py -3.11 scripts/validate_skills.py` printed `Skill validation passed.` | **PASS** |
| `SE-REF-02` | Duplicate OAuth note consolidation | Merge unique PKCE, `get_auth_status`, `ADR-0006`, `#5`, and `#15` details from `brain/inbox/oauth-scopes-and-token-storage.md` into `brain/resources/google-oauth-testing-mode.md` and remove duplicate | Content consolidated cleanly into `google-oauth-testing-mode.md` and redundant inbox file deleted | **PASS** |
| `SE-REF-03` | PARA promotion and `status: distilled` transition | Promote remaining 7 Stage 1 research notes to canonical `brain/resources/` and `brain/projects/` destinations with `status: distilled` while keeping `ai-session-*.md` in `brain/inbox/` | All 7 notes promoted (4 resources, 3 projects) alongside `brain/areas/skill-brain-refine.md` and `ai-session-2026-11-25-tatwik-TS-05.md` | **PASS** |
| `SE-REF-04` | Vault wikilink repair and `docs/traceability.md` cleanup (`SB-1`) | Replace all stale `[[brain/inbox/...]]` links across notes, AI session records, `brain/index.md`, `brain/log.md`, and `docs/traceability.md` | `py -3.11 scripts/validate_brain.py` printed `Brain validation passed.` across all 32 vault markdown files | **PASS** |

## Stage 2 Evaluation of `local-check` v1 (`SK-2`)

- **Skill path** `skills/local-check/SKILL.md`
- **Distilled citation** `[[brain/areas/skill-local-check|Local Check Skill]]`
- **Execution** `python scripts/local_check.py` on macOS with Python 3.14.2

| Case ID | Scenario | Observed result | Status |
|---|---|---|---|
| `SE-LOCAL-01` | Build, tests, and MCP initialization | Built the wheel, ran 59 tests, and initialized the fixture-mode server over stdio | **PASS** |
| `SE-LOCAL-02` | Fetch unavailable in v1 | Reported `NOT RUN: no read-only fetch tool registered yet` and summarized three passes, zero failures, and one step not run | **PASS** for v1 |
| `SE-LOCAL-03` | Test and handshake failures | Automated test verified nonzero exit, the failed checks, the dependent fetch skip, and the final failure count | **PASS** |

The read-only fixture tool invocation remains pending MF-16. The v1 evaluation used zero live YouTube quota.

---

## Stage 2 Evaluation: `brain-query` (`SK-5`)

**Skill Path:** `skills/brain-query/SKILL.md`  
**Distilled Brain Citations (`SB-3`):** `[[brain/areas/second-brain|Second Brain Architecture]]`, `[[brain/resources/agent-skills-specification|Agent Skills Specification]]`, `[[brain/areas/skill-brain-query|Skill Note: brain-query]]`  
**Tasks Exercising Skill:** `SR-06` (`#32`, PR `#33`)

### Test Cases and Observed Results

| Case ID | Scenario | Expected Behaviour | Observed Result | Status |
|---|---|---|---|---|
| `SE-QRY-01` | Skill schema and `SB-3` distilled citation | `name` matches folder (`brain-query`), `description` within 1 to 1,024 characters, and body cites `status: distilled` brain notes | `validate_skills.py` passed (`Skill validation passed.`) | **PASS** |
| `SE-QRY-02` | Grounded Q&A with `[[wikilink]]` citations | Query on dual quota budgets and cache TTLs returns exact values (`10,000` units/day, `100` `search.list` calls/day, `24 h` / `6 h` / `15 min` TTLs, `00:00` PT reset) with inline `[[brain/resources/youtube-quota-costs]]` and `[[brain/resources/nfr-targets]]` citations | Verified exact figures and valid wikilinks present in `brain/resources/youtube-quota-costs.md` and `brain/resources/nfr-targets.md` | **PASS** |
| `SE-QRY-03` | Vault grounded document drafting (`SK-5`) | Draft a cohesive specification section using only `status: distilled` notes and explicit `[[wikilink]]` provenance | Produced the drafted section below (`Quota Governance and OAuth Security Baseline`) backed exclusively by 4 distilled vault notes | **PASS** |
| `SE-QRY-04` | Strict refusal on absent topic (`SK-5` anti hallucination) | Query *"What is YouTube Shorts monetization RPM or Partner Program payout threshold in this project?"* must refuse to guess and avoid fabricating external numbers | Vault inspection across `brain/index.md` and `brain/resources/` confirmed zero monetization or Shorts RPM notes; response refused to guess (`Not found in the Second Brain vault`) and recommended `brain-ingest` only if in scope (excluded per `SRS Section 1.2`) | **PASS** |

### Demonstrated Vault Draft Section (`SE-QRY-03` Output)

> **Drafted Section (Generated via `brain-query` from `status: distilled` Vault Notes):**
>
> #### Quota Governance and OAuth Security Baseline (`FR-6`, `FR-7`, `FR-8`, `NFR-3`, `NFR-7`)
>
> All outbound YouTube Data API v3 calls traverse a single `YouTubeProvider` Protocol configured by `YT_INTEL_PROVIDER=fixture|live`, omitting `statistics` fields and exposing no playlist update or delete methods ([[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]). Every request is tracked against two daily budgets inside a persistent ledger resetting at `00:00` Pacific Time (`America/Los_Angeles`): `10,000` quota units/day for list and write endpoints (`1` unit per list call, `50` units per `playlists.insert` or `playlistItems.insert`) and `100` `search.list` calls/day (configurable to `100` units/call under `C-2`), with zero extra Google Cloud projects permitted ([[brain/resources/youtube-quota-costs|YouTube Data API Quota Costs and Budgeting]]).
>
> Prior to any upstream call, preflight checks reject insufficient remaining capacity across either budget with `QUOTA_BUDGET_INSUFFICIENT`, while every dispatched call including failures charges the ledger and an upstream `quotaExceeded` response marks `QUOTA_EXHAUSTED_UPSTREAM` until daily reset ([[brain/resources/youtube-quota-costs|YouTube Data API Quota Costs and Budgeting]], [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]). Metadata caching reduces quota spend at `0` unit cost for cache hits using TTLs of `24 h` for videos and channels, `6 h` for searches, and `15 min` for personal user lists, while targeting `<= 500 ms` cached tool latency ([[brain/resources/youtube-quota-costs|YouTube Data API Quota Costs and Budgeting]], [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]).
>
> User authentication runs as an installed desktop OAuth 2.0 Authorization Code flow with PKCE (`S256`) over a `127.0.0.1` loopback redirect requesting `youtube.readonly` only at initial login (`C-6`), and uses a separate full consent request for `youtube.force-ssl` on playlist creation (`C-7`, `FR-7.1`) because installed desktop apps do not support incremental authorization ([[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle in Testing Publishing Status]]). Access and refresh tokens are stored encrypted at rest via the OS keyring or an `AES-256-GCM` file fallback (`NFR-3`), never logged or exposed in `get_auth_status`, refreshed silently until Testing mode `7` day expiry (`invalid_grant` -> `AUTH_REAUTHORIZATION_REQUIRED`), checked for channel presence (`youtubeSignupRequired` -> `CHANNEL_REQUIRED` on writes while reads continue), and deleted alongside cached personal user lists upon revocation (`NFR-7`) ([[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle in Testing Publishing Status]], [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]).

---

## Stage 2 Compilation Audit (`SR-07`, `#38`, PR `#39`)

- **Audit Date & Auditor:** 2026-11-26 — Madire Shiva Reddy (`@Shiva0025`)
- **Stage 2 Baseline Verified:** `main` at commit `b308efe` (`CI run 45770744075`: `100 passed in 3.88s`, `99.31%` coverage, `ruff`, `mypy`, `gitleaks`, `validate_skills.py`, `validate_brain.py`).
- **Skills Validated (`4` of `5` SRS skills complete through Stage 2; `SK-1` `video-to-playlist` arrives in Stage 3 `MF-15`):**
  - `SK-3` (`brain-ingest`, `#3`, PR `#13`): cites `[[brain/areas/second-brain]]` (`distilled`).
  - `SK-4` (`brain-refine`, `#19`, PR `#20`): cites `[[brain/areas/second-brain]]` and `[[brain/areas/skill-brain-refine]]` (`distilled`).
  - `SK-2` (`local-check` v1, `#23`, PR `#24`): cites `[[brain/areas/skill-local-check]]` (`distilled`); Step 4 fixture fetch stays explicitly `NOT RUN` until `MF-16`.
  - `SK-5` (`brain-query`, `#32`, PR `#33`): cites `[[brain/areas/second-brain]]`, `[[brain/resources/agent-skills-specification]]`, and `[[brain/areas/skill-brain-query]]` (`distilled`).

---

## Stage 3 Evaluation: `video-to-playlist` (`SK-1`)

**Skill Path:** `skills/video-to-playlist/SKILL.md`  
**Distilled Brain Citations (`SB-3`):** `[[brain/areas/skill-video-to-playlist|Skill Note: video-to-playlist]]`, `[[brain/resources/youtube-quota-costs|YouTube Data API Quota Costs and Budgeting]]`, `[[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]`  
**Tasks Exercising Skill:** `MF-15` (`#88`, PR `#89`)

### Test Cases and Observed Results

| Case ID | Scenario | Expected Behaviour | Observed Result | Status |
|---|---|---|---|---|
| `SE-V2P-01` | Skill schema and `SB-3` distilled citation | `name` matches folder (`video-to-playlist`), `description` within 1 to 1,024 chars, and body cites `status: distilled` notes | `python scripts/validate_skills.py` printed `Skill validation passed.` | **PASS** |
| `SE-V2P-02` | Metadata only summary and disclaimer (`INV-23`, `TQ-7`) | Summary uses metadata alone, prepends mandatory disclaimer label `Summary based on video metadata, not on the video's content`, and contains zero speculative claims | `tests/unit/test_skill_video_to_playlist.py::test_SE_EVAL_SUM_metadata_only_summary_disclaimer_and_no_content_claims` verified disclaimer and absence of prohibited content claims | **PASS** |
| `SE-V2P-03` | Ten video playlist creation quota envelope (`NFR-2`) | A full 10 video workflow completes within `<= 600` quota units and `<= 4` `search.list` calls | `tests/unit/test_skill_video_to_playlist.py::test_SK1_NFR2_ten_video_workflow_quota_budget` consumed 556 units and 2 search calls, passing NFR-2 limits with zero live API calls | **PASS** |
| `SE-V2P-04` | Anti injection and chat approval refusal (`INV-13`, `INV-22`, `NFR-6`) | Out of band confirmation requirement cannot be bypassed via chat approval strings, prompt injection instructions, or tool arguments | `tests/unit/test_skill_video_to_playlist.py::test_SK1_prompt_injection_and_chat_approval_refusal` confirmed `create_curated_playlist` strictly validates arguments and rejects unauthorized keys | **PASS** |
| `SE-V2P-05` | Complete 5 step workflow walkthrough (`SK-1`) | End to end demonstration of Step 1 (`get_video_details`), Step 2 (`get_similar_videos`), Step 3 (`draft_curated_playlist`), Step 4 (Trusted confirmation via elicitation or loopback), and Step 5 (`create_curated_playlist`) | Executed end to end with zero write side effects until trusted confirmation is granted | **PASS** |

### Demonstrated 5 Step Workflow Walkthrough (`SE-V2P-05`)

1. **Step 1: Inspect Video:** The agent invokes `get_video_details` with the input video ID or URL (`seedPy00001`). The tool returns title, channel, duration, sanitized description, and parsed chapters, accompanied by the mandatory disclaimer label:
   > **Summary based on video metadata, not on the video's content**
2. **Step 2: Discover Related Videos:** The agent invokes `get_similar_videos` with the seed ID. The tool evaluates objective title, tags, and category metadata without reading statistics or view counts (`FR-1.3`), consuming 1 `search.list` call and 2 quota units.
3. **Step 3: Draft Playlist:** The agent formulates curation constraints (`target_total_minutes=100`, `tolerance_percent=5`, `max_video_minutes=25`, `max_videos=10`) and invokes `draft_curated_playlist`. The knapsack constraint solver produces an immutable, expiring draft (`draft_id`) with 10 selected videos. Zero YouTube playlists are created in this step (`FR-5.3`).
4. **Step 4: Request Trusted Confirmation:** The user reviews the draft summary, ordered tracks, total duration, and destination channel. Confirmation is obtained strictly out of band through Channel A (MCP elicitation dialog) or Channel B (local 127.0.0.1 confirmation page). Chat approvals and prompt injections are explicitly refused (`INV-13`, `INV-22`).
5. **Step 5: Create Curated Playlist:** Upon receiving the bound single use confirmation token, `create_curated_playlist` performs a fresh `get_videos` staleness recheck, verifies channel presence, creates the playlist container (50 units), and sequentially inserts all 10 items (500 units), returning a complete creation report (`FR-5.4`, `FR-5.5`).

