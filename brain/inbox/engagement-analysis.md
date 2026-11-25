---
title: Engagement Analysis Buckets, Period Comparisons and Privacy Aggregates
type: reference
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-25
updated: 2026-11-25
tags:
  - youtube
  - engagement
  - analytics
  - privacy
  - durations
requirements:
  - FR-4
  - FR-4.1
  - FR-4.2
  - FR-4.3
  - NFR-7
  - SB-1
  - SB-6
issues:
  - "#6"
prs: []
sources:
  - "Final_SRS_Submission.pdf Section 4.4 and 5 (checked 2026-11-25)"
  - "YouTube Data API v3 search.list videoDuration Filter: https://developers.google.com/youtube/v3/docs/search/list (checked 2026-11-25)"
---

# Engagement Analysis Buckets, Period Comparisons and Privacy Aggregates

## Summary
The `analyze_engagement` tool (`FR-4`) and `youtube://user/context` resource summarize a user explicit YouTube signals (likes, subscriptions, playlists) using aggregated statistics only. Strict boundary rules govern duration buckets, period comparison validity, and personal data privacy (`INV-07`, `INV-08`).

## Duration Buckets and Exclusions (`FR-4.1`, `INV-07`)
Video durations parsed from ISO 8601 `contentDetails.duration` are classified using YouTube Data API `search.list` `videoDuration` boundaries:
- **Short:** strictly less than 4 minutes (`duration_seconds < 240`; `239 s` is `short`).
- **Medium:** 4 to 20 minutes inclusive (`240 <= duration_seconds <= 1200`; both `240 s` and `1200 s` are `medium`).
- **Long:** strictly greater than 20 minutes (`duration_seconds > 1200`; `1201 s` is `long`).
- **Exclusions:** Live broadcasts and zero duration entries (`0 s` / `P0D`) are excluded from bucket counts and duration statistics.
- **Median Duration:** Calculated over remaining valid video durations and presented alongside human readable duration formatting (`NFR-9`).

## Monthly Trends and Period Comparisons (`FR-4.1`, `FR-4.2`)
- **Monthly Activity Counts:** Bucketed strictly by user action event time (`FR-3.1`, `INV-04`), never by video publication date.
- **Equal Length Period Comparison (`FR-4.2`):** Compares a selected period against the immediately preceding period of equal duration using **dated events only**:
  - Absolute change: $\Delta = \text{current} - \text{previous}$
  - Percentage change (when $\text{previous} > 0$):
    $$\text{pct} = \frac{\text{current} - \text{previous}}{\text{previous}} \times 100$$
  - **Zero Baseline Rules:**
    - If $\text{previous} = 0$ and $\text{current} > 0$: report `"new activity"` with no percentage figure.
    - If $\text{previous} = 0$ and $\text{current} = 0$: report `"no activity"`.
  - **Minimum Sample Guard:** If either period has fewer than 5 dated events (`< 5`), flag the comparison explicitly as `"insufficient data"` rather than reporting a trend.

## Privacy and Aggregates Only Invariant (`FR-4.3`, `NFR-7`, `INV-08`)
- Return aggregates only: top channels, top categories, monthly event counts, duration distribution, median duration, period comparison status, and per source coverage counts (`dated`, `undated`, `first_observed`).
- Never return raw personal lists of liked videos, channel subscriptions, or private playlist items in tool outputs or `youtube://user/context`.
- Explicitly state in the output that watch history is unavailable in the official YouTube Data API v3 (`FR-4.3`, Section 1.2).

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/second-brain|Second Brain Architecture]]
- [[brain/inbox/youtube-event-timestamps|YouTube Event Timestamps and Temporal Interest Weighting]]
- [[brain/inbox/channel-similarity|Channel Similarity Profiling and Ranking]]
