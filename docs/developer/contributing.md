# Developer Contributing Guide (SE-7, NFR-9)

This document outlines the contribution workflow, coding standards, pull request policies, and Second Brain maintenance practices for the YouTube Video Intelligence MCP Server project.

## 1. Branching and Pull Request Workflow

All development activity follows the branching and pull request guidelines in `docs/developer/branching.md`:

1. **Start from clean main:** Always update your local `main` branch before branching:
   ```bash
   git checkout main
   git pull origin main
   ```
2. **Feature branches:** Create a dedicated branch using the convention `<member>/<TASK-ID>-<short-slug>`:
   ```bash
   git checkout -b shiva/SR-17-dev-docs
   ```
3. **One task, one branch, one pull request:** Every task is tracked by a single GitHub Issue and resolved by a single Pull Request referencing `Closes #<issue>`.
4. **No direct pushes to main:** All changes merge via Pull Request with passing CI and at least one human code review.

## 2. Commit Message Standards

Per repository rules:
- Commit messages must be clear, concise, and descriptive plain sentences.
- Avoid prefixes like `feat:`, `fix:`, `chore:`, or `update:`.
- Example of an accepted commit message: `Add developer setup and architecture documentation for SR-17`

## 3. Code Style and Quality Standards

All source code and test files must adhere to strict quality gates:

- **Python Version:** Python `3.11` or higher.
- **Linting and Formatting:** Enforced via `ruff`. Run `ruff check .` and `ruff format --check .`.
- **Static Typing:** Enforced via `mypy` in strict mode (`mypy src`). All public functions, parameters, and return types must carry explicit type annotations.
- **No Secrets:** Never commit `.env` files, API keys, OAuth client secrets, refresh tokens, or personal identifiers. The CI pipeline scans every commit using `gitleaks`.
- **Documentation Style:**
  - Do not use emojis in documentation, commit messages, or code comments. Keep documentation formal, clean, and professional.
  - Avoid using hyphens between words in prose and headings where natural spacing fits.

## 4. Architectural Boundaries and Provider Isolation

When contributing new tools, algorithms, or services, maintain the mandatory architectural boundaries:

- **Provider Boundary (SE-6, FR-8.1):** Never import HTTP clients (`urllib.request`, `requests`, `httpx`, `aiohttp`) or `googleapiclient` inside domain or tool modules. All external queries must go through `YouTubeProvider`.
- **No Upstream LLM Calls:** All computation is local and deterministic.
- **Objective Metadata Only (FR-1.3, FR-2.2):** Never use or request YouTube `statistics` (views, likes, subscriber counts).
- **Dual Quota Awareness (FR-6):** Every tool that may dispatch API calls must enforce preflight budget checks against `PersistentQuotaLedger`.

## 5. Testing and Coverage Requirements

- **Zero Quota PR CI (TQ-5):** All automated tests run against scrubbed public and synthetic fixtures with `YT_INTEL_PROVIDER=fixture`. No test should consume live YouTube API quota.
- **Minimum Test Coverage (TQ-4):** Pull requests must maintain at least `85 percent` branch and line coverage across the `yt_intel_mcp` package.
- **Regression Tests (TQ-8):** Every defect fix must include a reproducing regression test and a logged entry in `docs/testing/defect-log.md`.

## 6. Documentation and Schema Synchronization

When adding or modifying MCP tools:
1. Update the bundled JSON schema in `src/yt_intel_mcp/schemas/<tool_name>.json`.
2. Run the tool reference generator to update documentation:
   ```bash
   python scripts/generate_tool_reference.py
   ```
3. Verify that the drift check passes:
   ```bash
   python scripts/generate_tool_reference.py --check
   ```
   CI automatically enforces this check; pull requests with out of date documentation will fail the pipeline.

## 7. Second Brain Knowledge Graph Discipline

All non trivial engineering sessions must be recorded in the Second Brain (`brain/`):
- Maintain notes according to PARA structure (`inbox/`, `projects/`, `areas/`, `resources/`, `archive/`).
- Record AI assisted sessions under `brain/inbox/ai-session-YYYY-MM-DD-<member>-<task>.md`.
- Include standard YAML frontmatter: `title`, `type`, `status`, `authors`, `created`, `updated`, `tags`, `requirements`, `issues`, `prs`, `sources`.
- Validate the knowledge graph with `python scripts/validate_brain.py`.

## 8. Review and Merge Process

- Every pull request requires review from designated team members.
- Review and merging can be automated using the team operations helper script:
  ```powershell
  # Review and merge a verified PR
  .\agent_code\team_ops.ps1 -Action finish-pr -PrNumber <PR#> -Reviewer <REVIEWER_HANDLE> -Author <AUTHOR_HANDLE>
  ```
