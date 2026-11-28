---
title: Second Brain Knowledge Index
type: index
status: distilled
authors:
  - Team Whatsup
created: 2026-11-09
updated: 2026-11-27
tags:
  - index
  - second-brain
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
  - "#96"
  - "#98"
  - "#100"
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
  - "#89"
  - "#91"
  - "#93"
  - "#95"
  - "#97"
  - "#99"
  - "#101"
  - "#103"
  - "#102"
  - "#106"
  - "#107"
sources:
  - "Course SDLC Specification (checked 2026-11-12)"
---

# Second Brain Knowledge Index

Requirements: n/a — central index of the Second Brain vault.

Welcome to the central knowledge vault for the YouTube Video Intelligence MCP Server project.

## Structure
- [[brain/inbox/|Inbox]]: Unsorted notes, incoming research, and AI session logs.
- [[brain/projects/youtube-mcp/|Active Projects]]: Project plans, reviews, and requirement notes.
- [[brain/areas/|Areas]]: Long term standards, engineering patterns, and security guidelines.
- [[brain/resources/|Resources]]: Reference materials, API quotas, and algorithms.
- [[brain/archive/|Archive]]: Inactive notes and completed milestones.

## Active Projects
- [[brain/projects/youtube-mcp/project-overview|YouTube MCP Project Overview]]: Goals, milestones, and active deadlines.
- [[brain/projects/stage-1-review|Stage 1 Review]]: Requirements baseline audit, skill evaluation summary, and process findings.
- [[brain/projects/stage-2-review|Stage 2 Review]]: Architecture, ADRs `0001`–`0007`, contracts, Stage 2 skill evals, and `SB-1` audit.
- [[brain/projects/stage-3-review|Stage 3 Review]]: Implementation and component verification audit across all 28 Stage 3 tasks, zero live quota assertion, and release preparation.
- [[brain/projects/stage-4-review|Stage 4 Review]]: Final audit summary, live demo readiness, and viva preparation (`TS-17`, Issue #102).
- [[brain/projects/engagement-analysis|Engagement Analysis Buckets, Period Comparisons and Privacy Aggregates]]: Duration buckets, comparison edge cases, and privacy rules for `FR-4`.
- [[brain/projects/playlist-constraints|Playlist Duration and Spoken Language Constraints]]: Duration boundaries and default audio language checks under `FR-5.1` and `FR-5.1a`.
- [[brain/projects/partial-playlist-outcomes|Playlist Writes and Partial Outcomes]]: Stale draft checks, ordered writes, and outcome reporting under `FR-5.5`.

## Core Architectural and Engineering Areas
- [[brain/areas/second-brain|Second Brain Architecture]]: Standards for note taking, PARA, and compliance.
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]: Dependency inversion for YouTube API.
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]: Defending against untrusted video metadata and enforcing human gates.
- [[brain/areas/skill-brain-refine|Skill Note: brain-refine]]: Design rationale, PARA placement rules, duplicate merging protocol, and `SK-4` evaluation targets.
- [[brain/areas/skill-brain-query|Skill Note: brain-query]]: Grounded vault Q&A, citation standards, refusal guard, and document drafting contract for `SK-5`.
- [[brain/areas/skill-local-check|Local Check Skill]]: Fixture-mode build, tests, stdio startup, and read-only fetch verification for `SK-2`.
- [[brain/areas/skill-video-to-playlist|Skill Note: video-to-playlist]]: Design rationale, 5-step workflow, metadata summary disclaimer, and evaluation criteria for `SK-1`.

## Technical Resources and Specifications
- [[brain/resources/youtube-quota-costs|YouTube API Quota Costs]]: Quota ledger, method pricing, and daily limit tracking.
- [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle]]: Testing mode 7 day expiration, PKCE flow, separate scopes, and encrypted token storage.
- [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]: Missing endpoints, channel presence, and watch history constraints.
- [[brain/resources/mcp-protocol-specification|MCP Protocol Specification]]: Model Context Protocol primitives and elicitation.
- [[brain/resources/tfidf-cosine-similarity|TF IDF and Cosine Similarity]]: Content similarity mathematics and objective metadata ranking.
- [[brain/resources/knapsack-constraint-solving|Knapsack Constraint Solving]]: Optimization models for duration bounded playlists.
- [[brain/resources/fixture-testing-and-vcr|Fixture Testing and VCR]]: Cassette replay and zero quota continuous integration.
- [[brain/resources/agent-skills-specification|Agent Skills Specification]]: Directory conventions and frontmatter validation for skills.
- [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]: Binding quantitative targets and upstream to MCP error mappings (`NFR-1`..`NFR-10`).
- [[brain/resources/channel-similarity|Channel Similarity Profiling and Ranking]]: Feature extraction and weighted cosine similarity for `FR-2`.
- [[brain/resources/youtube-event-timestamps|YouTube Event Timestamps and Temporal Interest Weighting]]: Event time fields, 90 day decay, and undated handling for `FR-3`.
- [[brain/resources/mcp-elicitation-confirmation|Trusted Playlist Confirmation with MCP Elicitation]]: Approval channels and server held token binding under `FR-5.4`.

## AI Assisted Development Sessions
- [[brain/inbox/ai-session-2026-11-23-shiva-SR-01|AI Session SR-01]]: Python package skeleton and stdio smoke test.
- [[brain/inbox/ai-session-2026-11-23-farhan-MF-01|AI Session MF-01]]: Standalone skill and brain validators.
- [[brain/inbox/ai-session-2026-11-23-tatwik-TS-01|AI Session TS-01]]: Align brain vault and skills to SRS v1.0.
- [[brain/inbox/ai-session-2026-11-25-shiva-SR-02|AI Session SR-02]]: Ingest `NFR` and `OAuth` notes via `brain-ingest` and distil 4 infrastructure notes.
- [[brain/inbox/ai-session-2026-11-25-farhan-MF-02|AI Session MF-02]]: Enforce fixture mode CI checks (Issue #8, PR #16).
- [[brain/inbox/ai-session-2026-11-25-tatwik-TS-02|AI Session TS-02]]: Ingest `FR-2`, `FR-3`, and `FR-4` research notes via `brain-ingest`.
- [[brain/inbox/ai-session-2026-11-25-farhan-MF-03|AI Session MF-03]]: Ingest the playlist research notes and review prompt injection defence (Issue #7, PR #17).
- [[brain/inbox/ai-session-2026-11-25-tatwik-TS-03|AI Session TS-03]]: Stage 1 review, `brain-ingest` evaluation, `SB-1` back link audit, and changelog (Issue #9, PR #18).
- [[brain/inbox/ai-session-2026-11-25-tatwik-TS-05|AI Session TS-05]]: Author `brain-refine` (`SK-4`), merge duplicate OAuth note, promote Stage 1 notes into PARA, and repair vault links (Issue #19, PR #20).
- [[brain/inbox/ai-session-2026-11-25-farhan-MF-05|AI Session MF-05]]: Build and run the fixture-mode local checks (Issue #23, PR #24).
- [[brain/inbox/ai-session-2026-11-25-shiva-SR-03|AI Session SR-03]]: Accept ADR-0001 runtime, official `mcp` SDK, toolchain, and `src/yt_intel_mcp/schemas/` path (Issue #21, PR #22).
- [[brain/inbox/ai-session-2026-11-25-shiva-SR-04|AI Session SR-04]]: Freeze shared v1.0 contracts (`CT-1`), protocols, config defaults, stubs, fixture guide, and ADR-0002 (Issue #25, PR #26).
- [[brain/inbox/ai-session-2026-11-26-tatwik-TS-04|AI Session TS-04]]: Author strict `FR-1..FR-4` tool JSON Schemas, `ADR-0003`, `ADR-0007`, analysis architecture diagrams, and Decision `G-01` (Issue #27, Issue #28, PR #29).
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-05|AI Session SR-05]]: Author system architecture overview, deployment/ER/sequence diagrams, and `ADR-0006` for encrypted token storage and WAL SQLite persistence (Issue #30, PR #31).
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-06|AI Session SR-06]]: Author `brain-query` (`SK-5`) skill, distilled skill note, and vault grounded draft evaluations (Issue #32, PR #33).
- [[brain/inbox/ai-session-2026-11-26-farhan-MF-04|AI Session MF-04]]: Author strict playlist JSON Schemas (`NFR-5`), `ADR-0004` (`G-02`), `ADR-0005` (`G-03`), and `docs/architecture/playlist.md` diagrams (Issue #34, PR #35).
- [[brain/inbox/ai-session-2026-11-26-farhan-MF-06|AI Session MF-06]]: Author master test plan, PR vs live CI plan, `NFR-1` benchmark method, and `TQ-8` defect log template (Issue #36, PR #37).
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-07|AI Session SR-07]]: Compile Stage 2 skill evaluations, audit `SB-1` back links, author `stage-2-review.md`, and prepare `v0.2.0` (`stage-2`) release changelog (Issue #38, PR #39).
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-08|AI Session SR-08]]: Implement `FixtureYouTubeProvider`, `scripts/scrub_fixture.py`, scrubbed public and synthetic user fixtures, and `IT_PROV`/`SEC_PII` tests (Issue #40, PR #41).
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-09|AI Session SR-09]]: Build MCP end to end system test harness (`tests/system/conftest.py`, `tests/system/test_harness.py`) and `docs/developer/testing.md` (Issue #42, PR #43).
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-10|AI Session SR-10]]: Implement `store.py`, `quota/ledger.py`, `get_quota_status` tool and `youtube://metrics/quota` resource, `UT_QUOTA`, and `QT_1`..`QT_3` tests (Issue #44, PR #45).
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-11|AI Session SR-11]]: Implement `cache.py` (`MetadataCache`, `CachedYouTubeProvider`), `IT_CACHE`, and `NT_QUOTA` tests (Issue #46, PR #47).
- [[brain/inbox/ai-session-2026-11-26-tatwik-TS-06|AI Session TS-06]]: Implement strict YouTube video, channel, playlist, URL host, and range bounds validation with `UT_ID` and `NT_VAL` tests (Issue #48, PR #49).
- [[brain/inbox/ai-session-2026-11-26-farhan-MF-07|AI Session MF-07]]: Implement `sanitize.py` (`NFKC`, invisible/bidi/tag/control char stripping, URL/Markdown link stripping, HTML escaping, `sanitize_video_meta`) with adversarial tests in `tests/security/test_sanitize.py` (Issue #50, PR #51).
- [[brain/inbox/ai-session-2026-11-26-tatwik-TS-07|AI Session TS-07]]: Implement ISO-8601 duration parsing (`PT#H#M#S`, `P#DT...`, `P0D`), live/zero detection, and human readable formatting with `UT_DUR` unit tests (Issue #52, PR #53).
- [[brain/inbox/ai-session-2026-11-26-farhan-MF-08|AI Session MF-08]]: Implement `playlist/constraints.py` (`PlaylistConstraints`, `build_playlist_constraints`, exact `Decimal` window `[T*(1-tol), T]`, inclusive `max_video_minutes`, upper bound `max_videos`) with `UT_SOLV_WINDOW` tests (Issue #54, PR #55).
- [[brain/inbox/ai-session-2026-11-26-tatwik-TS-08|AI Session TS-08]]: Implement `similarity/text.py` (`TfidfVectorizer`, sublinear TF IDF, bounded `cosine_similarity`, query/overlap helpers) with `UT_SIM` and `X_PERF_SCORE` tests (Issue #56, PR #57).
- [[brain/inbox/ai-session-2026-11-26-farhan-MF-09|AI Session MF-09]]: Implement `playlist/language.py` (`defaultAudioLanguage`-only primary subtag filter, ignoring `defaultLanguage`, `"Audio language unverified"` opt in) with `UT_LANG` and `NT_LANG` tests (Issue #58, PR #59).
- [[brain/inbox/ai-session-2026-11-26-farhan-MF-10|AI Session MF-10]]: Implement `playlist/solver.py` (TF IDF relevance maximizing constrained solver within 500 ms for 200 candidates, deterministic tie breaking, rich `CONSTRAINTS_UNSATISFIABLE` diagnostics) with `UT_SOLV` and `X_PERF_SELECT` tests (Issue #60, PR #61).
- [[brain/inbox/ai-session-2026-11-26-farhan-MF-11|AI Session MF-11]]: Implement `playlist/drafts.py` (`PlaylistDraft`, `DraftStore` 10m TTL) and `tools/draft_curated_playlist.py` (`G-03` workflow preflight, zero writes) with `ST_FR5`, `DRAFT_EXPIRED`, and `QT_3` tests (Issue #62, PR #63).
- [[brain/inbox/ai-session-2026-11-26-tatwik-TS-09|AI Session TS-09]]: Implement `tools/get_video_details.py` (`1 u` preflight, chapter parsing, sanitized objective metadata, human duration, `VIDEO_UNAVAILABLE`) with MCP system and `NT_VID` negative tests (Issue #64, PR #65).
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-12|AI Session SR-12]]: Implement `auth/token_store.py` (OS keyring + `AES-256-GCM` fallback, revoke purge), `tools/get_auth_status.py`, `schemas/get_auth_status.json`, `SEC_OAUTH`, and `SEC_PII` revoke test (Issue #66, PR #67).
- [[brain/inbox/ai-session-2026-11-27-shiva-SR-13|AI Session SR-13]]: Implement OAuth PKCE flow, loopback listener, separate write consent (`youtube.force-ssl`), silent refresh (`invalid_grant`), and channel check (Issue #68, PR #69).
- [[brain/inbox/ai-session-2026-11-27-farhan-MF-12|AI Session MF-12]]: Implement server held confirmation tokens, draft binding, single use consumption, and NT_HITL tests (Issue #70, PR #71).
- [[brain/inbox/ai-session-2026-11-27-farhan-MF-13|AI Session MF-13]]: Implement MCP elicitation and local loopback confirmation channels (Issue #72, PR #73).
- [[brain/inbox/ai-session-2026-11-27-shiva-SR-14|AI Session SR-14]]: Implement live YouTube Data API v3 provider with retry policies, zero write retries, quota tracking, error mapping, and IT_PROV tests (Issue #74, PR #75).
- [[brain/inbox/ai-session-2026-11-27-tatwik-TS-10|AI Session TS-10]]: Implement `similarity/videos.py` and `tools/get_similar_videos.py` (`ADR-0003` weights, dynamic missing feature redistribution, MMR diversity, `<= 1s + 2u` preflight, zero popularity signals) with `UT_SIM`, `ST_FR1`, and `NT_VID` tests (Issue #76, PR #77).
- [[brain/inbox/ai-session-2026-11-27-farhan-MF-14|AI Session MF-14]]: Implement confirmed playlist creation write path, zero write retries, item error continuation, and COMPLETE/PARTIAL outcome reporting (Issue #78, PR #79).
- [[brain/inbox/ai-session-2026-11-27-tatwik-TS-12|AI Session TS-12]]: Implement `analysis/events.py` (`INV-04` event time extraction, `first_observed` policy) and `analysis/profile.py` (90 day half life decay, neutral `0.5` undated weight) with `UT_STAT_TS` and `UT_PROF` tests (Issue #80, PR #81).
- [[brain/inbox/ai-session-2026-11-27-tatwik-TS-13|AI Session TS-13]]: Implement `analysis/recommend.py` and `tools/get_recommendations.py` (`<= 3s + <= 25u` preflight, exclude liked/saved videos, human reasons, `INSUFFICIENT_USER_SIGNAL`) with `ST_FR3` and `NT_SIG` tests (Issue #82, PR #83).
- [[brain/inbox/ai-session-2026-11-27-tatwik-TS-14|AI Session TS-14]]: Implement `analysis/engagement.py`, `tools/analyze_engagement.py`, and `youtube://user/context` (duration buckets, monthly trends, period comparison, timestamp coverage, aggregates only) with `UT_STAT_BUCKET`, `UT_STAT_ZERO`, `UT_STAT_TS`, `ST_FR4`, and `SEC_PII` tests (Issue #84, PR #85).
- [[brain/inbox/ai-session-2026-11-28-shiva-SR-15|AI Session SR-15]]: Implement MCP server runtime integration, tool registration, and provider boundary import-lint tests (Issue #86, PR #87).
- [[brain/inbox/ai-session-2026-11-28-tatwik-TS-16|AI Session TS-16]]: Author `docs/user/guide.md` covering installation, OAuth setup, MCP host connection, tools, trusted confirmation, 7 day reauthorization, privacy, and exclusions (Issue #90, PR #91).
- [[brain/inbox/ai-session-2026-11-28-farhan-MF-15|AI Session MF-15]]: Implement video-to-playlist product skill and evaluations for `SK-1` (Issue #88, PR #89).
- [[brain/inbox/ai-session-2026-11-28-farhan-MF-16|AI Session MF-16]]: Upgrade local-check skill to v2 with read-only fetch and zero live quota (Issue #92, PR #93).
- [[brain/inbox/ai-session-2026-11-28-shiva-SR-17|AI Session SR-17]]: Author developer guides (setup, architecture, contributing) and tool reference generator with CI drift check (Issue #94, PR #95).
- [[brain/inbox/ai-session-2026-11-28-farhan-MF-17|AI Session MF-17]]: Execute Stage 3 review, CI results audit, defect verification, and v0.3.0 stage-3 release changelog (Issue #96, PR #97).
- [[brain/inbox/ai-session-2026-11-28-tatwik-TS-11|AI Session TS-11]]: Implement `similarity/channels.py` and `tools/get_similar_channels.py` (`ADR-0003` weights, `G-01` Option A `INVALID_ARGUMENT`, `<= 1s + 32u` preflight, zero subscriber counts) with `UT_SIM` and `ST_FR2` tests (Issue #100, PR #101).
- [[brain/inbox/ai-session-2026-11-28-farhan-MF-18|AI Session MF-18]]: Execute Stage 4 final quality and compliance audit across all SRS and SDLC gates (Issue #98, PR #99).
- [[brain/inbox/ai-session-2026-11-28-tatwik-TS-17|AI Session TS-17]]: Author docs/demo/stage-4-checklist.md, record rehearsal and viva ownership, and write brain/projects/stage-4-review.md (Issue #102, PR #103).
- [[brain/inbox/ai-session-2026-11-28-shiva-SR-18|AI Session SR-18]]: Finalize traceability matrix audit, resolve Decision Register gaps (G-01, G-04), and prepare v1.0.0 release changelog (Issue #104, PR #105).
- [[brain/inbox/ai-session-2026-11-28-tatwik-TS-15|AI Session TS-15]]: Verify stdio MCP tool/resource discovery, `get_video_details` read call, elicitation fallback, and local CLI host observations in `docs/testing/host-compatibility.md` (Issue #106, PR #107).
- [[brain/inbox/ai-session-2026-11-28-shiva-SR-16|AI Session SR-16]]: Implement scheduled live API test workflow with hard quota cap and budget abort dry run tests (Issue #108).

## Logs and Reviews
- [[brain/log|Activity Log]]: Chronological records of project runs and AI sessions.
