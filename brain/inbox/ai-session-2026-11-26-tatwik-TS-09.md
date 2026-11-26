---
title: AI Session TS-09 get_video_details Tool
type: ai-session
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-26
updated: 2026-11-26
tags:
  - ai-session
  - stage-3
  - tools
  - metadata
  - security
requirements:
  - FR-1.4
  - SK-1
  - SK-2
  - NFR-6
  - NFR-9
issues:
  - "#64"
prs: []
sources:
  - "Final_SRS_Submission.pdf Sections 3.1, 4.1, 4.9, and 5 (checked 2026-11-26)"
  - "src/yt_intel_mcp/tools/draft_curated_playlist.py registration pattern (checked 2026-11-26)"
---

# AI Session TS-09 get_video_details Tool

## Task Summary
Implemented the read only `get_video_details` MCP tool for Stage 3 task `TS-09` (Issue `#64`), wiring strict validation, `1 u` quota preflight, metadata sanitization, chapter extraction, and human readable duration formatting.

## Deliverables Authored
- `src/yt_intel_mcp/tools/get_video_details.py`: implemented `validate_get_video_details_arguments`, `parse_chapters_from_description`, `execute_get_video_details`, and `register_get_video_details` returning sanitized objective metadata, channel info, raw/human/clock durations, live broadcast status, audio language fields, parsed chapters, and `metadata_only_notice` with zero popularity fields (`INV-01`, `INV-22`).
- `tests/system/test_get_video_details.py`: verified end to end MCP tool registration and invocation over memory streams (`dQw4w9WgXcQ`, live video handling, schema rejection with zero quota).
- `tests/negative/test_video_availability.py` (`NT_VID`): verified private, deleted, and missing videos return `VIDEO_UNAVAILABLE` and invalid IDs/URLs reject pre quota with `INVALID_ARGUMENT` and zero provider calls.

## Related Brain Context
- Aligns with [[brain/resources/tfidf-cosine-similarity]], [[brain/areas/security/prompt-injection-defence]], and [[brain/resources/nfr-targets]].

## Verification
- Verified `scripts/validate_skills.py`, `scripts/validate_brain.py`, and `tests/negative/test_video_availability.py` / `tests/system/test_get_video_details.py`.
