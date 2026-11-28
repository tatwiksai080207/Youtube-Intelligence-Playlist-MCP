---
title: "AI Session TS-17 Stage 4 Live Demo Checklist, Rehearsal, and Review"
type: ai-session
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-28
updated: 2026-11-28
tags:
  - ai-session
  - stage-4
  - demo
  - viva
requirements:
  - SB-1
  - SB-2
  - NFR-9
issues:
  - "#102"
prs:
  - "#103"
sources:
  - "docs/testing/ci-results.md"
  - "SDLC_and_Workflow.pdf Sections 6 and 7 Stage 4"
---

# AI Session TS-17 Stage 4 Live Demo Checklist, Rehearsal, and Review

## Summary
Completed `TS-17` on branch `tatwik/TS-17-stage4-demo` (Issue `#102`).

- Authored `docs/demo/stage-4-checklist.md` covering live `FR-1` through `FR-5`, `video-to-playlist` (`SK-1`) with trusted confirmation, `local-check` (`SK-2`), `brain-query` (`SK-5`), the end to end traceability walkthrough (`[[brain/resources/tfidf-cosine-similarity]]` -> `ADR-0003` -> `similarity/videos.py` -> `test_UT_SIM_*`), quota pre check with explicit fixture fallback, viva speaking ownership for all 3 teammates, and rehearsal verification.
- Authored `brain/projects/stage-4-review.md` (`SB-2`) summarizing Stage 4 audit readiness and `SR-18` handoff.

## Related Notes
- [[brain/projects/stage-4-review]]
- [[brain/projects/stage-3-review]]
- [[brain/resources/tfidf-cosine-similarity]]
