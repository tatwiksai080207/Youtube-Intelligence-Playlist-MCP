---
name: local-check
description: Build the YouTube MCP server, run fixture-mode tests, verify the local stdio handshake, invoke read-only fetch and quota status tools, and report all verification steps.
---

# Local Check

Run this skill before handing off a change that affects the server or the local development setup. See [[brain/areas/skill-local-check|Local Check Skill]] for the SK-2 verification contract.

## Run

Use a Python 3.11+ development environment with the project and its development dependencies installed. From the repository root, run:

```bash
python scripts/local_check.py
```

The runner builds a wheel in a temporary directory, runs `pytest -m "not live"` with `YT_INTEL_PROVIDER=fixture`, initializes the current checkout's MCP server over stdio, and invokes both `get_video_details` (exercising a read-only fetch path per SDLC Section 3) and `get_quota_status` (verifying quota ledger status and zero live usage).

## Report

Report the build, tests, server startup, read-only fetch, and overall summary from the command output. Include the reason for any `FAIL` or `NOT RUN`. A failed build, test run, or handshake produces a nonzero exit status. On a clean repository checkout, all five steps report `PASS`. The verification runs strictly in fixture mode using zero live YouTube quota.
