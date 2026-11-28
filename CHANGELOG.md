# Changelog

All notable changes to the YouTube Video Intelligence MCP Server (`yt-intel-mcp`) are documented in this file.

The format follows Keep a Changelog, and releases correspond to Stage milestones defined in `docs/developer/branching.md`.

## [Unreleased]

## [1.0.0] - 2026-11-28 (`v1.0.0`)

Stage 4 deliverable baseline: Complete system delivery of the YouTube Video Intelligence MCP Server (`yt-intel-mcp`), end to end traceability matrix audit, resolution of all Architectural Decision Register entries, live demonstration checklist with team viva ownership, and verified compliance across all quality gates.

### Added
- **Final Quality and Compliance Audit (`MF-18`, `#98`, PR `#99`):** Executed full quality audit on `main` verifying test coverage exceeding 91 percent, strict Mypy typing, Ruff linting, secret scanning via Gitleaks, zero live API quota consumption in PR CI, and distilled Second Brain note citations.
- **Stage 4 Live Demo and Viva Preparation (`TS-17`, `#102`, PR `#103`):** Authored `docs/demo/stage-4-checklist.md` with step by step MCP client verification for all tools, human in the loop trusted confirmation, local check skill run, Second Brain query walkthrough, and viva speaking ownership breakdown for all three teammates.
- **Final Traceability Matrix and Release Baseline (`SR-18`, `#104`):** Completed comprehensive audit of `docs/traceability.md`, resolved open items `G-01` and `G-04` in `docs/plan/development-plan.md`, verified bidirectional Second Brain links, and finalized `v1.0.0` release documentation.

## [0.3.0] - 2026-11-28 (`stage-3`)

Stage 3 deliverable baseline: Full implementation of all seven functional MCP tools, dual confirmation channels (MCP elicitation and loopback page), persistent quota governance and caching, token encryption at rest, live and fixture providers with AST import boundary protection, end to end Agent Skills (`SK-1`, `SK-2` v2), developer guides, and end user documentation.

### Added
- **Synthetic Fixtures & Provider (`SR-08`, `#40`, PR `#41`):** Authored `src/yt_intel_mcp/provider/fixture.py`, synthetic user data, and scrubber for offline testing.
- **System Test Harness (`SR-09`, `#42`, PR `#43`):** Authored `tests/system/` conftest, stdio client harness, and test runner documentation.
- **Dual Budget Quota Ledger (`SR-10`, `#44`, PR `#45`):** Authored persistent SQLite quota ledger, preflight checks, `get_quota_status` tool, and `youtube://metrics/quota` resource.
- **TTL Metadata Cache (`SR-11`, `#46`, PR `#47`):** Authored SQLite cache backend with TTL policies for videos, channels, and queries.
- **ID and URL Validation (`TS-06`, `#48`, PR `#49`):** Implemented strict YouTube ID formats and URL extraction helpers.
- **Metadata Sanitisation (`MF-07`, `#50`, PR `#51`):** Implemented NFKC normalisation, control character removal, and link stripping for untrusted metadata.
- **ISO-8601 Durations (`TS-07`, `#52`, PR `#53`):** Implemented ISO-8601 duration parser and formatter.
- **Playlist Constraints (`MF-08`, `#54`, PR `#55`):** Implemented constraint model with strict duration window bounds.
- **TF-IDF Similarity Engine (`TS-08`, `#56`, PR `#57`):** Implemented local term frequency inverse document frequency and cosine similarity calculation.
- **Audio Language Validator (`MF-09`, `#58`, PR `#59`):** Enforced `defaultAudioLanguage` filter with unknown language flags.
- **Knapsack Selection Solver (`MF-10`, `#60`, PR `#61`):** Implemented relevance maximising knapsack solver with diagnostic unsat reporting.
- **Draft Tool & Immutability (`MF-11`, `#62`, PR `#63`):** Authored `draft_curated_playlist` tool and expiring draft store.
- **Video Details Tool (`TS-09`, `#64`, PR `#65`):** Authored `get_video_details` tool returning objective metadata and chapter parsing.
- **Encrypted Token Store (`SR-12`, `#66`, PR `#67`):** Authored keyring and AES-256-GCM token storage and `get_auth_status` tool.
- **OAuth PKCE & Channel Verification (`SR-13`, `#68`, PR `#69`):** Authored desktop OAuth 2.0 PKCE flow, token refresh, and write consent checks.
- **Single Use Tokens (`MF-12`, `#70`, PR `#71`):** Implemented server side cryptographically bound confirmation tokens.
- **Trusted Confirmation Channels (`MF-13`, `#72`, PR `#73`):** Authored MCP elicitation handler and single use loopback `127.0.0.1` page.
- **Live Provider (`SR-14`, `#74`, PR `#75`):** Implemented live YouTube Data API v3 provider passing through `YouTubeProvider`.
- **Similar Videos Tool (`TS-10`, `#76`, PR `#77`):** Authored `get_similar_videos` tool evaluating objective title and category metadata.
- **Playlist Creation Write Path (`MF-14`, `#78`, PR `#79`):** Authored `create_curated_playlist` tool with stale checks and partial outcome reporting.
- **Event Time Profile (`TS-12`, `#80`, PR `#81`):** Implemented exponential half life interest profile and recency scoring.
- **Recommendations Tool (`TS-13`, `#82`, PR `#83`):** Authored `get_recommendations` tool blending similarity and interest profiles.
- **Engagement Analysis Tool (`TS-14`, `#84`, PR `#85`):** Authored `analyze_engagement` tool and `youtube://user/context` resource.
- **Server Integration & Import Boundary (`SR-15`, `#86`, PR `#87`):** Wired MCP server lifecycle and verified provider boundary protection via AST lint.
- **Product Skill `video-to-playlist` (`MF-15`, `#88`, PR `#89`):** Authored `SK-1` skill with metadata summary disclaimer and 600 quota unit envelope.
- **User Guide (`TS-16`, `#90`, PR `#91`):** Authored end user documentation `docs/user/guide.md`.
- **Local Check Skill v2 (`MF-16`, `#92`, PR `#93`):** Upgraded `scripts/local_check.py` to v2 (`SK-2`) with live stdio fixture fetch and zero quota check.
- **Developer Documentation & Generator (`SR-17`, `#94`, PR `#95`):** Authored developer guides, automated reference generator, and CI drift check.
- **Stage 3 Review and Audit (`MF-17`, `#96`, PR `#97`):** Authored `docs/testing/ci-results.md`, audited defect log, compiled skill evals, and wrote `brain/projects/stage-3-review.md`.

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
