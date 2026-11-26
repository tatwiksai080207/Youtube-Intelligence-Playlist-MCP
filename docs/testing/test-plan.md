# Master Test Plan, CI Plan, and Verification Matrix (`MF-06`)

- **Task:** `MF-06`
- **Owner:** Mohammed Farhan (`@farhan4599`)
- **Reviewer:** Madire Shiva Reddy (`@Shiva0025`)
- **GitHub Issue:** `#36`
- **GitHub PR:** `#37`
- **Requirements:** `TQ-1`, `TQ-2`, `TQ-3`, `TQ-4`, `TQ-5`, `TQ-6`, `TQ-7`, `TQ-8`, `SEC`, `NFR-1`..`NFR-10`, `SE-5`, `SB-1`
- **Baseline:** `Final_SRS_Submission.pdf` (version 1.0, Sections 5 and 6)

## 1. Testing Strategy and Scope Boundaries

All automated verification enforces the product invariants (`INV-01`..`INV-24`) and process baselines (`SE-6`, `TQ-1`..`TQ-8`, `SEC`):

1. **Zero Live Quota in PR CI (`TQ-5`, `NFR-2`):** Pull Request CI runs strictly with `YT_INTEL_PROVIDER=fixture` against scrubbed public fixtures and synthetic user library fixtures (`docs/developer/fixtures.md`), consuming `0` live YouTube API quota and requiring zero network credentials.
2. **Provider Isolation Enforcement (`SE-6`, `INV-18`, `NFR-10`):** Only `provider/live.py` and `auth/oauth.py` may import HTTP or Google client libraries, enforced via an automated AST import boundary test (`SR-15`).
3. **Coverage and Static Quality Gates (`NFR-10`):** Minimum `85%` branch and statement coverage (`pytest --cov=yt_intel_mcp --cov-fail-under=85`), clean `ruff check .` and `ruff format --check .`, strict `mypy src`, `gitleaks` secret scanning, and Second Brain / Agent Skill validators (`scripts/validate_skills.py`, `scripts/validate_brain.py`).
4. **Regression Discipline (`TQ-8`):** Every real defect discovered during implementation, host compatibility, or CI must receive a `type:defect` GitHub Issue, a regression test that fails prior to the fix and passes afterward, and an entry in `docs/testing/defect-log.md`.

## 2. Complete SRS Test ID Mapping (`TQ-1`..`TQ-8`, `SEC`, `NFR-1`..`NFR-10`)

### 2.1 Unit Tests (`TQ-1` and Stage 1/2 Contract Suites)

| SRS Test ID | Suite | Target Test File | Owner | Task | Requirement / Invariant Covered |
|---|---|---|---|---|---|
| `UT_ID` | `unit` | `tests/unit/test_validation_ids.py` | Tatwik | `TS-06` | `FR-1.1`, `FR-2.1`, `NFR-5`, `INV-02` (11 char IDs, URL host allow list, `UC...` IDs, `@handle`) |
| `UT_DUR` | `unit` | `tests/unit/test_durations.py` | Tatwik | `TS-07` | `FR-4.1`, `FR-5.1`, `FR-5.2`, `NFR-9` (`PT#H#M#S`, `P#DT...`, `P0D` zero/live, human format) |
| `UT_SIM` | `unit` | `tests/unit/test_similarity.py` | Tatwik | `TS-08`, `TS-10`, `TS-11` | `FR-1.2`, `FR-1.3`, `FR-2.2`, `INV-01`, `INV-03` (TF IDF cosine, popularity invariance, tag redistribution, channel profile) |
| `UT_SOLV_WINDOW` | `unit` | `tests/unit/test_playlist_constraints.py` | Farhan | `MF-08` | `FR-5.1`, `INV-09` (`[T*(1-tol), T]` endpoints e.g. `114:00`..`120:00`, `113:59`/`120:01` rejected, inclusive `max_video_minutes`) |
| `UT_LANG` | `unit` | `tests/unit/test_playlist_language.py` | Farhan | `MF-09` | `FR-5.1a`, `INV-10` (primary subtag match on `defaultAudioLanguage` only, opt in `"Audio language unverified"`) |
| `UT_SOLV` | `unit` | `tests/unit/test_playlist_solver.py` | Farhan | `MF-10` | `FR-5.2`, `INV-09`, `INV-11` (relevance maximization, deterministic tie break, rich `CONSTRAINTS_UNSATISFIABLE`) |
| `UT_PROF` | `unit` | `tests/unit/test_profile.py` | Tatwik | `TS-12` | `FR-3.1`, `FR-3.2`, `INV-04`, `INV-05` (90 day half life decay, neutral `0.5` undated weight, `first_observed`) |
| `UT_STAT_TS` | `unit` | `tests/unit/test_events.py`, `tests/unit/test_engagement.py` | Tatwik | `TS-12`, `TS-14` | `FR-3.1`, `FR-3.2`, `FR-4.3`, `INV-04`, `INV-08` (event time provenance only, never upload dates, coverage counts) |
| `UT_STAT_BUCKET` | `unit` | `tests/unit/test_engagement.py` | Tatwik | `TS-14` | `FR-4.1`, `INV-07` (`<240s`, `240..1200s` inclusive, `>1200s` buckets, boundaries `239/240/1200/1201s`, median) |
| `UT_STAT_ZERO` | `unit` | `tests/unit/test_engagement.py` | Tatwik | `TS-14` | `FR-4.2`, `INV-07` (`"new activity"`, `"no activity"`, `<5` dated events `"insufficient data"` flag) |
| `UT_QUOTA` | `unit` | `tests/unit/test_quota_ledger.py` | Shiva | `SR-10` | `FR-6.1`, `C-2`, `INV-19` (persistent WAL ledger, dual budgets, `00:00` PT DST reset, charge failures) |
| `CT_1` / `NFR_5` | `unit` | `tests/unit/test_contracts.py`, `test_analysis_schemas.py`, `test_playlist_schemas.py` | Shiva / Tatwik / Farhan | `SR-04`, `TS-04`, `MF-04` | `FR-8.1`, `NFR-5`, `NFR-9`, `INV-01`, `INV-13`, `INV-14` (17 `ErrorCode`s, upstream mapping, strict JSON Schemas, `draft_id` only) |
| `TQ_1` / `TQ_4` (CLI) | `unit` | `tests/unit/test_validators.py`, `test_local_check.py`, `test_smoke.py` | Farhan / Shiva | `MF-01`, `MF-05`, `SR-01` | `SB-1`, `SB-3`, `SK-2`, `NFR-10` (validators, `local_check.py`, stdio server initialization) |

### 2.2 Integration Tests (`TQ-2`)

| SRS Test ID | Suite | Target Test File | Owner | Task | Requirement / Invariant Covered |
|---|---|---|---|---|---|
| `IT_PROV` | `integration` | `tests/integration/test_fixture_provider.py`, `test_live_provider.py`, `test_import_boundary.py` | Shiva | `SR-08`, `SR-14`, `SR-15` | `FR-8.1`, `NFR-8`, `NFR-10`, `INV-18`, `INV-24` (fixture/live parity, read retries `<= 3`, write retries `0`, no `statistics`, AST import lint) |
| `IT_CACHE` | `integration` | `tests/integration/test_cache.py` | Shiva | `SR-11` | `FR-6.3`, `NFR-1`, `NFR-7` (`24h`/`6h`/`15m` TTLs, `0` quota cache hit, `<= 500 ms` latency, revoke purge) |
| `IT_DRAFT` | `integration` | `tests/integration/test_playlist_writer.py` | Farhan | `MF-14` | `FR-5.5`, `NFR-8`, `INV-16`, `INV-17`, `INV-24` (`playlists.insert` private + ordered `playlistItems.insert`, `0` retries, `COMPLETE`) |
| `IT_DRAFT_PARTIAL` | `integration` | `tests/integration/test_playlist_writer.py` | Farhan | `MF-14` | `FR-5.5`, `NFR-8`, `INV-16`, `INV-17` (continue after item failure, stop immediately on quota/auth errors, `PARTIAL` report fields) |

### 2.3 System / MCP End to End Tests (`TQ-3`)

| SRS Test ID | Suite | Target Test File | Owner | Task | Requirement / Invariant Covered |
|---|---|---|---|---|---|
| `ST_FR1` | `system` | `tests/system/test_fr1_similar_videos.py` | Tatwik | `TS-09`, `TS-10` | `FR-1.1`..`FR-1.4`, `SK-1`, `INV-01`..`INV-03` (`get_video_details` and `get_similar_videos` over MCP stdio) |
| `ST_FR2` | `system` | `tests/system/test_fr2_similar_channels.py` | Tatwik | `TS-11` | `FR-2.1`, `FR-2.2`, `INV-01` (`get_similar_channels` over MCP stdio, subscriber invariance) |
| `ST_FR3` | `system` | `tests/system/test_fr3_recommendations.py` | Tatwik | `TS-13` | `FR-3.1`..`FR-3.3`, `INV-04`..`INV-06` (`get_recommendations` with reasons and library exclusion) |
| `ST_FR4` | `system` | `tests/system/test_fr4_engagement.py` | Tatwik | `TS-14` | `FR-4.1`..`FR-4.3`, `NFR-7`, `INV-07`, `INV-08` (`analyze_engagement` and `youtube://user/context` aggregates) |
| `ST_FR5` | `system` | `tests/system/test_fr5_playlist.py` | Farhan | `MF-11`, `MF-14` | `FR-5.1`..`FR-5.5`, `INV-09`..`INV-17` (`draft_curated_playlist` immutability, zero writes, confirmed creation) |
| `ST_FR5_CONFIRM` | `system` | `tests/system/test_fr5_confirmation.py` | Farhan | `MF-13` | `FR-5.4`, `INV-13`, `INV-14` (MCP `elicitation` dialog and `127.0.0.1` loopback HTML/POST confirmation flow) |

*(Shared MCP client/server harness and fixture wiring reside in `tests/system/conftest.py`, built in `SR-09`.)*

### 2.4 Negative Tests (`TQ-4`)

| SRS Test ID | Suite | Target Test File | Owner | Task | Requirement / Invariant Covered |
|---|---|---|---|---|---|
| `NT_VAL` | `negative` | `tests/negative/test_input_validation.py` | Tatwik | `TS-06` | `FR-1.1`, `FR-2.1`, `NFR-5`, `INV-02` (malformed IDs, rejected hosts, out of range bounds -> `INVALID_ARGUMENT`, 0 calls) |
| `NT_VID` | `negative` | `tests/negative/test_video_availability.py` | Tatwik | `TS-09`, `TS-10` | `FR-1.4`, `INV-03` (private, deleted, live videos excluded or returning `VIDEO_UNAVAILABLE`) |
| `NT_SIG` | `negative` | `tests/negative/test_user_signals.py` | Tatwik | `TS-13` | `FR-3.3`, `INV-06` (empty explicit signal history -> `INSUFFICIENT_USER_SIGNAL`) |
| `NT_LANG` | `negative` | `tests/negative/test_language_conflicts.py` | Farhan | `MF-09` | `FR-5.1a`, `INV-10` (conflicting `defaultLanguage` vs `defaultAudioLanguage`, missing audio excluded by default) |
| `NT_HITL` | `negative` | `tests/negative/test_hitl_confirmation.py` | Farhan | `MF-07`, `MF-12`, `MF-13` | `FR-5.4`, `NFR-6`, `INV-13`, `INV-14`, `INV-22` (`CONFIRMATION_MISMATCH`, `DRAFT_EXPIRED`, `CONFIRMATION_REUSED`, `CONFIRMATION_DECLINED`, prompt injection rejection, hidden token) |
| `NT_HITL_UNAVAIL` | `negative` | `tests/negative/test_hitl_confirmation.py` | Farhan | `MF-13` | `FR-5.4`, `INV-13` (no elicitation and no loopback UI -> `CONFIRMATION_UNAVAILABLE`, zero writes) |
| `NT_DRAFT_STALE` | `negative` | `tests/negative/test_draft_stale.py` | Farhan | `MF-14` | `FR-5.5(1)`, `INV-15` (stale/changed video pre write -> `DRAFT_STALE`, zero writes) |
| `NT_QUOTA` | `negative` | `tests/negative/test_quota_upstream.py` | Shiva | `SR-11` | `FR-6.3`, `NFR-8`, `INV-19` (upstream `quotaExceeded` -> `QUOTA_EXHAUSTED_UPSTREAM` until `00:00` PT reset) |
| `NT_AUTH` | `negative` | `tests/negative/test_oauth_errors.py` | Shiva | `SR-13` | `FR-7.1`, `FR-7.2`, `C-4`, `C-7`, `INV-20` (`invalid_grant` -> `AUTH_REAUTHORIZATION_REQUIRED`, missing write scope -> `SCOPE_INSUFFICIENT`) |
| `NT_ACC` | `negative` | `tests/negative/test_oauth_errors.py` | Shiva | `SR-13` | `FR-7.3`, `C-5`, `INV-20` (`youtubeSignupRequired` -> `CHANNEL_REQUIRED` on writes while reads succeed) |

### 2.5 Quota (`TQ-6`), Security (`SEC`), Performance (`NFR-1`), Skill Evals (`TQ-7`), and Regression (`TQ-8`)

| SRS Test ID | Suite | Target Test File / Artifact | Owner | Task | Requirement / Invariant Covered |
|---|---|---|---|---|---|
| `QT_1` | `quota` | `tests/quota/test_quota_preflight.py` | Shiva | `SR-10` | `FR-6.2`, `NFR-2`, `INV-19` (unit budget insufficient -> `QUOTA_BUDGET_INSUFFICIENT`, 0 provider calls) |
| `QT_2` | `quota` | `tests/quota/test_quota_preflight.py` | Shiva | `SR-10` | `FR-6.2`, `C-2`, `INV-19` (`search.list` call budget insufficient -> `QUOTA_BUDGET_INSUFFICIENT`, 0 calls) |
| `QT_3` | `quota` | `tests/quota/test_quota_preflight.py` | Shiva / Farhan | `SR-10`, `MF-11`, `MF-14` | `FR-6.2`, `NFR-2`, `INV-19`, `G-02`, `G-03` (playlist workflow preflight includes `50 + 50/video`, 0 calls on failure) |
| `SEC_OAUTH` | `security` | `tests/security/test_oauth_security.py` | Shiva | `SR-12`, `SR-13` | `FR-7.1`, `FR-7.2`, `NFR-3`, `INV-20` (minimum scopes, keyring/`AES-256-GCM`, zero plaintext tokens on disk or logs) |
| `SEC_PII` | `security` | `tests/security/test_pii_and_fixtures.py` | Shiva / Tatwik | `SR-08`, `SR-12`, `TS-14` | `FR-4.3`, `FR-8.2`, `NFR-4`, `NFR-7`, `INV-08`, `INV-21` (scrubbed fixtures, zero PII/tokens, aggregates only, revoke purge) |
| `NFR_6` (sanitize) | `security` | `tests/security/test_sanitize.py` | Farhan | `MF-07` | `NFR-6`, `INV-22` (NFKC, bidi/invisible control strip, URL/link removal, HTML escaping, length limits) |
| `X_PERF_SCORE` | `perf` | `tests/perf/test_perf_budgets.py` | Tatwik | `TS-08` | `NFR-1`, `FR-1.2` (`150` candidate similarity scoring `<= 150 ms`) |
| `X_PERF_SELECT` | `perf` | `tests/perf/test_perf_budgets.py` | Farhan | `MF-10` | `NFR-1`, `FR-5.2`, `ADR-0005` (`200` candidate playlist solver `<= 500 ms`) |
| `SE_EVAL_SUM` | `unit` / `skill-eval` | `tests/unit/test_skill_video_to_playlist.py`, `docs/testing/skill-evals.md` | Farhan | `MF-15` | `SK-1`, `TQ-7`, `NFR-2`, `INV-23` (metadata only summary label + 10 video run `<= 600 u`, `<= 4` searches) |
| `TQ-7` (all skills) | `skill-eval` | `docs/testing/skill-evals.md` | All | `TS-03`, `SR-07`, `MF-17` | `SK-1`..`SK-5` (`SE-ING-*`, `SE-REF-*`, `SE-LOCAL-*`, `SE-QRY-*`, `SE_EVAL_SUM`) |
| `TQ-8` | `regression` | `docs/testing/defect-log.md` and targeted `tests/` | Fixer | `MF-06`, ongoing | Every logged `type:defect` issue carries a failing before / passing after regression test |

## 3. PR CI vs. Scheduled Live Test Plan (`TQ-5`, `NFR-2`)

| Aspect | PR & Push CI (`.github/workflows/ci.yml`) | Scheduled / Manual Live Smoke CI (`.github/workflows/live.yml`, `SR-16`) |
|---|---|---|
| **Triggers** | `push` and `pull_request` targeting `main` or `develop` | `schedule` and `workflow_dispatch` only (NEVER triggered on PRs) |
| **Runner OS** | `ubuntu-latest`, Python `3.11` | `ubuntu-latest`, Python `3.11` |
| **Provider Mode** | `YT_INTEL_PROVIDER=fixture` (mandatory) | `YT_INTEL_PROVIDER=live` (read only smoke checks) |
| **Live API Quota** | `0` units, `0` search calls | Hard preflight and abort ceiling: `<= 300` units and `<= 10` `search.list` calls per run (`LiveTestConfig`) |
| **Credentials** | None (`gitleaks` enforces zero secrets in repo) | GitHub Actions Secrets (`G-04`), refreshed weekly per Google Testing mode `7` day token expiry (`C-4`) |
| **Commands Executed** | `gitleaks`, `ruff check .`, `ruff format --check .`, `mypy src`, `pytest -m "not live" --cov=yt_intel_mcp --cov-fail-under=85`, `python scripts/validate_skills.py`, `python scripts/validate_brain.py` | `pytest -m live` (dry run budget abort tested offline in `SR-16`) |
| **Platform Note** | Linux CI runs all `test_validators.py` assertions cleanly (`55/55`); Windows local runs observe `28` pre existing POSIX `/` vs `\` stderr path mismatches (`docs/testing/skill-evals.md`) while `validate_brain.py` and `validate_skills.py` CLIs pass natively on both OSes | Live tests avoid destructive playlist operations per `SRS Section 1.2` |

## 4. Performance Measurement Method (`NFR-1`)

Performance assertions (`X_PERF_SCORE`, `X_PERF_SELECT`, `IT_CACHE`) run deterministically in offline fixture mode (`YT_INTEL_PROVIDER=fixture`) so CI timing stays reproducible without network jitter:

1. **Synthetic Workload Construction:**
   - `X_PERF_SCORE` (`TS-08`): Generate `150` deterministic `VideoMeta` candidates with varied titles, tags, descriptions (`<= 500` chars), categories, and durations alongside one seed `VideoMeta`.
   - `X_PERF_SELECT` (`MF-10`): Generate `200` deterministic candidate videos spanning diverse durations (`60 s` to `1200 s`), relevance scores, and `defaultAudioLanguage` tags for a `120` minute (`5%` tolerance) target window (`max_videos = 25`).
   - `IT_CACHE` (`SR-11`): Populate local SQLite WAL cache (`<tmp_path>/yt_intel.db`) and measure end to end cache lookup and response assembly with `0` provider calls.
2. **Timing Protocol:**
   - Perform `1` warm up pass to initialize Python regex/SQLite prepared state, then measure `5` consecutive iterations using `time.perf_counter()` (converting elapsed duration to milliseconds).
   - Assert **median** and **worst observed run** (or `95th` percentile across batches) stay strictly within target thresholds with headroom (`<= 150 ms` for `X_PERF_SCORE`, `<= 500 ms` for `X_PERF_SELECT` and `IT_CACHE`).
   - Keep `tests/perf/` under `-m "not live"` so every PR verifies performance budgets automatically on CI runners.
