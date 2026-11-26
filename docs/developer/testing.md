# Developer Testing Guide and MCP System Test Harness (`TQ-3`, `SE-7`)

All automated verification in `yt-intel-mcp` runs offline in fixture mode (`YT_INTEL_PROVIDER=fixture`) so pull request checks consume zero live YouTube Data API v3 quota and require no network access or OAuth secrets (`docs/testing/test-plan.md`).

## 1. Test Suite Layout

| Suite Path | Purpose | SRS Coverage |
|---|---|---|
| `tests/unit/` | Contracts, JSON Schemas, validation, durations, TF IDF scoring, validators | `TQ-1`, `CT_1`, `UT_*` |
| `tests/integration/` | Fixture and live provider parity, cache TTLs, playlist writer assembly | `TQ-2`, `IT_PROV`, `IT_CACHE`, `IT_DRAFT*` |
| `tests/system/` | MCP client and server system flows over shared harness (`tests/system/conftest.py`) | `TQ-3`, `ST_FR1`..`ST_FR5_CONFIRM` |
| `tests/negative/` | Rejection, unavailable videos, missing signals, language mismatches, HITL errors | `TQ-4`, `NT_*` |
| `tests/quota/` | Persistent dual quota ledger enforcement and insufficient budget zero call guards | `TQ-6`, `QT_1`..`QT_3` |
| `tests/security/` | Scrubbed fixtures, zero PII or tokens, encryption hygiene, sanitization | `SEC_PII`, `SEC_OAUTH`, `NFR-6` |
| `tests/perf/` | Deterministic benchmark assertions for similarity scoring and solver runtime | `NFR-1`, `X_PERF_*` |

## 2. Running Local Checks

Activate the virtual environment and run every static and fixture gate in offline mode:

```powershell
$env:YT_INTEL_PROVIDER = "fixture"
python scripts/validate_skills.py
python scripts/validate_brain.py
ruff check .
ruff format --check .
mypy src
pytest -m "not live" --cov=yt_intel_mcp --cov-fail-under=85
```

### Windows Platform Note for `tests/unit/test_validators.py`
The validator CLI scripts (`validate_skills.py` and `validate_brain.py`) pass on Windows and Linux. On Windows, `tests/unit/test_validators.py` reports 28 expected path separator mismatches where stderr formats relative paths with `\` instead of `/`. Linux CI (`ubuntu-latest`) runs the full `pytest -m "not live"` suite without exclusions. Locally on Windows you can run all non validator suites cleanly with:

```powershell
pytest -m "not live" --ignore=tests/unit/test_validators.py --cov=yt_intel_mcp --cov-fail-under=85
```

## 3. MCP System Test Harness (`tests/system/conftest.py`)

`SR-09` establishes a shared system test harness for `ST_FR1`..`ST_FR5_CONFIRM` and related negative confirmation flows without touching real user state in `~/.yt-intel-mcp`.

### Key Fixtures and Capabilities
1. **Isolated Storage and Fixture Environment (`system_data_dir`, `system_sqlite_path`, `system_env`, `system_config`):**
   - Redirects `YT_INTEL_DATA_DIR` to `tmp_path / "yt-intel-data"` and `YT_INTEL_FIXTURE_DIR` to `tests/fixtures`.
   - Initializes an isolated temporary SQLite database at `<tmp_path>/yt-intel-data/yt_intel.db` with `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA foreign_keys=ON`, and `PRAGMA busy_timeout=5000`.
2. **Offline Provider Wiring (`fixture_provider`, `SystemHarness.provider`):**
   - Instantiates `FixtureYouTubeProvider.from_config(...)` against scrubbed public and synthetic JSON fixtures.
   - Exposes `.calls`, `.total_quota_used`, `.created_playlists`, `.inserted_items`, `.set_error(...)`, and `.set_insert_failure(...)` directly to system tests so tests can assert zero API calls or inject deterministic faults.
3. **In Memory vs Stdio MCP Transports (`system_harness`, `stdio_system_harness`, `system_harness_factory`):**
   - `system_harness` runs an in process `MCPServer` connected to `ClientSession` over `anyio` memory streams (`transport="memory"`), allowing deterministic fault injection and temporary tool hooks via `configure_server`.
   - `stdio_system_harness` launches the real `python -m yt_intel_mcp` process over `stdio_client` (`transport="stdio"`) to verify process startup, JSON RPC stdio framing, and isolated environment handling end to end.
4. **Elicitation Capability Toggle and Outcome Simulation (`ElicitationRecorder`, `ElicitationResponseSpec`):**
   - Pass `enable_elicitation=True` to attach a recording `elicitation_callback` to `ClientSession`, advertising MCP `ClientCapabilities.elicitation` during `initialize`.
   - Pass `enable_elicitation=False` (or parametrize `elicitation_enabled=False`) to omit the callback so `ClientSession` advertises no `elicitation` capability, triggering loopback `127.0.0.1` fallback (`Channel B`) or `CONFIRMATION_UNAVAILABLE` (`NT_HITL_UNAVAIL`).
   - Simulate `accept`, `decline`, or `cancel` decisions via `elicitation_action`, custom payloads via `elicitation_content`, or ordered multi step interactions via `elicitation_sequence=[ElicitationResponseSpec(...), ...]`. Every server prompt and returned response is captured in `harness.elicitation`.

### Example Using `system_harness_factory`

```python
@pytest.mark.anyio
async def test_confirmation_declined(system_harness_factory):
    async with system_harness_factory(
        transport="memory",
        enable_elicitation=True,
        elicitation_action="decline",
    ) as harness:
        assert harness.elicitation_enabled is True
        # Invoke playlist tool via harness.call_tool_json(...)
        # Assert harness.elicitation.actions == ["decline"]
```

## 4. Opt In Live API Smoke Tests (`-m live`)

Live tests marked with `@pytest.mark.live` are strictly excluded from PR CI (`-m "not live"`). Live execution (`YT_INTEL_PROVIDER=live`) runs only on explicit developer consent or the scheduled workflow (`SR-16`) with a hard cap of 300 units and 10 `search.list` calls per run (`LiveTestConfig` in `src/yt_intel_mcp/config.py`).
