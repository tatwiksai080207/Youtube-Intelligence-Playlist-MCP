---
title: Second Brain Knowledge Index
type: index
status: distilled
authors:
  - Team Whatsup
created: 2026-11-09
updated: 2026-11-25
tags:
  - index
  - second-brain
requirements:
  - "n/a"
issues:
  - "#1"
  - "#3"
  - "#9"
prs:
  - "#10"
  - "#13"
  - "#18"
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

## Core Architectural and Engineering Areas
- [[brain/areas/second-brain|Second Brain Architecture]]: Standards for note taking, PARA, and compliance.
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]: Dependency inversion for YouTube API.
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]: Defending against untrusted video metadata and enforcing human gates.

## Technical Resources and Specifications
- [[brain/resources/youtube-quota-costs|YouTube API Quota Costs]]: Quota ledger, method pricing, and daily limit tracking.
- [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle]]: Testing mode 7 day expiration and PKCE flow.
- [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]: Missing endpoints, channel presence, and watch history constraints.
- [[brain/resources/mcp-protocol-specification|MCP Protocol Specification]]: Model Context Protocol primitives and elicitation.
- [[brain/resources/tfidf-cosine-similarity|TF IDF and Cosine Similarity]]: Content similarity mathematics and objective metadata ranking.
- [[brain/resources/knapsack-constraint-solving|Knapsack Constraint Solving]]: Optimization models for duration bounded playlists.
- [[brain/resources/fixture-testing-and-vcr|Fixture Testing and VCR]]: Cassette replay and zero quota continuous integration.
- [[brain/resources/agent-skills-specification|Agent Skills Specification]]: Directory conventions and frontmatter validation for skills.

## Inbox Research Notes (Pending Refinement in TS-05)
- [[brain/inbox/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]: Binding quantitative targets and upstream-to-MCP error mappings (`NFR-1`..`NFR-10`).
- [[brain/inbox/oauth-scopes-and-token-storage|OAuth Scopes, PKCE and Encrypted Token Storage]]: Least-privilege scopes, no incremental auth (`C-7`), PKCE loopback, and encrypted storage (`FR-7`).
- [[brain/inbox/channel-similarity|Channel Similarity Profiling and Ranking]]: Feature extraction and weighted cosine similarity for `FR-2`.
- [[brain/inbox/youtube-event-timestamps|YouTube Event Timestamps and Temporal Interest Weighting]]: Event time fields, 90 day decay, and undated handling for `FR-3`.
- [[brain/inbox/engagement-analysis|Engagement Analysis Buckets, Period Comparisons and Privacy Aggregates]]: Duration buckets, comparison edge cases, and privacy rules for `FR-4`.
- [[brain/inbox/mcp-elicitation-confirmation|Trusted Playlist Confirmation with MCP Elicitation]]: Approval channels and server-held token binding under `FR-5.4`.
- [[brain/inbox/playlist-constraints|Playlist Duration and Spoken Language Constraints]]: Duration boundaries and default audio language checks under `FR-5.1` and `FR-5.1a`.
- [[brain/inbox/partial-playlist-outcomes|Playlist Writes and Partial Outcomes]]: Stale drafts, ordered writes, and outcome reporting under `FR-5.5`.

## AI Assisted Development Sessions
- [[brain/inbox/ai-session-2026-11-23-shiva-SR-01|AI Session SR-01]]: Python package skeleton and stdio smoke test.
- [[brain/inbox/ai-session-2026-11-23-farhan-MF-01|AI Session MF-01]]: Standalone skill and brain validators.
- [[brain/inbox/ai-session-2026-11-23-tatwik-TS-01|AI Session TS-01]]: Align brain vault and skills to SRS v1.0.
- [[brain/inbox/ai-session-2026-11-25-shiva-SR-02|AI Session SR-02]]: Ingest `NFR` and `OAuth` notes via `brain-ingest` and distil 4 infrastructure notes.
- [[brain/inbox/ai-session-2026-11-25-farhan-MF-02|AI Session MF-02]]: Enforce fixture-mode CI checks (Issue #8, PR #16).
- [[brain/inbox/ai-session-2026-11-25-tatwik-TS-02|AI Session TS-02]]: Ingest `FR-2`, `FR-3`, and `FR-4` research notes via `brain-ingest`.
- [[brain/inbox/ai-session-2026-11-25-farhan-MF-03|AI Session MF-03]]: Ingest the playlist research notes and review prompt-injection defence (Issue #7, PR #17).
- [[brain/inbox/ai-session-2026-11-25-tatwik-TS-03|AI Session TS-03]]: Stage 1 review, `brain-ingest` evaluation, `SB-1` back-link audit, and changelog (Issue #9, PR #18).

## Logs and Reviews
- [[brain/log|Activity Log]]: Chronological records of project runs and AI sessions.
