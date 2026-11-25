---
title: AI Session — MF-02 Required CI Checks
type: ai-session
status: inbox
authors:
  - Mohammed Farhan
created: 2026-11-25
updated: 2026-11-25
tags:
  - ai-session
  - ci
  - stage-1
requirements:
  - TQ-5
  - NFR-4
  - NFR-10
  - SB-1
issues:
  - "#8"
prs: []
sources:
  - "Final_SRS_Submission.pdf v1.0, sections 5 and 6.1 (checked 2026-11-25)"
  - "Local development session (2026-11-25)"
---

# AI Session — MF-02

- **Goal** Enforce lint, formatting, typing, fixture tests, coverage, and vault validators through the required `lint-and-validate` job. Retain Gitleaks.
- **AI tool** Codex drafted the workflow, traceability updates, session note, and temporary test used to verify the gate.
- **Human reviewers** Madire Shiva Reddy and Molleti Tatwik Sai.
- **Verification plan** Run the workflow commands locally. On the PR, show that a deliberately failing test fails the required job. Remove the test and verify green CI on the final commit.
- **Human changes** Pending author and reviewer review.
- **Related notes** [[brain/index|Second Brain Index]], [[brain/resources/fixture-testing-and-vcr|Fixture Testing and VCR]], and [[brain/inbox/ai-session-2026-11-23-farhan-MF-01|MF-01 Validators]].
