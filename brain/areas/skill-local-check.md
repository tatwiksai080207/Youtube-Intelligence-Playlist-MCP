---
title: Local Check Skill (SK-2)
type: skill-note
status: distilled
authors:
  - Mohammed Farhan
created: 2026-11-25
updated: 2026-11-28
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
  - "#92"
prs:
  - "#24"
  - "#93"
sources:
  - "Final_SRS_Submission.pdf v1.0, sections 4.9 and 6.1 (checked 2026-11-25)"
  - "MF-05 local execution on macOS with Python 3.14.2 (checked 2026-11-25)"
  - "MF-16 local execution on Windows 11 with Python 3.11 (checked 2026-11-28)"
---

# Local Check Skill

## Summary

`local-check` gives developers one command to verify the current checkout. It builds a wheel, runs non-live tests, initializes the normal MCP process over stdio, and invokes read-only fixture tools (`get_video_details` and `get_quota_status`). All checks run with `YT_INTEL_PROVIDER=fixture` using zero live YouTube API units.

## Verification boundary

- The wheel build checks packaging with the declared build backend and removes the temporary output. A package index may be needed for build dependencies.
- The tests and stdio process load the current checkout. MCP initialization verifies the server identity, while Step 4 invokes both `get_video_details` with sample fixture data and `get_quota_status` to verify quota ledger operations.
- The runner reports all five steps (`Build project`, `Run automated tests`, `Start MCP server`, `Read-only fetch`, and `Summary`). On a clean checkout, all steps report `PASS`.
- Any failure in packaging, testing, handshake, or tool execution returns a nonzero exit status with diagnostic messages.

## Related notes

- [[brain/resources/fixture-testing-and-vcr|Fixture Testing and VCR]]
- [[brain/resources/mcp-protocol-specification|MCP Protocol Specification]]
- [[brain/inbox/ai-session-2026-11-25-farhan-MF-05|MF-05 implementation and evaluation]]
- [[brain/inbox/ai-session-2026-11-28-farhan-MF-16|MF-16 implementation and evaluation]]
