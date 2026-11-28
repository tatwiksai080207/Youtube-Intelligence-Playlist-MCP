---
title: "AI Session SR-16 Scheduled Live API Test Workflow"
type: ai-session
status: inbox
authors:
  - Madire Shiva Reddy
created: 2026-11-28
updated: 2026-11-28
tags:
  - ai-session
  - stage-3
  - ci
  - live-tests
requirements:
  - TQ-5
  - NFR-2
  - SB-1
issues:
  - "#108"
prs:
  - "#109"
sources:
  - "docs/testing/test-plan.md"
  - "docs/developer/testing.md"
  - "Final_SRS_Submission.pdf (v1.0)"
---

# AI Session SR-16 Scheduled Live API Test Workflow

## Summary
Completed task `SR-16` on branch `shiva/SR-16-live-workflow` (Issue `#108`).

- Added `.github/workflows/live.yml` with `schedule` (weekly cron) and `workflow_dispatch` triggers, strictly excluding PR and push triggers to maintain zero live quota consumption during pull requests (`TQ-5`, `NFR-2`).
- Enhanced `LiveTestConfig` with `to_quota_config()` and added `PersistentQuotaLedger.for_live_tests()` to enforce the hard per run ceiling of at most 300 quota units and at most 10 `search.list` calls.
- Updated `test_IT_PROV_opt_in_live_api_call` in `tests/integration/test_live_provider.py` to attach the live test quota guard.
- Authored dry run unit tests in `tests/unit/test_live_workflow.py` proving that both unit and search call budgets immediately abort with `ToolError(ErrorCode.QUOTA_BUDGET_INSUFFICIENT)` before dispatching any network calls.
- Updated `docs/traceability.md`, `brain/index.md`, and `brain/log.md`.

## Related Notes
- [[brain/resources/nfr-targets]]
- [[brain/inbox/ai-session-2026-11-27-shiva-SR-14]]
- [[brain/inbox/ai-session-2026-11-28-shiva-SR-18]]
