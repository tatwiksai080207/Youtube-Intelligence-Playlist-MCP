# AI Agent Guidelines YouTube Video Intelligence MCP Server (yt-intel-mcp)

## 1. Project and Baseline
This repository implements the YouTube Video Intelligence MCP Server (yt-intel-mcp) for IIIT Bangalore Software Engineering Lab (Team Whatsup).
- **Product Baseline:** `Final_SRS_Submission.pdf` (version 1.0, strictly binding).
- **Development Plan and Decision Register:** `docs/plan/development-plan.md`
- **Traceability Matrix:** `docs/traceability.md`
- **Branching and PR Policy:** `docs/developer/branching.md`

## 2. Mandatory Architectural and Product Boundaries
- **Provider Isolation (SE-6, FR-8.1):** All YouTube Data API v3 calls MUST pass through `YouTubeProvider`. Domain modules MUST NEVER import HTTP or Google client libraries directly.
- **Deterministic Server:** The server performs local metadata scoring and constraint solving only; it MUST NEVER make upstream LLM calls.
- **Objective Metadata Only (FR-1.3, FR-2.2):** View, like, and subscriber counts MUST NEVER affect similarity or channel rankings. Never request `statistics`.
- **Trusted Confirmation (FR-5.4, NFR-6):** Playlist creation (`create_curated_playlist`) MUST require out of band trusted confirmation via MCP elicitation or the server one-time 127.0.0.1 confirmation page. Chat text, tool arguments, and video metadata NEVER constitute approval.
- **Dual Quota Enforcement (FR-6, C-2):** Track both daily budgets (10,000 units per day and 100 `search.list` calls per day, configurable, resetting at 00:00 Pacific Time) in a persistent ledger. Every tool MUST run preflight checks before dispatching API calls.
- **Exclusions (Section 1.2):** No scraping, unofficial APIs, watch history, downloads, playback, transcripts, audio visual analysis, editing or deleting existing playlists, or extra Google Cloud projects.

## 3. Second Brain (brain/) and Agent Skills (skills/)
- Maintain engineering knowledge in `brain/` using PARA (`inbox/`, `projects/`, `areas/`, `resources/`, `archive/`), `index.md`, and `log.md`.
- All notes use `[[wikilinks]]`, valid SRS v1.0 requirement IDs, real Issue and PR back-links (SB-1), and standard YAML frontmatter (`status`, `authors`, `sources`, `requirements`, `issues`, `prs`).
- Every ADR (`docs/adr/`) and every `skills/<name>/SKILL.md` MUST cite at least one distilled brain note (SB-3).
- Record significant AI assisted sessions as `brain/inbox/ai-session-YYYY-MM-DD-<member>-<task>.md`.
- All changes to code, skills, docs, and `brain/` MUST go through Pull Requests with at least one human review.

## 4. Security and Testing Rules
- NEVER commit secrets, OAuth client secrets, refresh tokens, `.env`, or real personal data.
- NEVER paste secrets, tokens, or credentials into AI tools.
- PR CI MUST run strictly against scrubbed public fixtures and synthetic user fixtures (`YT_INTEL_PROVIDER=fixture`), consuming zero live API quota.
- Maintain at least 85 percent test coverage, passing lint (`ruff`), strict typing (`mypy`), secret scanning (`gitleaks`), and SKILL/brain validators.
- Real defects MUST be logged in `docs/testing/defect-log.md` with a GitHub Issue and regression test (TQ-8).
