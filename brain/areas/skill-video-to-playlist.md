---
title: "Skill Note: video-to-playlist (SK-1)"
type: skill-note
status: distilled
authors:
  - Mohammed Farhan
created: 2026-11-28
updated: 2026-11-28
tags:
  - skills
  - video-to-playlist
  - curation
  - metadata
  - prompt-injection
  - hitl
  - quota
requirements:
  - SK-1
  - NFR-2
  - TQ-7
  - SB-1
  - SB-3
  - SB-6
issues:
  - "#88"
prs:
  - "#89"
sources:
  - "Final_SRS_Submission.pdf Section 4.9 SK-1, Section 5 NFR-2, and Section 6.2 (checked 2026-11-28)"
  - "docs/adr/0004-trusted-confirmation.md (checked 2026-11-28)"
  - "docs/adr/0005-playlist-selection.md (checked 2026-11-28)"
---

# Skill Note: video-to-playlist (SK-1)

## Summary
The `video-to-playlist` Agent Skill (`skills/video-to-playlist/SKILL.md`, requirement `SK-1`) provides the primary product workflow for `yt-intel-mcp`. Given a single seed video, the skill orchestrates a five step pipeline: summarizing the video from objective metadata alone, discovering structurally similar videos, drafting a duration constrained playlist, guiding out of band human in the loop confirmation, and executing the creation with comprehensive outcome reporting.

## Metadata Boundary and Disclaimer (`INV-23`, `SE_EVAL_SUM`)
In accordance with project scope exclusions (Section 1.2), audio visual playback, speech transcripts, and pixel level content analysis are strictly prohibited. Consequently:
1. Video summaries are synthesized exclusively from objective metadata exposed by `get_video_details` (title, description, tags, category, chapters in description, duration, and channel identity).
2. The summary MUST always be explicitly preceded by the exact disclaimer label:
   > **Summary based on video metadata, not on the video's content**
3. The AI agent is strictly barred from asserting claims about spoken narration, visual scenes, or subjective opinions delivered inside the video.

## Five Step Execution Pipeline
1. **Summarize Seed Video:** Resolves video identifier and obtains objective metadata via `get_video_details` (cost: 1 unit).
2. **Find Similar Videos:** Discovers candidate videos using `get_similar_videos` with TF IDF cosine similarity across titles, tags, and descriptions (`FR-1`, cost: 1 search call and 2 units). Engagement metrics (views, likes, subscriber numbers) never alter rankings (`FR-1.3`).
3. **Draft Constrained Playlist:** Constructs a knapsack optimized playlist draft via `draft_curated_playlist` (`FR-5.1..5.3`, cost: $\le 3$ search calls and $\le 5$ units). Enforces exact duration boundaries $[T \times (1 - \text{tolerance}), T]$, language filtering (`FR-5.1a`), and maximum video duration limits.
4. **Create Curated Playlist:** Dispatches `create_curated_playlist` with `draft_id` only (`INV-13`). Enforces pre-write staleness checks (`DRAFT_STALE`), write scope consent (`youtube.force-ssl`), channel presence (`CHANNEL_REQUIRED`), and zero write retries (`NFR-8`, `INV-24`).
5. **Show Playlist Analysis:** Reports final status (`COMPLETE` or `PARTIAL`), video count, actual versus target duration, channel distribution, and detailed failure or unattempted records if any write failed (`INV-17`).

## Prompt Injection Defense and Trusted Confirmation Gate (`INV-13`, `INV-22`, `NFR-6`)
Untrusted metadata in video titles and descriptions could contain adversarial prompt injection payloads instructing the agent to bypass confirmation or approve malicious playlist writes. The skill reinforces key system defenses:
- Chat messages, tool arguments, or instructions in video metadata NEVER count as approval (`FR-5.4`).
- Approval requires out of band confirmation via MCP elicitation dialog (Channel A) or a local 127.0.0.1 browser page (Channel B).
- The server mints a single use cryptographic token bound to the account and draft, preventing token reuse or tampering (`INV-14`).

## Quota Governance and Evaluation Targets (`NFR-2`, `TQ-7`)
- **Workflow Budget Cap:** A complete 10 video curation run consumes at most 560 units and 4 search calls, remaining comfortably within the `NFR-2` ceiling of $\le 600$ units and $\le 4$ `search.list` calls.
- **Skill Evaluations:** Documented under `docs/testing/skill-evals.md` across test scenarios `SE_EVAL_SUM` (metadata only summary label), `SE-V2P-01` (summarization), `SE-V2P-02` (similarity), `SE-V2P-03` (drafting), `SE-V2P-04` (confirmation gate), and `SE-V2P-05` (write execution and quota).

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/agent-skills-specification|Agent Skills Specification]]
- [[brain/projects/playlist-constraints|Playlist Duration and Spoken Language Constraints]]
- [[brain/resources/mcp-elicitation-confirmation|Trusted Playlist Confirmation with MCP Elicitation]]
- [[brain/projects/partial-playlist-outcomes|Playlist Writes and Partial Outcomes]]
- [[brain/resources/youtube-quota-costs|YouTube API Quota Costs]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
- [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
