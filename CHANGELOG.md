# Changelog

All notable changes to the YouTube Video Intelligence MCP Server (`yt-intel-mcp`) are documented in this file.

The format follows Keep a Changelog, and releases correspond to Stage milestones defined in `docs/developer/branching.md`.

## [Unreleased]

## [0.2.0] - 2026-11-26 (`stage-2`)

Stage 2 deliverable baseline: Accepted ADRs `0001` through `0007`, frozen shared domain and provider contracts (`CT-1`), strict draft 2020-12 JSON Schemas for all seven functional tools, system and subsystem architecture diagrams (`SE-2`), refined PARA Second Brain, core Agent Skills (`SK-2`, `SK-4`, `SK-5`), and master test and defect plans (`TQ-1` through `TQ-8`).

### Added
- **Runtime and Packaging Decision (`SR-03`, `#21`, PR `#22`):** Accepted `docs/adr/0001-runtime-and-toolchain.md` confirming Python 3.11+, the official `mcp` SDK, toolchain standards, and `src/yt_intel_mcp/schemas/` (`D-02` and `C-02` resolved).
- **Shared Core Contracts Freeze (`SR-04`, `#25`, PR `#26`):** Froze `errors.py` (17 `ErrorCode`s, envelopes, `map_upstream_error`), objective `models.py` (`INV-01`), `config.py` defaults, `YouTubeProvider` Protocol (`SE-6`), `QuotaGuard` Protocol, Stage 2 stubs (`sanitize.py`, `validation/ids.py`), `docs/adr/0002-provider-and-errors.md`, `docs/developer/fixtures.md`, and `tests/unit/test_contracts.py`.
- **`brain-refine` Skill and First PARA Run (`TS-05`, `#19`, PR `#20`):** Authored `skills/brain-refine/SKILL.md` (`SK-4`) and `brain/areas/skill-brain-refine.md`, consolidated duplicate OAuth notes, promoted seven Stage 1 research notes to `status: distilled` PARA folders, and repaired vault links.
- **`local-check` Skill v1 (`MF-05`, `#23`, PR `#24`):** Authored `skills/local-check/SKILL.md` (`SK-2`), `scripts/local_check.py`, `brain/areas/skill-local-check.md`, and `tests/unit/test_local_check.py` verifying wheel build, fixture tests, and stdio MCP initialization.
- **Analysis Design Contract (`TS-04`, `#27`, PR `#29`):** Authored five strict tool JSON Schemas (`get_video_details`, `get_similar_videos`, `get_similar_channels`, `get_recommendations`, `analyze_engagement`), `docs/adr/0003-similarity-scoring.md`, `docs/adr/0007-interest-profile.md` (`G-05` and `G-06` resolved), `docs/architecture/analysis.md`, `tests/unit/test_analysis_schemas.py`, and logged team decision `G-01` in Issue `#28`.
- **System Architecture and Persistence (`SR-05`, `#30`, PR `#31`):** Authored `docs/architecture/overview.md` (component, deployment, SQLite `erDiagram` for `quota_ledger`/`cache_entries`/`first_observed`, quota preflight, and OAuth flows) and `docs/adr/0006-token-storage-and-persistence.md` (OS keyring, `AES-256-GCM` fallback, WAL SQLite, delete on revoke).
- **`brain-query` Skill (`SR-06`, `#32`, PR `#33`):** Authored `skills/brain-query/SKILL.md` (`SK-5`), distilled `brain/areas/skill-brain-query.md`, and `SE-QRY-01`–`SE-QRY-04` evaluations with a vault grounded drafted specification excerpt.
- **Playlist Design Contract (`MF-04`, `#34`, PR `#35`):** Authored `draft_curated_playlist.json` and `create_curated_playlist.json` (`draft_id` only), `docs/adr/0004-trusted-confirmation.md` (`G-02` resolved), `docs/adr/0005-playlist-selection.md` (`G-03` resolved), `docs/architecture/playlist.md`, and `tests/unit/test_playlist_schemas.py`.
- **Master Test Plan and Defect Log (`MF-06`, `#36`, PR `#37`):** Authored `docs/testing/test-plan.md` mapping all SRS test IDs, PR vs. scheduled live CI, and `NFR-1` benchmark protocol plus `docs/testing/defect-log.md` (`TQ-8`).
- **Stage 2 Review and Audit (`SR-07`, `#38`, PR `#39`):** Authored `brain/projects/stage-2-review.md`, compiled Stage 2 skill evaluation evidence in `docs/testing/skill-evals.md`, and completed the `SB-1` back link audit across `docs/traceability.md` and `brain/`.

## [0.1.0] - 2026-11-25 (`stage-1`)

Stage 1 deliverable baseline: Requirements specification, Second Brain foundation, Python package skeleton, standalone validators, and gating fixture CI.

### Added
- **Requirements Baseline (`SE-1`):** `Final_SRS_Submission.pdf` (version 1.0) defining `FR-1` through `FR-8`, `SK-1` through `SK-5`, `NFR-1` through `NFR-10`, `TQ-1` through `TQ-8`, and verification traceability.
- **Repository Governance and Templates (`TS-00`, `#1`, PR `#10`):** Reconciled root `AGENTS.md`, `docs/developer/branching.md`, `docs/plan/development-plan.md` with Architectural Decision and Conflict Register, `docs/traceability.md`, `.github/ISSUE_TEMPLATE/{task,defect}.md`, and `.github/pull_request_template.md`.
- **Python Package and Stdio MCP Server (`SR-01`, `#2`, PR `#11`):** `pyproject.toml` and `src/yt_intel_mcp/` (`__init__.py`, `__main__.py`, `server.py`) with MCP `initialize` handshake smoke test (`tests/unit/test_smoke.py`).
- **Skill and Second Brain Validators (`MF-01`, `#4`, PR `#12`):** Standalone `scripts/validate_skills.py`, `scripts/validate_brain.py`, `scripts/_validation.py`, `scripts/srs_ids.txt`, and unit test fixtures (`tests/unit/test_validators.py`).
- **Second Brain Vault and `brain-ingest` (`TS-01`, `#3`, PR `#13`):** Distilled architecture note `brain/areas/second-brain.md` (`SB-3`), updated `skills/brain-ingest/SKILL.md`, and 10 aligned foundational research notes.
- **Team Research Notes (`SB-6`):**
  - Tatwik (`TS-02`, `#6`, PR `#14`): `channel-similarity.md`, `youtube-event-timestamps.md`, `engagement-analysis.md`.
  - Shiva (`SR-02`, `#5`, PR `#15`): `nfr-targets.md`, `oauth-scopes-and-token-storage.md`, and distilled infrastructure notes.
  - Farhan (`MF-03`, `#7`, PR `#17`): `mcp-elicitation-confirmation.md`, `playlist-constraints.md`, `partial-playlist-outcomes.md`, and distilled prompt injection defence note.
- **Gating CI Pipeline (`MF-02`, `#8`, PR `#16`):** Enforced `gitleaks`, `ruff check`, `ruff format --check`, `mypy src`, `pytest -m "not live" --cov=yt_intel_mcp --cov-fail-under=85`, `validate_skills.py`, and `validate_brain.py` under `YT_INTEL_PROVIDER=fixture`.
- **Stage 1 Review and Skill Evaluations (`TS-03`, `#9`, PR `#18`):** `brain/projects/stage-1-review.md` and `docs/testing/skill-evals.md`.

### Fixed
- Granted `pull-requests: read` permission and `fetch-depth: 0` checkout in `.github/workflows/ci.yml` so `gitleaks` scans PR commits cleanly (`TS-00`, PR `#10`).
- Normalized `brain/log.md` entries and `skills/brain-ingest/SKILL.md` log format to consistent 4 column rows (`TS-02` PR `#14`, `TS-03` `#9`).
