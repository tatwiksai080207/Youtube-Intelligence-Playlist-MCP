---
title: "AI Session TS-14 analyze_engagement Tool and youtube://user/context Resource"
type: ai-session
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-27
updated: 2026-11-27
tags:
  - ai-session
  - tools
  - engagement
  - fr-4
  - privacy
requirements:
  - FR-4.1
  - FR-4.2
  - FR-4.3
  - NFR-7
  - SB-1
issues:
  - "#84"
prs:
  - "#85"
sources:
  - "Final_SRS_Submission.pdf (v1.0)"
  - "docs/adr/0007-interest-profile.md"
---

# AI Session TS-14 `analyze_engagement` Tool and `youtube://user/context` Resource

## Summary
Implemented `TS-14` (`FR-4.1` through `FR-4.3`, `NFR-7`, `INV-07`, `INV-08`) on branch `tatwik/TS-14-engagement`.

- Added `src/yt_intel_mcp/analysis/engagement.py` with `classify_duration_bucket` (`<240s`, `240-1200s`, `>1200s`, excluding live and zero duration items), median duration, monthly trends over `DATED` events only, period comparison (`new_activity`, `no_activity`, `insufficient_dated_data` below 5 events, `compared`), watch history disclaimer, timestamp coverage, and aggregate only serialization.
- Added `src/yt_intel_mcp/tools/analyze_engagement.py` exposing `analyze_engagement` and the `youtube://user/context` MCP resource (`USER_CONTEXT_RESOURCE_URI`) with pre quota validation and zero search calls.
- Added unit tests `tests/unit/test_analysis_engagement.py` (`UT_STAT_BUCKET`, `UT_STAT_ZERO`, `UT_STAT_TS`) and MCP system/privacy tests `tests/system/test_analyze_engagement.py` (`ST_FR4`, `SEC_PII`).

## Related Notes
- [[brain/projects/engagement-analysis]]
- [[brain/resources/youtube-event-timestamps]]
- [[brain/inbox/ai-session-2026-11-27-tatwik-TS-12]]
- [[brain/inbox/ai-session-2026-11-27-tatwik-TS-13]]
