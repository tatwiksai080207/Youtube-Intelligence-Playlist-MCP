---
title: Second Brain Knowledge Index
type: index
status: distilled
authors:
  - Team Whatsup
created: 2026-11-09
updated: 2026-11-26
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
- [[brain/projects/engagement-analysis|Engagement Analysis Buckets, Period Comparisons and Privacy Aggregates]]: Duration buckets, comparison edge cases, and privacy rules for `FR-4`.
- [[brain/projects/playlist-constraints|Playlist Duration and Spoken Language Constraints]]: Duration boundaries and default audio language checks under `FR-5.1` and `FR-5.1a`.
- [[brain/projects/partial-playlist-outcomes|Playlist Writes and Partial Outcomes]]: Stale draft checks, ordered writes, and outcome reporting under `FR-5.5`.

## Core Architectural and Engineering Areas
- [[brain/areas/second-brain|Second Brain Architecture]]: Standards for note taking, PARA, and compliance.
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]: Dependency inversion for YouTube API.
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]: Defending against untrusted video metadata and enforcing human gates.
- [[brain/areas/skill-brain-refine|Skill Note: brain-refine]]: Design rationale, PARA placement rules, duplicate merging protocol, and `SK-4` evaluation targets.
- [[brain/areas/skill-brain-query|Skill Note: brain-query]]: Grounded vault Q&A, citation standards, refusal guard, and document drafting contract for `SK-5`.
- [[brain/areas/skill-local-check|Local Check Skill]]: Fixture-mode build, tests, and MCP startup verification for `SK-2`.

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
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-10|AI Session SR-10]]: Implement `store.py`, `quota/ledger.py`, `get_quota_status` tool and `youtube://metrics/quota` resource, `UT_QUOTA`, and `QT_1`..`QT_3` tests (Issue #44).

## Logs and Reviews
- [[brain/log|Activity Log]]: Chronological records of project runs and AI sessions.
