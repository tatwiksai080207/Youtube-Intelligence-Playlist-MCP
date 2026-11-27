---
title: "AI Session TS-12 Event-Time Extraction and Half-Life Interest Profile"
type: ai-session
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-27
updated: 2026-11-27
tags:
  - ai-session
  - analysis
  - profile
  - fr-3
requirements:
  - FR-3.1
  - FR-3.2
  - SB-1
issues:
  - "#80"
prs: []
sources:
  - "Final_SRS_Submission.pdf (v1.0)"
  - "docs/adr/0007-interest-profile.md"
---

# AI Session TS-12 Event-Time Extraction and Half-Life Interest Profile

## Summary
Implemented `TS-12` (`FR-3.1`, `FR-3.2`, `INV-04`, `INV-05`) on branch `tatwik/TS-12-event-profile`.

- Added `src/yt_intel_mcp/analysis/events.py` with `extract_event_time_from_record`, `events_from_liked_videos`, `normalize_user_event`, `normalize_user_events`, and `summarize_timestamp_coverage`, strictly rejecting `videos.snippet.publishedAt` and `playlistItems.contentDetails.videoPublishedAt` (`INV-04`) and persisting undated sightings in `first_observed` (`ADR-0007` `G-05`).
- Added `src/yt_intel_mcp/analysis/profile.py` with `compute_event_weight`, `deduplicate_events`, and `build_interest_profile`, applying 90 day half life decay for `DATED` events, fixed `0.5` weight for `UNDATED` and `FIRST_OBSERVED` (`G-06`), cross source max weight deduplication, and `INSUFFICIENT_USER_SIGNAL` when empty (`INV-06`).
- Added unit tests `tests/unit/test_analysis_events.py` (`UT_STAT_TS`) and `tests/unit/test_analysis_profile.py` (`UT_PROF`).

## Related Notes
- [[brain/resources/youtube-event-timestamps]]
- [[brain/projects/engagement-analysis]]
- [[brain/inbox/ai-session-2026-11-27-tatwik-TS-10]]
