# Developer Setup Guide (SE-7, NFR-9)

This document provides instructions for setting up a local development environment for the YouTube Video Intelligence MCP Server (`yt-intel-mcp`).

## 1. Prerequisites

Before setting up the repository, verify that your machine has the following tools installed:

- **Python:** Version `3.11` or higher (`python --version`)
- **Git:** Version `2.30` or higher (`git --version`)
- **GitHub CLI:** Optional but recommended for pull request operations (`gh --version`)
- **C Compiler / Platform Tools:** Standard platform build tools if prebuilt wheels are unavailable for your operating system

## 2. Repository Cloning and Virtual Environment

Clone the repository and create an isolated virtual environment:

```bash
git clone https://github.com/tatwiksai080207/Youtube-Intelligence-Playlist-MCP.git
cd Youtube-Intelligence-Playlist-MCP

# Create a virtual environment using Python 3.11+
python -m venv .venv

# Activate the virtual environment:
# On Linux / macOS:
source .venv/bin/activate

# On Windows PowerShell:
.venv\Scripts\Activate.ps1
```

## 3. Package and Development Dependencies Installation

Install the package in editable mode with development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The `[dev]` optional dependencies install:
- `pytest` and `pytest-cov` for testing and coverage enforcement
- `ruff` for code linting and formatting
- `mypy` for static type checking
- `pyyaml` for Second Brain and skills YAML frontmatter parsing

## 4. Configuration and Environment Variables

The server configuration (`AppConfig` in `src/yt_intel_mcp/config.py`) reads environment variables to control provider mode, file storage locations, and quota parameters:

| Variable | Default Value | Description |
|---|---|---|
| `YT_INTEL_PROVIDER` | `fixture` | Provider mode: `fixture` (offline, zero quota) or `live` (Google YouTube Data API v3). PR CI strictly enforces `fixture`. |
| `YT_INTEL_DATA_DIR` | `~/.yt-intel-mcp` | Directory for local persistent SQLite database, encrypted tokens, and logs. |
| `YT_INTEL_FIXTURE_DIR` | `tests/fixtures` | Directory containing scrubbed public and synthetic user JSON fixtures. |
| `YT_INTEL_DAILY_UNITS` | `10000` | Daily quota units budget limit (resets midnight Pacific Time). |
| `YT_INTEL_DAILY_SEARCHES` | `100` | Daily `search.list` call budget limit (resets midnight Pacific Time). |
| `YT_INTEL_LOG_LEVEL` | `INFO` | Stderr logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

For local development and testing, always keep `YT_INTEL_PROVIDER=fixture` to ensure no live quota is consumed:

```powershell
$env:YT_INTEL_PROVIDER = "fixture"
```

## 5. Local Storage and SQLite Setup

The server uses SQLite in Write Ahead Logging (WAL) mode for local persistence:
- **Database Location:** `<YT_INTEL_DATA_DIR>/yt_intel.db` (defaults to `~/.yt-intel-mcp/yt_intel.db`).
- **Storage Initialization:** Managed automatically by `SQLiteStore` on first startup, creating tables for daily quota tracking, OAuth tokens, playlist drafts, confirmation tokens, and interest profile event observations.
- **Concurrency PRAGMAs:** The store applies `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA foreign_keys=ON`, and `PRAGMA busy_timeout=5000` to ensure safe concurrent access between the server process and test runners.

## 6. Running Local Verification Checks

Before submitting pull requests, run all static linters, validators, and unit tests:

```powershell
# 1. Validate Second Brain knowledge graph and skills YAML
python scripts/validate_skills.py
python scripts/validate_brain.py

# 2. Verify tool reference documentation matches schemas without drift
python scripts/generate_tool_reference.py --check

# 3. Check code style and formatting
ruff check src tests scripts
ruff format --check src tests scripts

# 4. Strict type checking
mypy src

# 5. Run test suite with coverage enforcement (>= 85 percent)
pytest -m "not live" --cov=yt_intel_mcp --cov-fail-under=85
```

### Windows Note for Validator Unit Tests
The validator CLI scripts pass across all platforms. On Windows, `tests/unit/test_validators.py` reports expected path separator differences in stderr output. You can exclude that single suite during local Windows testing:

```powershell
pytest -m "not live" --ignore=tests/unit/test_validators.py --cov=yt_intel_mcp --cov-fail-under=85
```

## 7. Starting the MCP Server Locally

You can launch the server over stdio to test MCP handshake and tool discovery:

```powershell
# Run the server in fixture mode over stdio
python -m yt_intel_mcp
```

Logging outputs strictly to `stderr` so as not to interfere with JSON RPC communication on `stdout`.
