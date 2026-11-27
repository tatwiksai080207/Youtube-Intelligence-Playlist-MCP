---
title: "AI Session TS-13 get_recommendations Tool"
type: ai-session
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-27
updated: 2026-11-27
tags:
  - ai-session
  - tools
  - recommendations
  - fr-3
requirements:
  - FR-3.3
  - NFR-5
  - SB-1
issues:
  - "#82"
prs: []
sources:
  - "Final_SRS_Submission.pdf (v1.0)"
  - "docs/adr/0007-interest-profile.md"
---

# AI Session TS-13 `get_recommendations` Tool

## Summary
Implemented `TS-13` (`FR-3.3`, `INV-06`) on branch `tatwik/TS-13-recommendations`.

- Added `src/yt_intel_mcp/analysis/recommend.py` with `RecommendedVideo`, `RecommendationResult`, and `score_recommendations` to score candidates against an `InterestProfile`, exclude already liked or saved videos (`excluded_video_ids`) and unavailable/live items, apply deterministic MMR diversity, and attach human readable reasons per item without popularity signals.
- Added `src/yt_intel_mcp/tools/get_recommendations.py` with strict argument validation (`validate_get_recommendations_arguments`), bounded quota preflight (`<= 3s + <= 25u`), explicit signal collection across `liked_video`, `subscription`, and `playlist_item`, and `INSUFFICIENT_USER_SIGNAL` when no user signals exist.
- Added unit tests `tests/unit/test_analysis_recommend.py` and MCP system/negative tests `tests/system/test_get_recommendations.py` (`ST_FR3`, `NT_SIG`).

## Related Notes
- [[brain/resources/youtube-event-timestamps]]
- [[brain/inbox/ai-session-2026-11-27-tatwik-TS-12]]
