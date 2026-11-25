---
title: Local Check Skill (SK-2)
type: skill-note
status: distilled
authors:
  - Mohammed Farhan
created: 2026-11-25
updated: 2026-11-25
tags:
  - skills
  - verification
  - fixtures
requirements:
  - SK-2
  - SB-3
  - TQ-5
  - TQ-7
issues:
  - "#23"
prs: []
sources:
  - "Final_SRS_Submission.pdf v1.0, sections 4.9 and 6.1 (checked 2026-11-25)"
  - "MF-05 local execution on macOS with Python 3.14.2 (checked 2026-11-25)"
---

# Local Check Skill

## Summary

`local-check` gives developers one command to verify the current checkout. It builds a wheel, runs non-live tests, and initializes the normal MCP process over stdio. All checks run with `YT_INTEL_PROVIDER=fixture`.

## Verification boundary

- The wheel build checks packaging with the declared build backend and removes the temporary output. A package index may be needed for build dependencies.
- The tests and stdio process load the current checkout. MCP initialization verifies the server identity and tool discovery checks whether the read-only fetch is registered.
- MF-16 will exercise the fixture fetch itself. Until then the result includes `NOT RUN` and the reason. Tool discovery uses zero YouTube quota.
- The runner prints all five statuses and returns a nonzero exit status if a required check fails. The reported `PASS` count covers build, tests, and startup separately from the fetch step.

## Related notes

- [[brain/resources/fixture-testing-and-vcr|Fixture Testing and VCR]]
- [[brain/resources/mcp-protocol-specification|MCP Protocol Specification]]
- [[brain/inbox/ai-session-2026-11-25-farhan-MF-05|MF-05 implementation and evaluation]]
