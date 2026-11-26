---
title: AI Session MF-10 Constrained Playlist Selection Solver
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
  - solver
requirements:
  - FR-5.2
  - NFR-1
  - SB-1
issues:
  - "#60"
prs: []
sources:
  - "Final_SRS_Submission.pdf v1.0, Section 4.5 FR-5.2 and Section 5 NFR-1 (checked 2026-11-26)"
  - "docs/adr/0005-playlist-selection.md Section 3 (checked 2026-11-26)"
---

# AI Session MF-10 Constrained Playlist Selection Solver

## Task Summary
Implemented `src/yt_intel_mcp/playlist/solver.py` (`MF-10`, Issue `#60`) per `docs/adr/0005-playlist-selection.md`, maximising objective TF IDF topic relevance over strict duration and spoken audio language constraints within the `<= 500 ms` (`NFR-1`) performance ceiling for `200` candidates.

## Deliverables Authored
- `src/yt_intel_mcp/playlist/solver.py` (exported from `src/yt_intel_mcp/playlist/__init__.py`):
  - `score_candidates_for_topic`: scores deduplicated candidate videos in `[0.0, 1.0]` using `yt_intel_mcp.similarity.text` over sanitized title, tags, and description fields with zero popularity signals (`INV-01`).
  - `solve_playlist_selection`: enforces playability, live/zero duration exclusion, strict `defaultAudioLanguage` filtering (`FR-5.1a`, `INV-10`), and exact second bounds `[target_min_seconds, target_max_seconds]` (`INV-09`). Uses sparse exact cardinality DP or bounded branch and bound with bitset reachability in the small regime, and dual-slot bucketed cardinality DP + exact second local search + exact bitset fallback in the scaled `200` candidate regime.
  - `_diagnose_unsatisfiable`: produces structured `CONSTRAINTS_UNSATISFIABLE` errors stating `N` retrieved candidates (explicitly distinguishing candidate pool from YouTube overall), naming `binding_constraint`, and supplying user confirmation options (`broader_search` at `1` search call + `1` metadata unit, plus named parameter relaxations).
- Added `UT_SOLV` / `UT_DUR` unit tests in `tests/unit/test_playlist_solver.py` and `X_PERF_SELECT` benchmark in `tests/perf/test_perf_budgets.py`.
- Updated `docs/traceability.md`, `brain/index.md`, and `brain/log.md`.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/projects/playlist-constraints|Playlist Duration and Spoken Language Constraints]]
- [[brain/resources/knapsack-constraint-solving|Knapsack Constraint Solving]]

## Verification
- Pending local check run (`ruff`, `mypy`, `validate_skills.py`, `validate_brain.py`, `pytest`) and CI checks on Pull Request.
