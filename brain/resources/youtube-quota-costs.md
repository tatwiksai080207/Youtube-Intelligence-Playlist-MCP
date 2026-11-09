---
title: YouTube Data API Quota Costs and Budgeting
type: reference
created: 2026-11-09
tags:
  - youtube
  - quota
  - api
  - performance
requirements:
  - FR-6
  - NFR-QUOTA-1
  - NFR-QUOTA-2
  - NFR-QUOTA-3
---

# YouTube Data API Quota Costs and Budgeting

## Summary
The YouTube Data API v3 enforces a default daily quota limit of 10000 units per Google Cloud project. This allocation resets every midnight Pacific Time. Because operations vary dramatically in cost from 1 unit to 100 units, strict tracking and pre flight budget validation are required.

## Quota Accounting Details
Every request made to the YouTube Data API v3 consumes quota units regardless of whether the call succeeds or fails.

| Method | Resource | Cost in Units | Notes |
|---|---|---|---|
| `videos.list` | Videos | 1 unit per call | Retrieves up to 50 videos by ID |
| `channels.list` | Channels | 1 unit per call | Resolves channel by handle or ID |
| `search.list` | Search | 100 units per call | High cost operation returning up to 50 results |
| `playlists.insert` | Playlists | 50 units per call | Creates a new playlist container |
| `playlistItems.insert` | Playlist Items | 50 units per call | Adds a single video to a playlist |
| `subscriptions.list` | Subscriptions | 1 unit per page | Scans user subscriptions |
| `playlists.list` | Playlists | 1 unit per page | Scans user playlists |
| `videoCategories.list` | Categories | 1 unit per call | Static map, should be cached for 7 days |

## Architectural Implications
1. **Pre flight Verification**: Before executing a tool or workflow, the system must project the total quota cost. If projected cost exceeds available quota, the operation must abort immediately before making any upstream network call.
2. **Caching Strategy**: Cache video metadata for 24 hours and search results for 6 hours. This preserves quota during iterative exploration.
3. **Write Reserve**: Maintain a dedicated write reserve of 600 units to guarantee that once a playlist draft is approved, the creation step will not fail midway due to quota exhaustion.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]

