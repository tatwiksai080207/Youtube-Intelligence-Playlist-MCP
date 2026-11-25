# Changelog

All notable changes to the YouTube Video Intelligence MCP Server (`yt-intel-mcp`) are documented in this file.

The format follows Keep a Changelog, and releases correspond to Stage milestones defined in `docs/developer/branching.md`.

## [Unreleased]

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
- **Stage 1 Review and Skill Evaluations (`TS-03`, `#9`):** `brain/projects/stage-1-review.md` and `docs/testing/skill-evals.md`.

### Fixed
- Granted `pull-requests: read` permission and `fetch-depth: 0` checkout in `.github/workflows/ci.yml` so `gitleaks` scans PR commits cleanly (`TS-00`, PR `#10`).
- Normalized `brain/log.md` entries and `skills/brain-ingest/SKILL.md` log format to consistent 4 column rows (`TS-02` PR `#14`, `TS-03` `#9`).
