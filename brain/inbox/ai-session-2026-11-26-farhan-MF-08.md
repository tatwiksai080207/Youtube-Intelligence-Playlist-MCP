---
title: AI Session MF-08 Playlist Constraint Model and Window Logic
type: ai-session
status: inbox
authors:
  - Mohammed Farhan
created: 2026-11-26
updated: 2026-11-26
tags:
  - ai-session
  - stage-3
  - playlist
  - constraints
requirements:
  - FR-5.1
  - NFR-5
  - SB-1
issues:
  - "#54"
prs: []
sources:
  - "Final_SRS_Submission.pdf v1.0, Section 4.5 FR-5.1 (checked 2026-11-26)"
  - "docs/adr/0005-playlist-selection.md and src/yt_intel_mcp/durations.py (checked 2026-11-26)"
---

# AI Session MF-08 Playlist Constraint Model and Window Logic

## Task Summary
Implemented `src/yt_intel_mcp/playlist/__init__.py` and `src/yt_intel_mcp/playlist/constraints.py` (`MF-08`, Issue `#54`), enforcing strict duration window logic, inclusive `max_video_minutes`, upper bound `max_videos`, and pre quota parameter validation.

## Deliverables Authored
- `src/yt_intel_mcp/playlist/constraints.py`:
  - `PlaylistConstraints` frozen dataclass storing validated constraints, exact `Decimal` ceiling floor `target_min_seconds`, `target_max_seconds`, and `effective_max_video_seconds`.
  - `build_playlist_constraints`: validates `topic`, `target_total_minutes`, `tolerance_percent`, `max_video_minutes`, `max_videos`, BCP 47 `language`, `allow_unknown_language`, `title`, and `privacy_status` via `validation/bounds.py` before any quota spend (`INV-02`).
  - `is_video_duration_eligible`, `is_total_in_window`, and `evaluate_selection_constraints`: reuses `durations.is_live_or_zero_duration` (`TS-07`) and enforces `[T * (1 - tol), T]` without exceeding `T` (`INV-09`).
- `tests/unit/test_playlist_constraints.py`: added `UT_SOLV_WINDOW` and `NT_VAL` tests covering `120m @ 5%` (`114:00`..`120:00` accepted; `113:59` and `120:01` rejected), `Decimal` precision against binary float drift, inclusive `max_video_minutes`, `< max_videos` acceptance, and invalid parameter rejection.
- Updated `docs/traceability.md`, `brain/index.md`, and `brain/log.md`.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/projects/playlist-constraints|Playlist Duration and Spoken Language Constraints]]
- [[brain/resources/knapsack-constraint-solving|Knapsack Constraint Solving]]

## Verification
- Verified `ruff check .`, `ruff format --check .`, `mypy src`, `scripts/validate_skills.py`, `scripts/validate_brain.py`, and pytest suites in fixture mode.
