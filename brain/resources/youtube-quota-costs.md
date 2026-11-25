---
title: YouTube Data API Quota Costs and Budgeting
type: reference
status: distilled
authors:
  - Molleti Tatwik Sai
  - Madire Shiva Reddy
created: 2026-11-09
updated: 2026-11-25
tags:
  - youtube
  - quota
  - api
  - performance
requirements:
  - C-2
  - FR-6
  - FR-6.1
  - FR-6.2
  - FR-6.3
  - NFR-2
  - TQ-6
  - SB-1
  - SB-6
issues:
  - "#1"
  - "#5"
prs:
  - "#10"
sources:
  - "YouTube Data API v3 Quota Cost Calculator: https://developers.google.com/youtube/v3/determine_quota_cost (checked 2026-11-25)"
  - "YouTube Data API v3 search.list Reference: https://developers.google.com/youtube/v3/docs/search/list (checked 2026-11-25)"
  - "Final_SRS_Submission.pdf Section 2.4, 3.2, 4.6, 5 (checked 2026-11-25)"
---

# YouTube Data API Quota Costs and Budgeting

## Summary
The YouTube Data API v3 enforces a default daily quota of `10,000` units per Google Cloud project (`C-2`), resetting at `00:00` Pacific Time (DST-aware `America/Los_Angeles`). Per SRS Section 3.2 and `C-2`, `yt-intel-mcp` tracks **both** the `10,000` units/day pool for standard/write endpoints and the dedicated `100` `search.list` calls/day search bucket (`1` call each, configurable so the legacy `100` unit/call model can also be applied). Extra Google Cloud projects are strictly prohibited (`C-2`).

## Quota Accounting Details (`SRS Section 3.2`)
Every request sent to the YouTube Data API v3 consumes quota regardless of whether it succeeds or fails (`FR-6.1`):

| Method | Resource / Use | Cost (SRS Section 3.2) | Notes |
|---|---|---|---|
| `videos.list` | Videos (`<= 50` IDs) | `1` unit per call | Never request `statistics` part (`FR-1.3`) |
| `channels.list` | Channels (`id` or `forHandle`) | `1` unit per call | Resolves `relatedPlaylists` (`likes`, `uploads`) |
| `subscriptions.list` | Subscriptions (`mine=true`) | `1` unit per page | Exposes `snippet.publishedAt` event time (`FR-3.1`) |
| `playlists.list` | User playlists (`mine=true`) | `1` unit per page | Lists saved playlists |
| `playlistItems.list` | Playlist items | `1` unit per page | Exposes `snippet.publishedAt` event time (`FR-3.1`) |
| `videoCategories.list` | Video categories | `1` unit per call | Category lookup metadata |
| `search.list` | Candidate videos/channels | `1` call from `100` calls/day search bucket | Configurable to `100` units/call per `C-2` |
| `playlists.insert` | Create playlist container | `50` units per call | Write operation; never auto-retried (`FR-5.5`) |
| `playlistItems.insert` | Add single video to playlist | `50` units per call | Write operation; `50` units per video inserted |

## Architectural Implications (`FR-6.1`–`FR-6.3`, `NFR-2`)
1. **Persistent Dual-Budget Ledger (`FR-6.1`):** Persist both daily counters (`units` and `search_calls`) locally with `00:00` Pacific Time daily reset and charge every dispatched request, including failed calls.
2. **Pre-Flight Verification (`FR-6.2`, `TQ-6`):** Before executing any API call, estimate total tool or workflow cost across both budgets. If either budget would be exceeded, reject immediately with `QUOTA_BUDGET_INSUFFICIENT` without calling the upstream API. Playlist creation workflows must include write costs (`50 + 50 per video`).
3. **Metadata Caching & Upstream Exhaustion (`FR-6.3`):** Cache video and channel metadata for `24 h`, search responses for `6 h`, and user lists for `15 min` (cache hits cost `0` quota). Treat an upstream `quotaExceeded` response (`QUOTA_EXHAUSTED_UPSTREAM`) as exhausted until the next `00:00` PT reset.
4. **Workflow Budget Cap (`NFR-2`):** A full `video-to-playlist` workflow for 10 videos must consume `<= 600` units and `<= 4` `search.list` calls; PR CI consumes `0` live quota via `FixtureYouTubeProvider`.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]
- [[brain/inbox/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
- [[brain/areas/second-brain|Second Brain Architecture]]
