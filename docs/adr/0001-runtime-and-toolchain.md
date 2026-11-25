# ADR-0001: Runtime Stack, Official MCP SDK, Toolchain, and Schemas Package Path

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-25 |
| **Task** | `SR-03` (`[CONTRACT]`) |
| **GitHub Issue** | `#21` |
| **GitHub PR** | `#22` |
| **Author** | Madire Shiva Reddy (`@Shiva0025`) |
| **Reviewers** | Molleti Tatwik Sai (`@tatwiksai080207`), Mohammed Farhan (`@farhan4599`) |
| **Requirements & Decisions** | `SRS Section 2.3`, `SE-3`, `SB-3`, `NFR-10`, `D-02`, `C-02` |
| **Distilled Brain Notes Cited (`SB-3`)** | [[brain/resources/mcp-protocol-specification|Model Context Protocol Architecture and Primitives]], [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]], [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern and Dependency Inversion]], [[brain/areas/second-brain|Second Brain Architecture and Knowledge Management]] |

---

## 1. Context

1. **Runtime & SDK Selection (`D-02`, SRS Section 2.3):** The Stage 1 SRS provisionally designates Python 3.11+ with the official Model Context Protocol (MCP) SDK, while permitting Node.js LTS as an accepted alternative pending a final Stage 2 ADR decision (`ADR-0001`). In Stage 1, `SR-01` (PR `#11`) implemented the installable `yt-intel-mcp` package skeleton in Python with `mcp>=2.3,<3` (`mcp.server.mcpserver.MCPServer` over `stdio`), `MF-01` (PR `#12`) implemented Python-based skill and Second Brain validators, and `MF-02` (PR `#16`) made Python 3.11 CI checks gating.
2. **Schemas Directory Path Conflict (`C-02`, SRS Section 3.1 vs. PyPI `mcp` Package):** SRS Section 3.1 states *"Full schemas will live in `src/mcp/schemas/` (Stage 2)"*. However, the official Python MCP SDK installs the top-level module namespace `mcp` (`from mcp.server.mcpserver import MCPServer`). Creating a directory `src/mcp/schemas/` under `src/` introduces a top-level `mcp` directory alongside `src/yt_intel_mcp/` that risks PEP 420 implicit namespace shadowing or import resolution conflicts when `src/` is on `sys.path` (editable installs, local scripts, or `PYTHONPATH=src`) and sits outside the built `yt_intel_mcp` wheel package.
3. **Quality & Maintainability Baseline (`NFR-10`, `SE-6`):** The selected stack must support strict static typing (`mypy`), fast deterministic local similarity scoring (`NFR-1`) and constrained playlist solving (`NFR-1`), isolated `YouTubeProvider` boundaries (`SE-6`), and `>= 85%` branch-aware test coverage in zero-quota CI (`TQ-5`).

---

## 2. Decision

1. **Confirm Python 3.11+ and Official `mcp` SDK (`D-02` -> `RESOLVED`):**
   - Standardise permanently on **Python `>=3.11`** (CI target `"3.11"`, verified compatible up to Python `3.14`) and the official Python MCP SDK **`mcp>=2.3,<3`** using `mcp.server.mcpserver.MCPServer` over `stdio` (`SRS Section 3.3`).
   - Use **`hatchling`** as the PEP 517/518 build backend defined in `pyproject.toml`, exposing the console entrypoint `yt-intel-mcp = "yt_intel_mcp.__main__:main"`.
2. **Confirm Development & Quality Toolchain (`NFR-10`):**
   - Test execution & coverage: `pytest>=8`, `pytest-cov>=5` (branch coverage enabled, `--cov-fail-under=85`), `anyio>=4` (`asyncio` backend).
   - Linting & formatting: `ruff>=0.6` (`line-length = 100`, `target-version = "py311"`, rules `E, F, W, I, B, UP, N, SIM, RUF`).
   - Static type checking: `mypy>=1.11` (`python_version = "3.11"`, `strict = true`, `files = ["src"]`) plus `types-PyYAML` and `pyyaml>=6`.
3. **Place Tool JSON Schemas in `src/yt_intel_mcp/schemas/` (`C-02` -> `RESOLVED`):**
   - Store all strict MCP tool JSON Schema files (`<tool>.json`, `"additionalProperties": false`) under **`src/yt_intel_mcp/schemas/`** (`yt_intel_mcp.schemas` package data) instead of top-level `src/mcp/schemas/`.
   - Load schemas cleanly inside runtime validation and doc generation (`SR-17`) via `importlib.resources` / package-relative paths, ensuring they ship in built wheels (`packages = ["src/yt_intel_mcp"]`) without conflicting with the external `mcp` SDK namespace.

---

## 3. Alternatives Considered

1. **Node.js LTS + Official TypeScript MCP SDK (`SRS Section 2.3` alternative):**
   - *Rejected:* Switching runtimes in Stage 2 would discard the already merged `SR-01` stdio server and smoke tests, `MF-01` Python validators, and `MF-02` gating CI pipeline. Python 3.11+ provides native `zoneinfo` (for DST-aware `00:00 America/Los_Angeles` quota resets), `sqlite3` (WAL mode), `unicodedata` (NFKC sanitisation), and a unified single-language codebase.
2. **Keeping `src/mcp/schemas/` as specified literally in `SRS Section 3.1`:**
   - *Rejected:* Even without `src/mcp/__init__.py`, placing `src/mcp/` under `src/` creates a PEP 420 namespace package collision risk whenever `src/` precedes `site-packages` on `sys.path`, potentially breaking `import mcp.server.mcpserver` or `import mcp.client.stdio`. Moving schemas into `src/yt_intel_mcp/schemas/` cleanly preserves single-package layout (`yt_intel_mcp`) and requires updating no runtime behavior.

---

## 4. Consequences

- **Resolved Register Items:** `D-02` and `C-02` are marked **`RESOLVED`** in `docs/plan/development-plan.md`, and the provisional header comment in `pyproject.toml` is updated to reflect acceptance.
- **Unblocked Downstream Stage 2 Work:**
  - `SR-04` can freeze shared contracts (`errors.py`, `models.py`, `provider/base.py`, `quota/guard.py`, `config.py`) in `src/yt_intel_mcp/`.
  - `TS-04` and `MF-04` have a frozen, conflict-free target directory (`src/yt_intel_mcp/schemas/`) for all tool JSON Schemas.
  - `SR-17` can generate `docs/developer/tool-reference.md` directly from `src/yt_intel_mcp/schemas/*.json`.
- **Change Control:** Because `SR-03` is a `[CONTRACT]` ADR, any future change to the minimum Python version, `mcp` SDK major version (`<3`), or schemas package location requires a superseding ADR approved by both peer reviewers (`@tatwiksai080207` and `@farhan4599`).

---

## 5. References

- `Final_SRS_Submission.pdf` (v1.0): Section 2.3 (Operating Environment), Section 3.1 (MCP Tools), Section 5 (`NFR-1`, `NFR-5`, `NFR-9`, `NFR-10`).
- `pyproject.toml`, `src/yt_intel_mcp/server.py`, `tests/unit/test_smoke.py`, `.github/workflows/ci.yml`.
- Distilled Second Brain notes:
  - [[brain/resources/mcp-protocol-specification|Model Context Protocol Architecture and Primitives]]
  - [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
  - [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern and Dependency Inversion]]
  - [[brain/areas/second-brain|Second Brain Architecture and Knowledge Management]]

