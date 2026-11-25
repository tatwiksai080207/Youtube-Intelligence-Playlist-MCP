---
title: "Skill Note: brain-query (SK-5)"
type: skill-note
status: distilled
authors:
  - Madire Shiva Reddy
created: 2026-11-26
updated: 2026-11-26
tags:
  - skills
  - second-brain
  - query
  - citations
  - drafting
  - sdlc
requirements:
  - SK-5
  - SB-1
  - SB-3
  - SB-6
  - TQ-7
issues:
  - "#32"
prs: []
sources:
  - "Final_SRS_Submission.pdf Section 4.9 SK-5 (checked 2026-11-26)"
  - "SDLC Specification Section 1 and Section 3 (checked 2026-11-26)"
  - "Second Brain Vault Inspection across resources/ and areas/ (checked 2026-11-26)"
---

# Skill Note: brain-query (SK-5)

## Summary
The `brain-query` Agent Skill (`skills/brain-query/SKILL.md`, requirement `SK-5`) provides grounded retrieval and technical document drafting over the `brain/` PARA vault. It enforces inline `[[wikilink]]` citations for every claim, distinguishes `status: distilled` notes from `status: inbox` logs, and refuses to guess whenever requested details are absent from the vault.

## Design Rationale and Retrieval Safeguards
1. **Index First Navigation (`brain/index.md`):** Queries start from [[brain/index|Second Brain Index]] so agents discover canonical `resources/`, `projects/`, and `areas/` notes reliably instead of skimming arbitrary filenames or relying on stale inbox drafts.
2. **Distilled Priority (`SB-3`):** Document drafting (SRS clauses, ADRs, and developer specifications) must cite `status: distilled` notes such as [[brain/resources/youtube-quota-costs|YouTube Data API Quota Costs and Budgeting]], [[brain/resources/google-oauth-testing-mode|Google OAuth Lifecycle in Testing Publishing Status]], [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]], and [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern and Dependency Inversion]].
3. **Mandatory Refusal on Vault Gaps:** LLMs tend to extrapolate missing API limits or configuration values from pretraining memory. `brain-query` prohibits ungrounded completion: any fact absent from `brain/` triggers an explicit `Not found in the Second Brain vault` refusal (for queries) or `[MISSING FROM VAULT]` marker (for drafts), pointing the author back to `brain-ingest` (`SK-3`) and `Final_SRS_Submission.pdf`.
4. **Traceability and Non Mutation (`SB-1`, `SB-5`):** Read queries never alter vault notes; drafted artifacts merge through Pull Requests with real Issue and PR back links.

## Evaluation and Demonstrated Draft (`TQ-7`)
Stage 2 evaluation cases (`SE-QRY-01` through `SE-QRY-04`) and a complete vault grounded drafted specification section (covering YouTube Data API quota preflight and OAuth testing boundaries) are recorded in `docs/testing/skill-evals.md`.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/second-brain|Second Brain Architecture]]
- [[brain/resources/agent-skills-specification|Agent Skills Specification]]
- [[brain/areas/skill-brain-refine|Skill Note: brain-refine]]
- [[brain/inbox/ai-session-2026-11-26-shiva-SR-06|AI Session SR-06]]
