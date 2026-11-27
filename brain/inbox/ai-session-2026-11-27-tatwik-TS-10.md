---
title: "AI Session TS-10: get_similar_videos Tool and Objective Video Similarity"
type: ai-session
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-27
updated: 2026-11-27
tags:
  - ai-session
  - similarity
  - tools
  - fr-1
requirements:
  - FR-1.1
  - FR-1.2
  - FR-1.3
  - FR-1.4
  - NFR-1
  - NFR-5
  - NFR-6
  - SB-1
issues:
  - "#76"
prs:
  - "#77"
sources:
  - "Final_SRS_Submission.pdf (v1.0)"
  - "docs/adr/0003-similarity-scoring.md"
---

# AI Session TS-10: `get_similar_videos` Tool and Objective Video Similarity

## Summary
Implemented `TS-10` (`FR-1.1` through `FR-1.4`, `INV-01` through `INV-03`) on branch `tatwik/TS-10-similar-videos`.

- Added `src/yt_intel_mcp/similarity/videos.py` with `resolve_video_similarity_weights`, `is_eligible_candidate`, `compute_duration_similarity`, and `rank_similar_videos` implementing `ADR-0003` default weights (`0.35` title, `0.25` tags, `0.20` description, `0.10` category, `0.10` duration), dynamic missing feature weight redistribution, MMR diversity re ranking, and deterministic lexicographic `video_id` tie breaking without popularity signals.
- Added `src/yt_intel_mcp/tools/get_similar_videos.py` with strict pre quota validation (`INVALID_ARGUMENT`), worst case quota preflight (`<= 1s + 2u`), seed availability checks (`VIDEO_UNAVAILABLE`), search query synthesis via `build_search_query`, and sanitized per feature score breakdowns.
- Added unit tests (`tests/unit/test_similarity_videos.py`) and MCP system/negative tests (`tests/system/test_get_similar_videos.py`).

## Related Notes
- [[brain/resources/tfidf-cosine-similarity]]
- [[brain/resources/nfr-targets]]
- [[brain/inbox/ai-session-2026-11-26-tatwik-TS-08]]
- [[brain/inbox/ai-session-2026-11-26-tatwik-TS-09]]
