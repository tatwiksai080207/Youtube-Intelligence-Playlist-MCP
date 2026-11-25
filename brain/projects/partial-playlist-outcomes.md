---
title: Playlist Writes and Partial Outcomes
type: reference
status: distilled
authors:
  - Mohammed Farhan
created: 2026-11-25
updated: 2026-11-25
tags:
  - youtube
  - playlist
  - partial-outcome
requirements:
  - FR-5.5
  - NFR-8
  - SB-1
  - SB-6
issues:
  - "#7"
  - "#19"
prs:
  - "#17"
  - "#20"
sources:
  - "Final_SRS_Submission.pdf v1.0, sections 4.5 and 5 (checked 2026-11-25)"
  - "YouTube Data API v3 playlists.insert: https://developers.google.com/youtube/data/reference/rest/v3/playlists/insert (checked 2026-11-25)"
  - "YouTube Data API v3 playlistItems.insert: https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/insert (checked 2026-11-25)"
---

# Playlist Writes and Partial Outcomes

## Summary

FR-5.5 requires a final check of the approved videos, ordered writes, and a report of what was actually created. The report distinguishes failed insertions from items the server never attempted.

## From approval to writes

The server dispatches YouTube requests through `YouTubeProvider`.

1. Immediately before writing, re-check the approved videos. If any approved video changed or became unavailable, return `DRAFT_STALE` with zero writes. The user needs a new draft and fresh approval.
2. Once all pre-write checks pass, use `playlists.insert` to create the playlist using the approved title and privacy setting, which defaults to `private`. Use `playlistItems.insert` to add the approved videos in their approved order. YouTube exposes playlist creation and item insertion as separate calls.
3. If an item fails after playlist creation, record its reason and continue with the remaining approved videos in order. A quota or authorization error stops processing immediately. Record the current item as failed when its insertion returns that error and mark the rest as not attempted. There are no substitutions, reorderings, or automatic write retries.

## Reporting and recovery

Return `COMPLETE` only when all approved videos were inserted and every constraint still holds. Otherwise return `PARTIAL` for the playlist that was created, with its URL, the inserted items, failed items and reasons, items left unattempted, actual total duration, and every unmet constraint.

For example, a 120-minute request at 5% tolerance approves videos of 40, 37, and 40 minutes. If the 37-minute insertion fails with an item-specific error and the other two succeed, report an 80-minute `PARTIAL` playlist below the 114-minute floor. If the second insertion fails with a quota error, the final 40-minute item is unattempted and the total is 40 minutes.

Any recovery that changes the approved contents requires a new draft and fresh trusted approval. Existing playlists, including the partial result, are outside the service's edit and delete scope.

## Verification targets

- `NT_DRAFT_STALE` checks zero writes when a video changes or becomes unavailable before writing.
- `IT_DRAFT`, `IT_DRAFT_PARTIAL`, and `ST_FR5` cover ordered insertion, continuing after an item failure, stopping on quota or authorization errors, and reporting the final duration and unmet constraints.

## Related notes

- [[brain/index|Second Brain Index]]
- [[brain/resources/mcp-elicitation-confirmation|Trusted confirmation]]
- [[brain/projects/playlist-constraints|Playlist constraints]]
- [[brain/resources/youtube-quota-costs|YouTube API Quota Costs]]
