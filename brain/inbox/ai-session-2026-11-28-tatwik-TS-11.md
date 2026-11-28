---
title: "AI Session TS-11 get_similar_channels Tool"
type: ai-session
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-28
updated: 2026-11-28
tags:
  - ai-session
  - similarity
  - tools
  - fr-2
requirements:
  - FR-2.1
  - FR-2.2
  - SB-1
issues:
  - "#100"
prs: []
sources:
  - "Final_SRS_Submission.pdf (v1.0)"
  - "docs/adr/0003-similarity-scoring.md"
---

# AI Session TS-11 `get_similar_channels` Tool

## Summary
Implemented `TS-11` (`FR-2.1`, `FR-2.2`, `INV-01`) on branch `tatwik/TS-11-similar-channels` (Issue `#100`).

- Added `src/yt_intel_mcp/similarity/channels.py` with `build_channel_profile`, `compute_topic_overlap`, and `rank_similar_channels` implementing `ADR-0003` channel weights (`0.25` topics, `0.20` keywords, `0.55` recent uploads), dynamic missing feature weight redistribution, deterministic `channel_id` tie breaking, and zero subscriber or view counts.
- Added `src/yt_intel_mcp/tools/get_similar_channels.py` resolving `UC...` IDs, `@handle`, and channel URLs (`G-01` Option A: `INVALID_ARGUMENT` when unresolved), preflighting `<= 1s + 32u`, and fetching recent uploads.
- Added unit tests `tests/unit/test_similarity_channels.py` (`UT_SIM`) and MCP system/negative tests `tests/system/test_get_similar_channels.py` (`ST_FR2`).

## Related Notes
- [[brain/resources/channel-similarity]]
- [[brain/inbox/ai-session-2026-11-27-tatwik-TS-10]]
