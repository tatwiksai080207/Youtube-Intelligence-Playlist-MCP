---
title: "Skill Note: brain-refine (SK-4)"
type: skill-note
status: distilled
authors:
  - Molleti Tatwik Sai
created: 2026-11-25
updated: 2026-11-25
tags:
  - skills
  - second-brain
  - para
  - refinement
  - sdlc
requirements:
  - SK-4
  - SB-1
  - SB-2
  - SB-3
  - SB-4
  - SB-5
  - SB-6
  - TQ-7
issues:
  - "#19"
prs:
  - "#20"
sources:
  - "Final_SRS_Submission.pdf Section 4.9 (checked 2026-11-25)"
  - "The AI Assisted Software Development Life Cycle (SDLC) Section 1 and Section 3 (checked 2026-11-25)"
  - "Course Task Roadmap Stage 2 TS-05 Specification (checked 2026-11-25)"
---

# Skill Note: brain-refine (SK-4)

## Summary
The `brain-refine` Agent Skill (`skills/brain-refine/SKILL.md`, requirement `SK-4`) standardizes the transition of raw research ingested into `brain/inbox/` into durable, `status: distilled` PARA knowledge notes. It governs duplicate consolidation, PARA folder placement, YAML frontmatter updates, vault wide `[[wikilink]]` repair, `brain/index.md` reorganization, and `docs/traceability.md` cleanup.

## Design Rationale and PARA Placement Rules
1. **Separating Research Notes from Session Logs:** Technical research notes ingested via `brain-ingest` start in `brain/inbox/` with `status: inbox` for rapid parallel contribution (`SB-6`). Once verified against SRS v1.0, they belong in canonical PARA directories while `ai-session-*.md` records remain inside `brain/inbox/` as chronological development logs.
2. **PARA Classification Criteria:**
   - **`brain/resources/`** holds enduring technical specifications, API contracts, protocol flows, and scoring algorithms reused across components (such as `channel-similarity`, `youtube-event-timestamps`, `mcp-elicitation-confirmation`, and `nfr-targets`).
   - **`brain/projects/`** holds feature scoped implementation constraints and deliverable oriented specifications (such as `engagement-analysis`, `playlist-constraints`, `partial-playlist-outcomes`, and stage reviews).
   - **`brain/areas/`** holds cross cutting engineering standards, security patterns, and `skill-*.md` design notes.
   - **`brain/archive/`** holds completed milestones or retired materials kept for auditability.
3. **Duplicate Merging Protocol:** When multiple Stage 1 tasks produce overlapping notes on the same topic, `brain-refine` merges all unique details into the established canonical note instead of promoting duplicate files. In the first refinement run (`TS-05`), `brain/inbox/oauth-scopes-and-token-storage.md` was merged into [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle in Testing Publishing Status]] while preserving PKCE `S256` details, `get_auth_status` scope reporting boundaries, `ADR-0006` storage references, and all `#5` and `#15` back links (`SB-1`).

## Verification and Quality Gate (`TQ-7`)
- Every skill run must pass `scripts/validate_skills.py` and `scripts/validate_brain.py` with zero broken wikilinks (`SB-1`), valid SRS IDs from `scripts/srs_ids.txt`, and explicit distilled citations (`SB-3`).
- Stage 2 evaluation cases (`SE-REF-01` through `SE-REF-04`) are tracked in `docs/testing/skill-evals.md` and exercised during `TS-05` (`#19`).

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/second-brain|Second Brain Architecture]]
- [[brain/resources/agent-skills-specification|Agent Skills Specification]]
- [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle in Testing Publishing Status]]
- [[brain/inbox/ai-session-2026-11-25-tatwik-TS-05|AI Session TS-05]]
