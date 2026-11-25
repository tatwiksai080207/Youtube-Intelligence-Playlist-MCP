# ADR-0007: Interest Profile Weighting, Timestamp Provenance, and Engagement Guards

- **Status:** Accepted
- **Date:** 2026-11-26
- **Decision Makers:** Molleti Tatwik Sai (owner), Madire Shiva Reddy, Mohammed Farhan
- **Task:** `TS-04`
- **GitHub Issue:** `#27`
- **GitHub PR:** `pending`
- **Requirements:** `FR-3.1`, `FR-3.2`, `FR-3.3`, `FR-4.1`, `FR-4.2`, `FR-4.3`, `NFR-1`, `NFR-2`, `NFR-7`, `SE-3`, `SB-3`
- **Brain Sources:**
  - [[brain/resources/youtube-event-timestamps|YouTube Event Timestamps and Temporal Interest Weighting]]
  - [[brain/projects/engagement-analysis|Engagement Analysis Buckets, Period Comparisons and Privacy Aggregates]]
  - [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]
  - [[brain/resources/youtube-quota-costs|YouTube API Quota Costs]]

## Context

`FR-3` (`get_recommendations`) and `FR-4` (`analyze_engagement`) derive user interest profiles and aggregate activity analytics exclusively from explicit authenticated YouTube library actions (`liked_video`, `subscription`, `playlist_item`). Two specification gaps identified in the planning register require explicit architectural closure before implementing `TS-12`, `TS-13`, and `TS-14`:

- **`G-05`:** Consistent handling of an optional local `first_observed` timestamp store between recommendation decay (`FR-3.2`) and engagement coverage reporting (`FR-4.3`).
- **`G-06`:** Exact fixed neutral weight applied to undated events in interest profile scoring (`FR-3.2`).

## Decision

### 1. Strict Signal Extraction and Event Time Provenance (`INV-04`, `INV-05`)

User signal collection gathers only explicit library sources aligned with `models.EventSource`:
- `"liked_video"`: entries from the likes playlist (`channels.list?mine=true` likes playlist via `playlistItems.list`, exposing user action timestamp `snippet.publishedAt`), or fallback `videos.list(myRating="like")` (which carries no like timestamp).
- `"subscription"`: subscribed channels (`subscriptions.list?mine=true`, exposing subscription timestamp `snippet.publishedAt`).
- `"playlist_item"`: items inside user owned playlists (`playlists.list?mine=true` then `playlistItems.list`, exposing playlist addition `snippet.publishedAt`).

**Prohibited fields (`INV-04`):** `videos.snippet.publishedAt` and `playlistItems.contentDetails.videoPublishedAt` represent global video upload time and MUST NEVER populate `UserEvent.event_time`. When zero items exist across all requested `sources`, tools fail fast with `INSUFFICIENT_USER_SIGNAL` (`INV-06`).

### 2. Temporal Half Life Decay and Resolution of `G-06` (`undated_weight = 0.5`)

For every deduplicated `UserEvent`, temporal weight $w(e)$ uses `ProfileConfig` defaults from `src/yt_intel_mcp/config.py`:

$$w(e) = \begin{cases}
0.5^{\max(0, \Delta t) / 90.0}, & \text{if } e.\text{time\_kind} = \texttt{DATED} \\
0.5, & \text{if } e.\text{time\_kind} \in \{\texttt{UNDATED}, \texttt{FIRST\_OBSERVED}\}
\end{cases}$$

- **Resolution of `G-06`:** Freeze `ProfileConfig.undated_weight = 0.5` as the neutral constant weight for undated items, equivalent to one half life (`90` days) so un timestamped likes neither overpower today's actions (`1.0`) nor vanish beside multi year history (`<= 0.125`).
- If an item appears across multiple sources (`liked_video` and `playlist_item`), aggregate cleanly using max recency weight across occurrences rather than counting the same video as duplicate signal mass (`max(weights)` with merged provenance tags).

### 3. Resolution of `G-05` (`first_observed` Policy Across `FR-3.2` and `FR-4.3`)

1. Persist monotonic local observation records `(source, item_id, first_observed_utc)` in SQLite only when reading live/fixture undated events for which the API supplies no user action timestamp. Never initialize or backfill `first_observed_utc` from upload publication dates.
2. When an undated item already exists in local storage, tag its normalized event as `EventTimeKind.FIRST_OBSERVED`; on its very first observation (or if persistence is absent), tag it `EventTimeKind.UNDATED`.
3. **Profile weighting (`FR-3.2`):** Treat `FIRST_OBSERVED` identically to `UNDATED` (`weight = 0.5`). Local server discovery time does not indicate when the user originally liked the video, so applying decay from `first_observed_utc` would falsely inflate old likes to `1.0`.
4. **Engagement reporting (`FR-4.3`):** Report separate coverage counts for `dated`, `undated`, and `first_observed` events (`timestamp_coverage`) and exclude both `undated` and `first_observed` events from dated period slicing and cadence trends (`INV-08`).

### 4. Candidate Query Synthesis and Budget Cap (`FR-3.3`, `NFR-2`)

1. Rank weighted profile unigrams, bigrams, tags, and categories across active decayed user events to build up to **`3`** concise search queries (`top_query_count = 3`).
2. Dispatch at most `3` `search.list` calls (`SearchHit` candidates) plus `<= 25` video metadata enrichment units (`videos.list` batched up to `50` IDs per `1` unit call, well within `<= 25` enrichment units and `NFR-2`), preflighted synchronously through `QuotaGuard`.
3. Filter out all videos already present in the user likes or saved playlists (`FR-3.3`), score candidates via `ADR-0003` objective similarity against top weighted interest centroids, exclude popularity fields (`INV-01`), and attach concise attribution strings (for example, `"Aligned with your interest in systems programming and Rust"`).

### 5. Engagement Analysis Schema, Buckets, and Guards (`FR-4.1`..`FR-4.3`)

- **Frozen `timeframe` enum (`analyze_engagement.json`):** `"7d"`, `"30d"`, `"90d"` (default), `"180d"`, `"365d"`, `"all"`.
- **Duration buckets (`EngagementConfig`):**
  - `short`: `duration_seconds < 240` (`< 4` minutes)
  - `medium`: `240 <= duration_seconds <= 1200` (`4` to `20` minutes)
  - `long`: `duration_seconds > 1200` (`> 20` minutes)
  - `unknown`: `duration_seconds is None`
- **Previous period comparison (`INV-07`):** When `compare_with_previous_period=true` and `timeframe != "all"`, compare against the equal length immediately preceding UTC window. When previous period activity is `0` (`0` dated events or `0` topic count), report percentage delta as `null` (`None`) with comparison status `"no_baseline_data"` instead of dividing by zero; for `"all"`, report comparison status `"not_applicable_for_all_timeframe"`.
- **Cadence confidence guard (`INV-08`):** Require `dated_event_count >= EngagementConfig.min_dated_events` (`5`) before computing trend cadence rates; below `5` dated events, return `"insufficient_dated_data"`.
- **Privacy preserving aggregate invariant (`FR-4.3`, `INV-09`, `NFR-7`):** Response payloads expose only aggregated topic shares, duration bucket distributions, source counts, timestamp coverage totals, and redacted top level cadence summaries; raw personal `video_id`, `channel_id`, or `playlist_id` activity histories are strictly omitted.

## Alternatives Considered

- **Decaying `first_observed` from local discovery timestamp in `FR-3.2`:** Rejected because the very first run would assign every multi year old like weight `1.0`, violating chronological fidelity (`INV-04`, `INV-05`).
- **Setting `undated_weight = 0.0` or `1.0`:** Rejected because `0.0` discards legitimate likes returned without action timestamps while `1.0` unfairly dominates real dated activity; `0.5` balances both cleanly (`G-06`).
- **Using freeform date range strings in `analyze_engagement`:** Rejected in favor of bounded `timeframe` presets to satisfy `NFR-5` schema predictability across MCP clients while allowing easy additive extension later if needed.

## Consequences

### Positive
- Resolves `G-05` and `G-06` cleanly prior to `TS-12`, `TS-13`, and `TS-14` implementation.
- Guarantees identical deterministic profile math and cadence guards across fixture replay and live execution.
- Keeps `FR-3` search cost bounded at `<= 3` search calls and `<= 25` metadata enrichment units (`C-2`, `NFR-2`).

### Trade Offs
- When all user likes come exclusively from undated endpoints, engagement cadence degrades intentionally to `"insufficient_dated_data"` rather than estimating trends from upload dates.
