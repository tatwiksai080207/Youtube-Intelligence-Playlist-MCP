# ADR-0005: Constrained Playlist Selection Solver and Draft Quota Preflight

- **Status:** Accepted
- **Date:** 2026-11-26
- **Decision Makers:** Mohammed Farhan (owner), Madire Shiva Reddy, Molleti Tatwik Sai
- **Task:** `MF-04`
- **GitHub Issue:** `#34`
- **GitHub PR:** `#35`
- **Requirements:** `FR-5.1`, `FR-5.1a`, `FR-5.2`, `FR-5.3`, `FR-6.2`, `NFR-1`, `NFR-2`, `NFR-5`, `NFR-9`, `SE-3`, `SB-3`
- **Distilled Brain Sources (`SB-3`):**
  - [[brain/projects/playlist-constraints|Playlist Duration and Spoken Language Constraints]]
  - [[brain/resources/knapsack-constraint-solving|Knapsack Constraint Solving for Playlist Duration Optimization]]
  - [[brain/resources/tfidf-cosine-similarity|TF IDF and Cosine Similarity]]
  - [[brain/resources/youtube-quota-costs|YouTube Data API Quota Costs]]
  - [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]

## Context

`draft_curated_playlist` (`FR-5.1`, `FR-5.1a`, `FR-5.2`, `FR-5.3`) turns a user's topic and numeric constraints into an immutable, time bounded playlist draft using objective YouTube metadata only. Two design constraints and one open planning gap require resolution before implementing `MF-08` through `MF-11`:

1. **Strict numeric and spoken language constraints (`INV-09`, `INV-10`):** Total duration must lie inside `[T * (1 - tolerance), T]` and never exceed `T`; `max_video_minutes` is inclusive; `max_videos` is an upper bound; and optional `language` filtering must inspect `snippet.defaultAudioLanguage` primary subtag only, never `snippet.defaultLanguage`.
2. **Deterministic sub 500 ms relevance solving (`NFR-1`, `INV-11`):** Selecting an optimal topic relevant subset over up to `200` candidates must complete in `<= 500 ms`, never silently relax constraints, and produce actionable `CONSTRAINTS_UNSATISFIABLE` diagnostics naming `N` retrieved candidates, the binding constraint, and user choice options.
3. **Open Gap `G-03`:** `FR-6.2` requires a workflow quota preflight that accounts for playlist write costs (`50 + 50` per video) before dispatching API calls, yet `draft_curated_playlist` does not know the exact final video count `k` prior to candidate search and solving.

## Decision

### 1. Strict Constraint Model (`src/yt_intel_mcp/playlist/constraints.py`, `FR-5.1`, `INV-09`)

- Convert `target_total_minutes` (`T`) and optional `max_video_minutes` (`M`) into integer seconds:
  - `target_max_seconds = round(T * 60)`
  - `target_min_seconds = math.ceil(target_max_seconds * (1.0 - tolerance_percent / 100.0))` (so a `120` minute request at `5%` allows `[6840, 7200]` seconds, i.e., `114:00` to `120:00`, while `6839` and `7201` are rejected)
  - `max_video_seconds = round(M * 60)` if `max_video_minutes` is provided, else `target_max_seconds`
- Candidate eligibility requires:
  - `video.is_available` is `True`, `video.privacy_status == "public"` (or playable non private), and `video.live_broadcast_content == "none"`
  - `video.duration_seconds is not None` and `1 <= video.duration_seconds <= max_video_seconds`
- Subset feasibility requires `1 <= len(selected) <= max_videos` and `target_min_seconds <= sum(v.duration_seconds for v in selected) <= target_max_seconds`. Constraints are never relaxed silently.

### 2. Spoken Audio Language Filter (`src/yt_intel_mcp/playlist/language.py`, `FR-5.1a`, `INV-10`)

- If `language` is omitted (`None`), skip spoken language filtering.
- If `language` is provided, extract its lowercase BCP 47 primary subtag (`requested.split("-")[0].lower()`).
- Inspect `video.default_audio_language` ONLY; ignore `video.default_language` completely.
  - Matching primary subtag -> eligible (`audio_language_status = "verified"`).
  - Different non empty primary subtag -> excluded unconditionally (even if `allow_unknown_language=True` or `default_language` matches).
  - Missing or blank `default_audio_language`:
    - Excluded when `allow_unknown_language=False` (default).
    - Included ONLY when `allow_unknown_language=True`, labelled `"Audio language unverified"` in the draft output.

### 3. Relevance Maximising Solver (`<= 500 ms` for `200` Candidates, `src/yt_intel_mcp/playlist/solver.py`, `NFR-1`, `INV-11`)

1. **Objective Relevance Scoring (`FR-5.2`, `INV-01`):**
   - Score each eligible candidate video against the sanitized `topic` query using pure TF IDF cosine similarity from `yt_intel_mcp.similarity.text` (`TS-08`), yielding deterministic relevance `r_i` in `[0.0, 1.0]` with zero view, like, or subscriber signals.
   - Pre sort eligible candidates deterministically by `(-r_i, video_id)`.
2. **Exact Boundary Hybrid Optimization (`<= 500 ms` target):**
   - **Exact regime (`N_elig * max_videos * (target_max_seconds + 1) <= 1_500_000` or `N_elig <= 35`):** Run exact cardinality bounded branch and bound with fractional knapsack upper bound pruning over exact integer seconds `[target_min_seconds, target_max_seconds]`, bounded by a `200 ms` search budget.
   - **Scaled regime (up to `N = 200` candidates, long targets up to `600` min):** Run bucketed cardinality dynamic programming (`B <= 240` duration buckets of size `step = max(1, target_max_seconds // 240)`) storing exact second sums and best objective values per `(count, bucket)` cell while pruning any branch whose exact duration exceeds `target_max_seconds`, followed by deterministic 1 for 1 swap and add/drop local search over exact integer seconds inside `[target_min_seconds, target_max_seconds]`.
   - **Exactness guarantee:** Every candidate subset evaluated as feasible is validated strictly against exact unrounded integer bounds `[target_min_seconds, target_max_seconds]`; bucket discretization never relaxes `113:59` or `120:01` boundaries.
   - **Deterministic tie breaking and ordering:** Equal total relevance breaks deterministically by lexicographically smallest sorted `tuple(video_id)` set; returned playlist order sorts selected items by descending relevance score, then ascending `video_id`.
3. **Structured `CONSTRAINTS_UNSATISFIABLE` Diagnostics (`FR-5.2`, `INV-11`):**
   - When no subset meets all constraints, raise `ToolError(ErrorCode.CONSTRAINTS_UNSATISFIABLE)` whose message and `details` explicitly state:
     - `candidates_retrieved`: exact count `N` retrieved (explicitly noting no compliant combination existed among those `N` candidates, not on YouTube overall)
     - `binding_constraint`: root cause (`language_filter`, `max_video_minutes`, `max_videos_capacity`, `target_total_window_floor`, or `insufficient_candidate_pool`)
     - `options`: explicit user choices requiring confirmation before re running, including broader search with estimated extra quota cost (`1` search call + `1` metadata unit) and specific named constraint relaxations (`allow_unknown_language=true`, higher `max_video_minutes`, wider `tolerance_percent`, or higher `max_videos`).

### 4. Immutable Expiring Drafts (`src/yt_intel_mcp/playlist/drafts.py`, `FR-5.3`, `INV-12`)

- Persist generated drafts in a server side `DraftStore` as frozen dataclasses (`ttl_seconds = 600` per `DraftConfig`).
- Each draft includes `draft_id`, `title`, `privacy_status`, `topic`, frozen constraint snapshot, ordered `DraftVideo` entries (`video_id`, sanitized `title`, sanitized `channel_title`, `duration_seconds`, `duration_human`, `audio_language_status`), `total_duration_seconds`, `total_duration_human`, `target_min_seconds`, `target_max_seconds`, `created_at_utc`, and `expires_at_utc`.

### 5. Resolution of `G-03`: Draft Time Write Cost Preflight (`FR-6.2`, `NFR-2`, `INV-19`)

Freeze the two phase preflight contract across `draft_curated_playlist` (`MF-11`) and `create_curated_playlist` (`MF-14`):

1. **Draft time pre read workflow preflight (`draft_curated_playlist`):**
   - Prior to calling `YouTubeProvider.search_videos` or `get_videos`, `draft_curated_playlist` computes:
     - `planned_read_cost`: `<= 3` `search_calls` and `<= 5` `units` (default draft discovery budget: up to `3` search calls + up to `3` metadata batch calls).
     - `worst_case_write_units`: `50 + 50 * effective_max_videos` (where `effective_max_videos = max_videos`).
   - Calls `QuotaGuard.preflight(CostEstimate(units=planned_read_cost.units + worst_case_write_units, search_calls=planned_read_cost.search_calls, operation="draft_curated_playlist_workflow"))`.
   - If insufficient, raises `QUOTA_BUDGET_INSUFFICIENT` with **zero provider calls** (`QT_3`).
   - Charges **only actual read calls executed** (`search.list` calls and `videos.list` units); unexecuted future writes are never charged during drafting.
2. **Exact write preflight (`create_curated_playlist`):**
   - Once a draft fixes `k = len(draft.videos)` items, `create_curated_playlist` preflights exact stale check + write units (`1 + 50 + 50 * k`, or `50 + 50 * k` immediately prior to `playlists.insert`) per `ADR-0004` (`G-02`).
3. **Budget verification against `NFR-2`:**
   - For a `10` video `video-to-playlist` workflow (`SK-1`): `get_video_details` (`1 u`) + `get_similar_videos` (`1 s + 2 u`) + `draft_curated_playlist` (`<= 3 s + <= 5 u`) + `create_curated_playlist` (`1 u` stale check + `0..1 u` channel check + `50 + 50 * 10 = 550 u`) consumes at most `4` search calls and `<= 560` units (`<= 600` units limit in `NFR-2`).

## Alternatives Considered

- **Pure quantized knapsack DP without exact second verification or local refinement:** Rejected because coarse time discretization (such as `10` second buckets) can misclassify boundary durations like `113:59` (`6839 s`) versus `114:00` (`6840 s`) or exceed `T` by rounding (`INV-09`).
- **Pre charging write quota during `draft_curated_playlist`:** Rejected because declined or expired drafts never write to YouTube, and `FR-6.1` / `FR-6.2` require preflighting estimated workflow cost while charging only actual dispatched requests.
- **Preflighting only read cost (`<= 3 s + <= 5 u`) in `draft_curated_playlist`:** Rejected because `FR-6.2` explicitly states *"a playlist workflow includes its write cost (`50 + 50` per video)"* prior to API calls (`QT_3`).

## Consequences

### Positive
- Resolves `G-03` cleanly before implementing `MF-08`, `MF-09`, `MF-10`, and `MF-11`.
- Guarantees deterministic sub `500 ms` solving on `200` candidates while preserving strict second level constraint boundaries (`UT_SOLV_WINDOW`, `X_PERF_SELECT`).
- Prevents wasting search quota when remaining daily units cannot sustain playlist creation (`QT_3`, `NFR-2`).

### Trade Offs
- Preflighting worst case `50 + 50 * max_videos` units assumes the user might select up to `max_videos` items; callers tight on daily quota can set a smaller `max_videos` bound (such as `10` in `SK-1`) to match their budget closely.

## References

- `Final_SRS_Submission.pdf` (v1.0): Section 3.1, Section 4.5 (`FR-5.1` to `FR-5.3`), Section 4.6 (`FR-6.2`), Section 5 (`NFR-1`, `NFR-2`, `NFR-5`).
- `docs/adr/0003-similarity-scoring.md` (`yt_intel_mcp.similarity.text` TF IDF scoring).
- `docs/adr/0004-trusted-confirmation.md` (trusted confirmation and `G-02` write execution order).
- `docs/architecture/playlist.md` (playlist subsystem component, state, and sequence diagrams).
