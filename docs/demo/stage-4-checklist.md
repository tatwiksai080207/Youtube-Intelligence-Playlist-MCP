# Stage 4 Live Demonstration Checklist, Rehearsal Log, and Viva Preparation (`TS-17`)

This checklist governs the Stage 4 live demonstration and viva comprehension walkthrough for the YouTube Video Intelligence MCP Server (`yt-intel-mcp`), satisfying SDLC Section 6 (Comprehension) and Section 7 (Stage 4).

## 1. Pre Demonstration Readiness Checks

Before starting the live demonstration:
1. **OAuth Authorization Window (Guide D):** Confirm Google Cloud Desktop OAuth credentials are active and the test user completed OAuth login within the last 7 days (`get_auth_status` returns `authenticated: true`, `has_channel: true`).
2. **Obsidian Second Brain Check (Guide F):** Confirm `brain/index.md` opens cleanly in Obsidian graph view with zero broken wikilinks (`py -3.11 scripts/validate_brain.py`).
3. **Quota Pre Check:** Run `get_quota_status` (or read `youtube://metrics/quota`) at `0` quota cost and verify sufficient remaining daily budget (`>= 1,000` units and `>= 15` search calls).
4. **Fixture Fallback Protocol:** If live YouTube API quota exhausts (`QUOTA_EXHAUSTED_UPSTREAM`) or network access is unavailable during the session, switch explicitly to fixture mode (`YT_INTEL_PROVIDER=fixture`) and state on screen that the fallback is running against scrubbed fixtures (`tests/fixtures/`). Never silently mix fixture and live outputs.

## 2. Live Demonstration Script

### Step 1: `local-check` Live Verification (`SK-2`)
- Run `py -3.11 scripts/local_check.py` (with `YT_INTEL_PROVIDER=fixture` for zero live quota verification) and show all 5 steps passing (`wheel build`, `pytest`, `validate_skills.py`, `validate_brain.py`, stdio `get_video_details` + `get_quota_status` round trip).

### Step 2: Live `FR-1` through `FR-5` in an MCP Client
1. **`FR-1` (`get_video_details` & `get_similar_videos`):** Inspect a seed video (`1` unit) and retrieve objective metadata matches (`<= 1` search + `2` units), confirming chapters, human readable duration, and zero popularity statistics.
2. **`FR-2` (`get_similar_channels`):** Resolve a channel `@handle` or URL and rank similar channels by topics, keywords, and recent uploads without subscriber counts (`<= 1` search + `<= 32` units).
3. **`FR-3` (`get_recommendations`):** Build a 90 day half life interest profile from explicit library signals, verify already liked/saved videos are excluded, and show human attribution reasons (`<= 3` searches + `<= 25` units).
4. **`FR-4` (`analyze_engagement` & `youtube://user/context`):** Show duration buckets (`<4m`, `4–20m`, `>20m`), timestamp coverage (`dated`, `undated`, `first_observed`), watch history disclaimer, and zero raw personal IDs (`<= 9` units, `0` searches).
5. **`FR-5` (`draft_curated_playlist` & `create_curated_playlist` via `video-to-playlist` `SK-1`):**
   - Run `video-to-playlist` (`SK-1`) end to end: inspect seed video, draft a constrained playlist within the target duration window and spoken audio language (`defaultAudioLanguage`), and display the metadata only summary notice.
   - Trigger `create_curated_playlist` with `draft_id` only, demonstrate that chat text cannot approve the write, and approve via the out of band trusted confirmation channel (MCP elicitation or `127.0.0.1` loopback page) to receive `COMPLETE` (or `PARTIAL`) outcome reporting.

### Step 3: `brain-query` Live Walkthrough (`SK-5`)
- Invoke `brain-query` on a grounded project question (for example, how `G-05` and `G-06` govern `first_observed` and `undated_weight`), verifying every claim cites a real distilled brain note and refuses unsupported claims.

### Step 4: End to End Traceability Walkthrough (`SE-5`)
Demonstrate the complete traceability chain from research knowledge to passing test:
1. **Second Brain Note:** `[[brain/resources/tfidf-cosine-similarity]]`
2. **Architecture Decision Record:** `docs/adr/0003-similarity-scoring.md` (`ADR-0003` weights and missing field redistribution)
3. **Implementation Module:** `src/yt_intel_mcp/similarity/videos.py` (`rank_similar_videos`)
4. **Verification Tests:** `tests/unit/test_similarity.py` (`test_UT_SIM_*`) and `tests/unit/test_similarity_videos.py`

## 3. Viva Speaking Ownership (SDLC Section 6)

| Team Member | Owned Modules & Subsystems | Owned Skills & ADRs | Key Tests to Explain |
|---|---|---|---|
| **Madire Shiva Reddy (`Shiva0025`)** | `provider/base.py`, `provider/fixture.py`, `provider/live.py`, `store.py`, `cache.py`, `quota/ledger.py`, `auth/token_store.py`, `auth/oauth.py`, `server.py` | `brain-query` (`SK-5`), `ADR-0001`, `ADR-0002`, `ADR-0006` | `UT_QUOTA`, `QT_1..3`, `IT_CACHE`, `IT_PROV`, `SEC_OAUTH`, `test_import_lint.py` |
| **Molleti Tatwik Sai (`tatwiksai080207`)** | `validation/ids.py`, `durations.py`, `similarity/text.py`, `similarity/videos.py`, `similarity/channels.py`, `analysis/events.py`, `analysis/profile.py`, `analysis/recommend.py`, `analysis/engagement.py`, `tools/get_video_details.py`, `tools/get_similar_videos.py`, `tools/get_similar_channels.py`, `tools/get_recommendations.py`, `tools/analyze_engagement.py`, `docs/user/guide.md` | `brain-ingest` (`SK-3`), `brain-refine` (`SK-4`), `ADR-0003`, `ADR-0007` | `UT_ID`, `NT_VAL`, `UT_DUR`, `UT_SIM`, `UT_STAT_TS`, `UT_PROF`, `UT_STAT_BUCKET`, `ST_FR1..ST_FR4` |
| **Mohammed Farhan (`farhan4599`)** | `sanitize.py`, `playlist/constraints.py`, `playlist/language.py`, `playlist/solver.py`, `playlist/drafts.py`, `playlist/writer.py`, `confirmation/tokens.py`, `confirmation/elicit.py`, `confirmation/local_page.py`, `tools/draft_curated_playlist.py`, `tools/create_curated_playlist.py`, `scripts/local_check.py`, `scripts/validate_*.py` | `video-to-playlist` (`SK-1`), `local-check` (`SK-2`), `ADR-0004`, `ADR-0005` | `NFR_6`, `UT_SOLV_WINDOW`, `UT_LANG`, `UT_SOLV`, `NT_HITL`, `ST_FR5_CONFIRM`, `IT_DRAFT`, `IT_DRAFT_PARTIAL` |

## 4. Team Rehearsal Record

- **Rehearsal Date:** `2026-11-28`
- **Participants:** Molleti Tatwik Sai, Madire Shiva Reddy, Mohammed Farhan
- **Scope Verified:**
  - Verified full offline CI suite (`476+` tests, `92%` coverage, `ruff`, `mypy`, `gitleaks`, `validate_skills.py`, `validate_brain.py`).
  - Verified `scripts/local_check.py` all 5 steps in fixture mode (`0` live quota).
  - Rehearsed end to end traceability walkthrough (`tfidf-cosine-similarity` -> `ADR-0003` -> `similarity/videos.py` -> `test_UT_SIM_*`) and individual viva ownership handoffs across all 3 members.
  - Verified `get_quota_status` preflight check and explicit fixture fallback labelling.
