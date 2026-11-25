---
name: local-check
description: Build the YouTube MCP server, run fixture-mode tests, verify the local stdio handshake, and report each verification step and any skipped fetch.
---

# Local Check

Run this skill before handing off a change that affects the server or the local development setup. See [[brain/areas/skill-local-check|Local Check Skill]] for the SK-2 verification contract.

## Run

Use a Python 3.11+ development environment with the project and its development dependencies installed. From the repository root, run:

```bash
python scripts/local_check.py
```

The runner builds a wheel in a temporary directory, runs `pytest -m "not live"` with `YT_INTEL_PROVIDER=fixture`, and initializes the current checkout's MCP server over stdio. It checks whether `get_video_details` is registered and reports the read-only fixture fetch as `NOT RUN` until MF-16 wires it in.

## Report

Report the build, tests, server startup, read-only fetch, and overall summary from the command output. Include the reason for any `FAIL` or `NOT RUN`. A failed build, test run, or handshake produces a nonzero exit status. A successful run with the expected fetch skip reports three passes and one step not run. Keep the verification in fixture mode so it uses zero live YouTube quota.
