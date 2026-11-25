---
title: YouTube Event Timestamps and Temporal Interest Weighting
type: reference
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-25
updated: 2026-11-25
tags:
  - youtube
  - timestamps
  - recommendations
  - decay
  - privacy
requirements:
  - FR-3
  - FR-3.1
  - FR-3.2
  - FR-3.3
  - FR-4.3
  - SB-1
  - SB-6
issues:
  - "#6"
prs: []
sources:
  - "Final_SRS_Submission.pdf Section 4.3 and 4.4 (checked 2026-11-25)"
  - "YouTube Data API v3 PlaylistItems Resource: https://developers.google.com/youtube/v3/docs/playlistItems (checked 2026-11-25)"
  - "YouTube Data API v3 Subscriptions Resource: https://developers.google.com/youtube/v3/docs/subscriptions (checked 2026-11-25)"
  - "YouTube Data API v3 Videos Resource: https://developers.google.com/youtube/v3/docs/videos (checked 2026-11-25)"
---

# YouTube Event Timestamps and Temporal Interest Weighting

## Summary
For personalized recommendations (`FR-3`) and engagement trend analysis (`FR-4`), user interest signals must be weighted and grouped strictly by **user action event time** rather than when a video was originally uploaded. Items lacking an action timestamp are weighted neutrally and explicitly reported as `undated` (`INV-04`, `INV-05`).

## Permitted Event Time Sources (`FR-3.1`)
User action timestamps come exclusively from three API fields:
1. **Liked Videos (Likes Playlist):** Resolving the user likes playlist ID via `channels.list?mine=true&part=contentDetails` (`relatedPlaylists.likes`) and querying `playlistItems.list?part=snippet` exposes `playlistItems.snippet.publishedAt`, which records the exact datetime when the user added the video to their likes playlist.
2. **Subscriptions:** Querying `subscriptions.list?mine=true&part=snippet` exposes `subscriptions.snippet.publishedAt`, which records when the user subscribed to that channel.
3. **User Playlist Items:** Querying `playlists.list?mine=true` followed by `playlistItems.list?part=snippet` exposes `playlistItems.snippet.publishedAt`, recording when the user added each video to that playlist.

## Prohibited Timestamp Fields (`INV-04`)
- `videos.snippet.publishedAt` (global video publication date on YouTube) and `playlistItems.contentDetails.videoPublishedAt` (video upload timestamp) MUST NEVER be used as user event times. Confusing upload time with action time corrupts both temporal interest decay (`FR-3.1`) and monthly activity trends (`FR-4.1`).

## Exponential 90 Day Half Life Decay (`FR-3.1`)
For a dated user action occurring $\Delta t \ge 0$ days prior to the evaluation timestamp, the decay weight is:
$$w(\Delta t) = 2^{-\Delta t / 90}$$
Recent likes, subscriptions, and playlist additions exert stronger influence on the constructed user interest profile than older interactions.

## Undated Items and First Observed Policy (`FR-3.2`, `INV-05`)
- **Undated Likes:** Retrieving likes via `videos.list?myRating=like` returns video snippets with no user rating timestamp.
- **Neutral Weighting:** Undated items receive a fixed configurable neutral weight (exact numeric value frozen in `ADR-0007`, gap `G-06`) and are reported as `undated`.
- **Optional First Observed Store (`G-05`):** The server may persist a local `first_observed` timestamp in SQLite for undated items across subsequent runs (policy frozen in `ADR-0007`). When used or counted in coverage metrics (`FR-4.3`), it must always be labelled as `first_observed` and never presented as the user like date.

## Recommendation Filtering and Coverage (`FR-3.3`, `FR-4.3`)
- Exclude videos already present in the user likes or saved playlists (`FR-3.3`), attach a concise reason per recommendation (such as `"similar to liked video X"`), and return `INSUFFICIENT_USER_SIGNAL` when no user signals exist (`INV-06`).
- Report explicit per source coverage counts (`dated`, `undated`, and `first_observed`) in analysis outputs (`FR-4.3`, `INV-08`).

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/second-brain|Second Brain Architecture]]
- [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]
- [[brain/inbox/engagement-analysis|Engagement Analysis Buckets, Period Comparisons and Privacy Aggregates]]
- [[brain/inbox/channel-similarity|Channel Similarity Profiling and Ranking]]
