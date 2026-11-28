---
title: Project Run and Activity Log
type: log
status: distilled
authors:
  - Team Whatsup
created: 2026-11-09
updated: 2026-11-27
tags:
  - log
  - audit
requirements:
  - "n/a"
issues:
  - "#1"
  - "#3"
  - "#9"
  - "#19"
  - "#27"
  - "#30"
  - "#32"
  - "#34"
  - "#36"
  - "#38"
  - "#40"
  - "#42"
  - "#44"
  - "#46"
  - "#48"
  - "#50"
  - "#52"
  - "#54"
  - "#56"
  - "#58"
  - "#60"
  - "#62"
  - "#64"
  - "#66"
  - "#68"
  - "#70"
  - "#72"
  - "#74"
  - "#76"
  - "#78"
  - "#80"
  - "#82"
  - "#84"
  - "#86"
  - "#88"
  - "#90"
  - "#92"
  - "#94"
prs:
  - "#10"
  - "#13"
  - "#18"
  - "#20"
  - "#29"
  - "#31"
  - "#33"
  - "#35"
  - "#37"
  - "#39"
  - "#41"
  - "#43"
  - "#45"
  - "#47"
  - "#49"
  - "#51"
  - "#53"
  - "#55"
  - "#57"
  - "#59"
  - "#61"
  - "#63"
  - "#65"
  - "#67"
  - "#69"
  - "#71"
  - "#73"
  - "#75"
  - "#77"
  - "#79"
  - "#81"
  - "#83"
  - "#85"
  - "#87"
  - "#89"
  - "#91"
  - "#93"
sources:
  - "Activity records for YouTube Video Intelligence MCP Server"
---

# Project Run and Activity Log

Requirements: n/a — activity log recording all project and brain operations.

| Timestamp | Actor | Action | Output / Notes |
|---|---|---|---|
| 2026-11-09 12:00 | Team Whatsup | Initialized Second Brain | Established PARA directory layout and index.md |
| 2026-11-09 12:38 | Molleti Tatwik Sai | Created brain-ingest skill | Created skills/brain-ingest/SKILL.md |
| 2026-11-09 12:40 | Molleti Tatwik Sai | Ingested Stage 1 Research Notes | Created 10 foundational research notes across resources/ and areas/ (deduplicated in TS-01) |
| 2026-11-23 12:20 | Molleti Tatwik Sai | TS-00 Workflow Bootstrap | Added dev plan, traceability matrix, AGENTS.md, templates (PR #10) |
| 2026-11-23 15:30 | Madire Shiva Reddy | SR-01 Package Skeleton | Added package skeleton, stdio server, and smoke tests (PR #11) |
| 2026-11-23 16:00 | Mohammed Farhan | MF-01 Validators | Added standalone skill and brain validators with fixtures (PR #12) |
| 2026-11-23 22:50 | Molleti Tatwik Sai | TS-01 Brain Alignment | Aligned all notes, index, log, and brain-ingest to SRS v1.0 schema (Issue #3, PR #13) |
| 2026-11-25 17:23 | Molleti Tatwik Sai | TS-02 Research Notes (brain-ingest) | Ingested `channel-similarity.md`, `youtube-event-timestamps.md`, `engagement-analysis.md`, `ai-session-2026-11-25-tatwik-TS-02.md` (Issue #6, PR #14) |
| 2026-11-25 17:45 | Madire Shiva Reddy | SR-02 Research Notes and Distillation (brain-ingest) | Ingested `nfr-targets.md`, `oauth-scopes-and-token-storage.md`, `ai-session-2026-11-25-shiva-SR-02.md`; distilled 4 infra notes (Issue #5, PR #15) |
| 2026-11-25 | Mohammed Farhan | MF-02 CI gates | [[brain/inbox/ai-session-2026-11-25-farhan-MF-02]] records the fixture-mode CI gates and failure verification (Issue #8, PR #16) |
| 2026-11-25 | Mohammed Farhan | MF-03 Playlist Research (brain-ingest) | Added [[brain/resources/mcp-elicitation-confirmation]], [[brain/projects/playlist-constraints]], [[brain/projects/partial-playlist-outcomes]], and [[brain/inbox/ai-session-2026-11-25-farhan-MF-03]]. Reviewed [[brain/areas/security/prompt-injection-defence]] (Issue #7, PR #17). |
| 2026-11-25 18:38 | Molleti Tatwik Sai | TS-03 Stage 1 Review and SB-1 Audit | Audited Stage 1 back-links, evaluated `brain-ingest`, resolved `G-09`, wrote `stage-1-review.md` and `CHANGELOG.md` (Issue #9, PR #18) |
| 2026-11-25 20:50 | Molleti Tatwik Sai | TS-05 Brain Refine Run (brain-refine) | Created `skills/brain-refine/SKILL.md` and [[brain/areas/skill-brain-refine]]; merged duplicate OAuth note into [[brain/resources/google-oauth-testing-mode]]; promoted 7 research notes to `brain/resources/` and `brain/projects/`; repaired wikilinks and added [[brain/inbox/ai-session-2026-11-25-tatwik-TS-05]] (Issue #19, PR #20) |
| 2026-11-25 | Mohammed Farhan | MF-05 Local Check | Added [[brain/areas/skill-local-check]] and recorded the verification in [[brain/inbox/ai-session-2026-11-25-farhan-MF-05]] (Issue #23, PR #24) |
| 2026-11-25 21:15 | Madire Shiva Reddy | SR-03 ADR-0001 Contract | Accepted Python 3.11+ / `mcp` SDK and `src/yt_intel_mcp/schemas/` in `docs/adr/0001-runtime-and-toolchain.md`; resolved `D-02` and `C-02`; added [[brain/inbox/ai-session-2026-11-25-shiva-SR-03]] (Issue #21, PR #22) |
| 2026-11-25 23:55 | Madire Shiva Reddy | SR-04 Shared Contracts Freeze | Froze `errors.py`, objective `models.py`, `config.py`, `YouTubeProvider`, `QuotaGuard`, and Stage 2 stubs; authored `docs/adr/0002-provider-and-errors.md` and `docs/developer/fixtures.md`; addressed PR #26 review updates (`search_unit_cost=0`, `ChannelMeta.keywords`, `get_channel_by_handle`, `duration_weight`/`keywords_weight`, `provider/live.py`); added [[brain/inbox/ai-session-2026-11-25-shiva-SR-04]] (Issue #25, PR #26) |
| 2026-11-26 01:42 | Molleti Tatwik Sai | TS-04 Analysis Design Contract | Authored 5 strict tool JSON Schemas (`NFR-5`) under `src/yt_intel_mcp/schemas/`, `docs/adr/0003-similarity-scoring.md`, `docs/adr/0007-interest-profile.md` (resolving `G-05`, `G-06`), `docs/architecture/analysis.md` (`SE-2`), and schema contract tests; logged `G-01` team vote in Issue #28; added [[brain/inbox/ai-session-2026-11-26-tatwik-TS-04]] (Issue #27, PR #29) |
| 2026-11-26 02:00 | Madire Shiva Reddy | SR-05 System Architecture and ADR-0006 | Authored `docs/architecture/overview.md` (`SE-2` component, deployment, SQLite ER for `quota_ledger`, `cache_entries`, and `first_observed`, quota preflight and OAuth read/write/revoke sequences) and `docs/adr/0006-token-storage-and-persistence.md` (OS keyring, AES-256-GCM fallback, WAL SQLite, delete on revoke); added [[brain/inbox/ai-session-2026-11-26-shiva-SR-05]] (Issue #30, PR #31) |
| 2026-11-26 02:15 | Madire Shiva Reddy | SR-06 Brain Query Skill (brain-query) | Authored `skills/brain-query/SKILL.md` (`SK-5`), [[brain/areas/skill-brain-query]], `SE-QRY-01`..`SE-QRY-04` evals with demonstrated vault draft in `docs/testing/skill-evals.md`, and [[brain/inbox/ai-session-2026-11-26-shiva-SR-06]] (Issue #32, PR #33) |
| 2026-11-26 11:12 | Mohammed Farhan | MF-04 Playlist Design Contract | Authored `draft_curated_playlist.json` and `create_curated_playlist.json` (`draft_id` only), `docs/adr/0004-trusted-confirmation.md` (resolving `G-02`), `docs/adr/0005-playlist-selection.md` (resolving `G-03`), `docs/architecture/playlist.md` (`SE-2`), contract tests, and [[brain/inbox/ai-session-2026-11-26-farhan-MF-04]] (Issue #34, PR #35) |
| 2026-11-26 12:14 | Mohammed Farhan | MF-06 Test Plan and Defect Log | Authored `docs/testing/test-plan.md` (full SRS test ID matrix, PR vs live CI plan, `NFR-1` benchmark protocol), `docs/testing/defect-log.md` (`TQ-8` template), traceability updates, and [[brain/inbox/ai-session-2026-11-26-farhan-MF-06]] (Issue #36, PR #37) |
| 2026-11-26 12:22 | Madire Shiva Reddy | SR-07 Stage 2 Review and SB-1 Audit | Audited Stage 2 `SB-1` back links and `SB-3` citations across all 7 ADRs and 4 skills, compiled Stage 2 evals in `docs/testing/skill-evals.md`, authored [[brain/projects/stage-2-review]], updated `CHANGELOG.md` for `v0.2.0` (`stage-2`), and added [[brain/inbox/ai-session-2026-11-26-shiva-SR-07]] (Issue #38, PR #39) |
| 2026-11-26 13:58 | Madire Shiva Reddy | SR-08 Fixture Provider and Scrubber | Implemented `src/yt_intel_mcp/provider/fixture.py`, `scripts/scrub_fixture.py`, scrubbed public and synthetic fixtures under `tests/fixtures/`, `IT_PROV` and `SEC_PII` tests, and [[brain/inbox/ai-session-2026-11-26-shiva-SR-08]] (Issue #40, PR #41) |
| 2026-11-26 16:15 | Madire Shiva Reddy | SR-09 MCP System Test Harness | Built `tests/system/conftest.py` (in memory and stdio MCP sessions, `FixtureYouTubeProvider`, temp WAL SQLite, toggleable elicitation simulation), `tests/system/test_harness.py`, `docs/developer/testing.md`, and [[brain/inbox/ai-session-2026-11-26-shiva-SR-09]] (Issue #42, PR #43) |
| 2026-11-26 18:26 | Madire Shiva Reddy | SR-10 Quota Ledger and Store | Implemented `src/yt_intel_mcp/store.py`, `src/yt_intel_mcp/quota/ledger.py`, `src/yt_intel_mcp/tools/get_quota_status.py` (`youtube://metrics/quota`), re-verified R-5 costs (`C-01`), added `UT_QUOTA` and `QT_1`..`QT_3` tests, and recorded [[brain/inbox/ai-session-2026-11-26-shiva-SR-10]] (Issue #44, PR #45) |
| 2026-11-26 18:55 | Madire Shiva Reddy | SR-11 TTL Metadata Cache | Implemented `src/yt_intel_mcp/cache.py` (`MetadataCache` and `CachedYouTubeProvider`) and `cache_entries` persistence in `store.py` (`24h`/`6h`/`15m` TTLs, `NFR-7` personal purge, `NFR-1` `<= 500 ms`, `QUOTA_EXHAUSTED_UPSTREAM` blocking), added `IT_CACHE` and `NT_QUOTA` tests, and recorded [[brain/inbox/ai-session-2026-11-26-shiva-SR-11]] (Issue #46, PR #47) |
| 2026-11-26 19:09 | Molleti Tatwik Sai | TS-06 ID and Bounds Validation | Replaced `validation/ids.py` stubs with strict `11` char video ID, `UC...`/`@handle`, playlist ID, allow listed YouTube URL host, and bounded range validators (`bounds.py`), updated `test_contracts.py`, added `UT_ID` (`tests/unit/test_validation_ids.py`) and `NT_VAL` (`tests/negative/test_input_validation.py`), and added [[brain/inbox/ai-session-2026-11-26-tatwik-TS-06]] (Issue #48, PR #49) |
| 2026-11-26 19:24 | Mohammed Farhan | MF-07 Metadata Sanitisation | Replaced `sanitize.py` stubs with `NFKC` normalization, invisible/bidi/tag/control char stripping, URL/Markdown link removal, `escape_html`, and `sanitize_video_meta`; updated `test_contracts.py`; added `tests/security/test_sanitize.py` and [[brain/inbox/ai-session-2026-11-26-farhan-MF-07]] (Issue #50, PR #51) |
| 2026-11-26 19:38 | Molleti Tatwik Sai | TS-07 ISO-8601 Durations | Implemented `src/yt_intel_mcp/durations.py` (`parse_iso8601_duration`, `parse_optional_duration`, `is_live_or_zero_duration`, `format_duration`, `format_duration_clock`, `format_iso8601_duration`), added `UT_DUR` unit tests in `tests/unit/test_durations.py`, and recorded [[brain/inbox/ai-session-2026-11-26-tatwik-TS-07]] (Issue #52, PR #53) |
| 2026-11-26 19:49 | Mohammed Farhan | MF-08 Playlist Constraint Model | Implemented `src/yt_intel_mcp/playlist/__init__.py` and `src/yt_intel_mcp/playlist/constraints.py` (`PlaylistConstraints`, `build_playlist_constraints`, `is_video_duration_eligible`, `is_total_in_window`, `evaluate_selection_constraints`), added `UT_SOLV_WINDOW` tests in `tests/unit/test_playlist_constraints.py`, updated traceability, and added [[brain/inbox/ai-session-2026-11-26-farhan-MF-08]] (Issue #54, PR #55) |
| 2026-11-26 20:33 | Molleti Tatwik Sai | TS-08 TF-IDF Cosine Engine | Implemented `src/yt_intel_mcp/similarity/__init__.py` and `src/yt_intel_mcp/similarity/text.py` (`tokenize_text`, `tokenize_tags`, `TfidfVectorizer`, `cosine_similarity`, `score_texts_cosine`, `extract_key_terms`, `build_search_query`, `shared_matched_terms`), added `UT_SIM` (`tests/unit/test_similarity.py`) and `X_PERF_SCORE` (`tests/perf/test_perf_budgets.py`), and added [[brain/inbox/ai-session-2026-11-26-tatwik-TS-08]] (Issue #56, PR #57) |
| 2026-11-26 20:45 | Mohammed Farhan | MF-09 Spoken Audio Language | Implemented `src/yt_intel_mcp/playlist/language.py` (`primary_language_subtag`, `evaluate_video_audio_language`, `is_video_language_eligible`, `filter_videos_by_language`, `UNVERIFIED_AUDIO_LANGUAGE_LABEL`) enforcing `defaultAudioLanguage`-only checks and ignoring `defaultLanguage`, added `UT_LANG` and `NT_LANG` tests, and added [[brain/inbox/ai-session-2026-11-26-farhan-MF-09]] (Issue #58, PR #59) |
| 2026-11-26 20:58 | Mohammed Farhan | MF-10 Constrained Playlist Solver | Implemented `src/yt_intel_mcp/playlist/solver.py` (`score_candidates_for_topic`, `solve_playlist_selection`, `PlaylistSolution`, `SelectedPlaylistVideo`) maximising TF IDF topic relevance over strict `FR-5.1` and `FR-5.1a` constraints within `<= 500 ms` for `200` candidates with rich `CONSTRAINTS_UNSATISFIABLE` diagnostics, added `UT_SOLV` and `X_PERF_SELECT` tests, and recorded [[brain/inbox/ai-session-2026-11-26-farhan-MF-10]] (Issue #60, PR #61) |
| 2026-11-26 21:24 | Mohammed Farhan | MF-11 Draft Tool and Expiring Drafts | Implemented `src/yt_intel_mcp/playlist/drafts.py` (`DraftVideo`, `PlaylistDraft`, `DraftStore`) and `src/yt_intel_mcp/tools/draft_curated_playlist.py` (`validate_draft_arguments`, `estimate_draft_workflow_cost`, `execute_draft_curated_playlist`, `register_draft_curated_playlist`), added unit, `ST_FR5`, `DRAFT_EXPIRED`, and `QT_3` tests, and recorded [[brain/inbox/ai-session-2026-11-26-farhan-MF-11]] (Issue #62, PR #63) |
| 2026-11-26 21:40 | Molleti Tatwik Sai | TS-09 get_video_details Tool | Implemented `src/yt_intel_mcp/tools/get_video_details.py` (`validate_get_video_details_arguments`, `parse_chapters_from_description`, `execute_get_video_details`, `register_get_video_details`) with `1 u` preflight, sanitization, live status, and human duration; added `tests/system/test_get_video_details.py`, `NT_VID` (`tests/negative/test_video_availability.py`), and [[brain/inbox/ai-session-2026-11-26-tatwik-TS-09]] (Issue #64, PR #65) |
| 2026-11-26 21:52 | Madire Shiva Reddy | SR-12 Encrypted Token Store | Implemented `src/yt_intel_mcp/auth/token_store.py` (OS keyring + `AES-256-GCM` `tokens.enc` fallback, `TokenBundle` redaction, revoke purge), `src/yt_intel_mcp/tools/get_auth_status.py`, `src/yt_intel_mcp/schemas/get_auth_status.json`, `SEC_OAUTH`, `SEC_PII` revoke test, and [[brain/inbox/ai-session-2026-11-26-shiva-SR-12]] (Issue #66, PR #67) |
| 2026-11-27 11:35 | Madire Shiva Reddy | SR-13 OAuth PKCE Flow and Channel Guard | Implemented RFC 7636 PKCE code verifier and S256 challenge generation, ephemeral 127.0.0.1 callback server, initial login requesting youtube.readonly only (C-6), separate full write consent requesting youtube.force-ssl (C-7, FR-7.1), silent token refresh mapping invalid_grant to AUTH_REAUTHORIZATION_REQUIRED (C-4), channel check raising CHANNEL_REQUIRED on writes (C-5, FR-7.3), tests in tests/security/test_oauth_security.py and tests/negative/test_oauth_errors.py, and [[brain/inbox/ai-session-2026-11-27-shiva-SR-13]] (Issue #68, PR #69) |
| 2026-11-27 12:00 | Mohammed Farhan | MF-12 Confirmation Tokens | Implemented src/yt_intel_mcp/confirmation/tokens.py (ConfirmationDecision, ConfirmationToken, ConfirmationTokenStore) bound to channel, draft, ordered videos, title, privacy, and expiry with single use consumption and zero token leakage; added NT_HITL tests in tests/negative/test_hitl_confirmation.py and unit tests in tests/unit/test_confirmation_tokens.py, and [[brain/inbox/ai-session-2026-11-27-farhan-MF-12]] (Issue #70, PR #71) |
| 2026-11-27 12:50 | Mohammed Farhan | MF-13 Trusted Confirmation Channels | Implemented MCP elicitation dialog channel with schema validation, local loopback confirmation page strictly bound to 127.0.0.1 with CSRF protection and CSP, NT_HITL adversarial tests, ST_FR5_CONFIRM system tests, and [[brain/inbox/ai-session-2026-11-27-farhan-MF-13]] (Issue #72, PR #73) |
| 2026-11-27 14:10 | Madire Shiva Reddy | SR-14 Live Provider | Implemented src/yt_intel_mcp/provider/live.py (LiveYouTubeProvider, UrllibLiveHttpTransport) with exponential backoff on reads (<=3 retries), zero write retries, strict exclusion of statistics, quota ledger charging, upstream error mapping, and IT_PROV integration tests in tests/integration/test_live_provider.py, and [[brain/inbox/ai-session-2026-11-27-shiva-SR-14]] (Issue #74, PR #75) |
| 2026-11-27 16:03 | Molleti Tatwik Sai | TS-10 get_similar_videos Tool | Implemented `src/yt_intel_mcp/similarity/videos.py` (`rank_similar_videos`, dynamic missing feature weight redistribution, MMR diversity) and `src/yt_intel_mcp/tools/get_similar_videos.py` (`<= 1s + 2u` preflight, objective metadata only) with `UT_SIM`, `ST_FR1`, and `NT_VID` tests, and recorded [[brain/inbox/ai-session-2026-11-27-tatwik-TS-10]] (Issue #76, PR #77) |
| 2026-11-27 17:15 | Mohammed Farhan | MF-14 Playlist Write Path and Outcome Reporting | Implemented `src/yt_intel_mcp/playlist/writer.py` (`write_curated_playlist`, `check_draft_staleness`) and `src/yt_intel_mcp/tools/create_curated_playlist.py` (9-step ADR-0004 pipeline) with 0 write retries, item failure continuation, `DRAFT_STALE` guard, `IT_DRAFT`, `IT_DRAFT_PARTIAL`, `NT_DRAFT_STALE`, and `ST_FR5` tests, and [[brain/inbox/ai-session-2026-11-27-farhan-MF-14]] (Issue #78, PR #79) |
| 2026-11-27 18:02 | Molleti Tatwik Sai | TS-12 Event Time Extraction and Interest Profile | Implemented `src/yt_intel_mcp/analysis/events.py` (`INV-04` event time extraction, `first_observed` provenance) and `src/yt_intel_mcp/analysis/profile.py` (90 day half life decay, `0.5` undated weight, cross source deduplication) with `UT_STAT_TS` and `UT_PROF` tests, and recorded [[brain/inbox/ai-session-2026-11-27-tatwik-TS-12]] (Issue #80, PR #81) |
| 2026-11-27 18:40 | Molleti Tatwik Sai | TS-13 get_recommendations Tool | Implemented `src/yt_intel_mcp/analysis/recommend.py` (`score_recommendations`, human reasons, MMR diversity) and `src/yt_intel_mcp/tools/get_recommendations.py` (`<= 3s + <= 25u` preflight, exclude seen videos, `INSUFFICIENT_USER_SIGNAL`) with `ST_FR3` and `NT_SIG` tests, and recorded [[brain/inbox/ai-session-2026-11-27-tatwik-TS-13]] (Issue #82, PR #83) |
| 2026-11-27 19:01 | Molleti Tatwik Sai | TS-14 analyze_engagement Tool and User Context | Implemented `src/yt_intel_mcp/analysis/engagement.py` (duration buckets, monthly trends, period comparisons, aggregate only serialization) and `src/yt_intel_mcp/tools/analyze_engagement.py` (`analyze_engagement` and `youtube://user/context`) with `UT_STAT_BUCKET`, `UT_STAT_ZERO`, `UT_STAT_TS`, `ST_FR4`, and `SEC_PII` tests, and recorded [[brain/inbox/ai-session-2026-11-27-tatwik-TS-14]] (Issue #84, PR #85) |
| 2026-11-28 12:31 | Molleti Tatwik Sai | TS-16 User Guide | Authored `docs/user/guide.md` (`SE-7`, `NFR-9`) covering installation, OAuth client and test user setup, 7 day reauthorization, MCP host connection, all tools and resources with examples and quota costs, trusted confirmation flow, privacy, and out of scope exclusions, and recorded [[brain/inbox/ai-session-2026-11-28-tatwik-TS-16]] (Issue #90, PR #91) |
| 2026-11-28 11:20 | Madire Shiva Reddy | SR-15 Server Integration | Wired AppConfig, SQLiteStore, PersistentQuotaLedger, TokenStore, DraftStore, ConfirmationTokenStore, CachedYouTubeProvider, and all 8 tools and 2 resources in src/yt_intel_mcp/server.py; added AST import boundary lint tests in tests/unit/test_import_lint.py, and [[brain/inbox/ai-session-2026-11-28-shiva-SR-15]] (Issue #86, PR #87) |
| 2026-11-28 12:15 | Mohammed Farhan | MF-15 video-to-playlist Product Skill | Authored skills/video-to-playlist/SKILL.md, [[brain/areas/skill-video-to-playlist]], SE-V2P-01..05 evals in docs/testing/skill-evals.md, unit tests in tests/unit/test_skill_video_to_playlist.py, and [[brain/inbox/ai-session-2026-11-28-farhan-MF-15]] (Issue #88, PR #89) |
| 2026-11-28 14:00 | Mohammed Farhan | MF-16 local-check Skill v2 | Wired Step 4 read-only fetch (get_video_details and get_quota_status) over MCP stdio, updated skills/local-check/SKILL.md, [[brain/areas/skill-local-check]], SE-LOCAL-04..06 in docs/testing/skill-evals.md, and [[brain/inbox/ai-session-2026-11-28-farhan-MF-16]] (Issue #92, PR #93) |
| 2026-11-28 14:30 | Madire Shiva Reddy | SR-17 Developer and Tool Reference Docs | Authored docs/developer/{setup,architecture,contributing}.md, implemented scripts/generate_tool_reference.py with CI drift check, generated docs/developer/tool-reference.md, added tests/unit/test_tool_reference.py, resolved C-03 in docs/plan/development-plan.md, and recorded [[brain/inbox/ai-session-2026-11-28-shiva-SR-17]] (Issue #94) |
