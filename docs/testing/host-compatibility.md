# MCP Host Compatibility Record (`TS-15`)

- **Task:** `TS-15`
- **Owner:** Molleti Tatwik Sai (`@tatwiksai080207`)
- **Reviewer:** Mohammed Farhan (`@farhan4599`)
- **GitHub Issue:** `#106`
- **Requirements:** SRS Section 2.3, `NFR-9`, `FR-5.4`, `TQ-8`

## 1. Compatibility Summary

| Host / Client | Version / Mode | Transport | Tool & Resource Discovery | Read Call (`get_video_details`) | Elicitation / Confirmation Capability | Observation Status |
|---|---|---|---|---|---|---|
| **Official Python `mcp` SDK Stdio Client** | `mcp` `ClientSession` (`YT_INTEL_PROVIDER=fixture`) | `stdio` | `8` tools and `2` resources discovered | `seedPy00001` succeeded (`10m 20s`, `2` chapters, metadata only summary) | Elicitation dialog when host declares `elicitation`; `127.0.0.1` loopback fallback or `CONFIRMATION_UNAVAILABLE` when omitted (`ST_FR5_CONFIRM`) | **Verified live over stdio** (`2026-11-28`) |
| **`scripts/local_check.py` (`SK-2`)** | Repo stdio verification runner (`YT_INTEL_PROVIDER=fixture`) | `stdio` | Initialized cleanly | `get_video_details` (`seedPy00001`) + `get_quota_status` (`0` live units) passed | Read only check (`N/A`) | **Verified live over stdio** (`2026-11-28`) |
| **Claude Code CLI (`claude.exe`)** | `2.1.322` (`--strict-mcp-config --mcp-config`) | `stdio` | CLI config accepted | Not run (`Not logged in · Please run /login`) | Supports MCP `elicitation` in authenticated Claude Code / Claude Desktop hosts | **Blocked on local auth** (`2026-11-28`) |
| **Gemini CLI (`gemini.ps1`)** | `0.70.0` (`gemini mcp add --scope project`) | `stdio` | Registered `yt-intel` in project settings | Failed at CLI startup (`This client is no longer supported for Gemini Code Assist for individuals`) | Loopback `127.0.0.1` confirmation fallback when host lacks `elicitation` | **CLI version unsupported** (`2026-11-28`) |

## 2. Observed Stdio Discovery, Read Call, and Elicitation Details

### 2.1 Server Identification and Discovery
Running `.venv\Scripts\python.exe -m yt_intel_mcp` with `YT_INTEL_PROVIDER=fixture` over `stdio`:
- **Server Info:** `yt-intel-mcp` version `0.1.0`
- **Tools Discovered (`8`):** `get_video_details`, `get_similar_videos`, `get_recommendations`, `analyze_engagement`, `draft_curated_playlist`, `create_curated_playlist`, `get_quota_status`, `get_auth_status`
- **Resources Discovered (`2`):** `youtube://user/context`, `youtube://metrics/quota`

### 2.2 Read Call Observation
Calling `get_video_details` with `{"video_id": "seedPy00001"}` returned:
- `summary`: `"Summary based on video metadata, not on the video's content: 'Python Asyncio Internals and Event Loops' by Systems Craft (10m 20s, 2 chapters)."`
- `data`: sanitized title, description, parsed chapters, duration, channel metadata, and `0` popularity statistics.

### 2.3 Elicitation Capability Matrix (`ST_FR5_CONFIRM`)
Verified in `tests/system/test_fr5_confirmation.py` (`6 passed in 1.09s`):
- **Host declares `elicitation` capability:** `create_curated_playlist` presents the structured confirmation dialog with account/channel, title, privacy (`private`), ordered video IDs, total duration, and expiry.
- **Host omits `elicitation` capability (e.g., standard stdio hosts without elicitation):** Server falls back to the single use `127.0.0.1` loopback confirmation page; if neither channel is reachable, returns `CONFIRMATION_UNAVAILABLE` with zero playlist writes.

## 3. Host Configuration Snippets

### Claude Code / Claude Desktop (`.mcp.json` or `claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "yt-intel": {
      "command": "python",
      "args": ["-m", "yt_intel_mcp"],
      "env": {
        "YT_INTEL_PROVIDER": "fixture"
      }
    }
  }
}
```

### VS Code (`.vscode/mcp.json`) and Gemini CLI (`gemini mcp add`)
```powershell
gemini mcp add --scope project --transport stdio --trust -e YT_INTEL_PROVIDER=fixture yt-intel python -m yt_intel_mcp
```

## 4. Defect Audit (`TQ-8`)

Zero server defects were observed during stdio discovery, read calls, or elicitation capability checks (`docs/testing/defect-log.md` requires no new `type:defect` entry). Interactive desktop verification in signed in Claude Desktop / Claude Code and VS Code Copilot GUI remains a human environment step when credentials for those host applications are active.
