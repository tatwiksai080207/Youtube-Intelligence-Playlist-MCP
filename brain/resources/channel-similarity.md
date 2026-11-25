---
title: Channel Similarity Profiling and Ranking
type: reference
status: distilled
authors:
  - Molleti Tatwik Sai
created: 2026-11-25
updated: 2026-11-25
tags:
  - youtube
  - channels
  - similarity
  - tfidf
  - metadata
requirements:
  - FR-2
  - FR-2.1
  - FR-2.2
  - C-3
  - SB-1
  - SB-6
issues:
  - "#6"
  - "#19"
prs:
  - "#14"
  - "#20"
sources:
  - "Final_SRS_Submission.pdf Section 4.2 and 5 (checked 2026-11-25)"
  - "YouTube Data API v3 Channels Resource: https://developers.google.com/youtube/v3/docs/channels (checked 2026-11-25)"
  - "YouTube Data API v3 PlaylistItems Resource: https://developers.google.com/youtube/v3/docs/playlistItems (checked 2026-11-25)"
---

# Channel Similarity Profiling and Ranking

## Summary
Because the YouTube Data API v3 provides no related channels endpoint (SRS constraint `C-3`), the `get_similar_channels` tool computes channel similarity locally from objective creator metadata (`FR-2.1`, `FR-2.2`). Subscriber counts, view counts, and engagement metrics never influence channel rankings (`INV-01`).

## Input Resolution and Validation
- **Accepted Forms (`FR-2.1`):** Channel URLs from allow listed YouTube hosts, `@handle` strings (resolved via `channels.list?forHandle=...`), or canonical `UC...` channel IDs.
- **Pre Flight Validation (`INV-02`):** Malformed IDs, disallowed URL hosts, or out of range `max_results` return `INVALID_ARGUMENT` before spending any API quota.
- **Nonexistent Channel Error Gap (`G-01`):** Whether a valid format handle or ID that resolves to zero channels returns `INVALID_ARGUMENT` or an erratum code is tracked under decision `G-01` for team vote before `TS-11` negative testing.

## Channel Profile Feature Extraction
For the seed channel and each candidate channel, `YouTubeProvider` fetches `channels.list` requesting `part=snippet,brandingSettings,topicDetails,contentDetails` (strictly omitting `statistics`). Each profile aggregates five metadata dimensions (`FR-2.2`):
1. **Channel Title (`snippet.title`):** Primary creator or topic identifier.
2. **Channel Description (`snippet.description`):** Long form description text, sanitised against prompt injection (`NFR-6`, `INV-22`).
3. **Channel Keywords (`brandingSettings.channel.keywords`):** Creator configured topic tags parsed cleanly from the keywords string.
4. **Topic Categories (`topicDetails.topicCategories`):** Wikipedia topic URLs assigned to the channel, normalised to comparable category tokens.
5. **Recent Uploads (`contentDetails.relatedPlaylists.uploads`):** Recent upload titles and tags retrieved via `playlistItems.list` and `videos.list` (again strictly excluding `statistics`).

## Candidate Retrieval and Scoring
- Extract key terms from the seed channel profile to build `search.list` (`type=channel`) candidate queries within the tool budget (`1 s + <= 32 u`, SRS Section 3.1).
- Construct TF IDF weighted feature vectors for each candidate profile and compute weighted cosine similarity (`[0, 1]`) across text metadata, topic overlap, and recent upload content.
- Return ranked channels with a transparent per feature score breakdown; subscriber counts never affect ranking (`FR-2.2`).

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/second-brain|Second Brain Architecture]]
- [[brain/resources/tfidf-cosine-similarity|TF IDF and Cosine Similarity]]
- [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]
- [[brain/resources/youtube-quota-costs|YouTube Quota Costs]]
- [[brain/resources/youtube-event-timestamps|YouTube Event Timestamps and Temporal Interest Weighting]]
