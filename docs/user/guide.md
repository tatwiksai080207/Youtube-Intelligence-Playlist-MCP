# YouTube Video Intelligence MCP Server User Guide

This guide explains how to install, configure, connect, and use the YouTube Video Intelligence MCP Server (`yt-intel-mcp`).

## 1. Overview and Core Guarantees

`yt-intel-mcp` is a deterministic Model Context Protocol (MCP) server for YouTube video discovery, explicit library analytics, and constraint based playlist curation.

- **Objective metadata ranking:** Video similarity and recommendations use title, tags, description, category, and duration signals only. View counts, like counts, comment counts, and subscriber counts are never requested or used.
- **Deterministic local execution:** The server performs local TF IDF scoring and constraint solving without making upstream LLM calls.
- **Dual daily quota protection:** Every live API tool enforces a persistent daily budget (`10,000` quota units and `100` `search.list` calls per day, resetting at `00:00` Pacific Time) via preflight checks before sending API requests.
- **Trusted playlist confirmation:** Creating a YouTube playlist always requires out of band human approval through MCP elicitation or the local `127.0.0.1` confirmation page.

## 2. Installation and Prerequisites

### Requirements
- Python `3.11` or newer
- An MCP compatible host (such as Claude Desktop, Cursor, Gemini CLI, or VS Code)
- For live YouTube access: an existing Google Cloud project with YouTube Data API v3 enabled

### Local Setup
Clone the repository and install the package in editable mode inside a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
```

To verify the installation offline using scrubbed public and synthetic fixtures without spending live quota:

```bash
YT_INTEL_PROVIDER=fixture python -m yt_intel_mcp
```

## 3. Google Cloud OAuth Client and Test User Setup

Do **not** create extra Google Cloud projects for this server. Reuse your existing approved Google Cloud project.

1. Open the Google Cloud Console for your existing project and confirm **YouTube Data API v3** is enabled under **APIs & Services > Library**.
2. Open **APIs & Services > OAuth consent screen**:
   - Keep the app in **Testing** publishing status.
   - Add your Google account email address under **Test users**.
3. Open **APIs & Services > Credentials**:
   - Create an **OAuth client ID** of type **Desktop app**.
   - Download the client credentials JSON or copy the client ID and client secret into your local environment or configuration (never commit credentials or `.env` files to version control).
4. **Least privilege scopes:**
   - Initial login requests read only access (`https://www.googleapis.com/auth/youtube.readonly`).
   - Write access (`https://www.googleapis.com/auth/youtube.force-ssl`) is requested separately only when creating a confirmed playlist, and only if your account owns a YouTube channel.

## 4. Seven Day Reauthorization and Token Storage

Because the OAuth consent screen remains in **Testing** mode, Google expires refresh tokens after **7 days**.

- When a refresh token expires or is revoked (`invalid_grant`), the server returns `AUTH_REAUTHORIZATION_REQUIRED`. Re run the OAuth login flow to obtain a fresh token.
- Tokens are stored encrypted at rest using the OS keyring when available, with an AES 256 GCM encrypted fallback file (`tokens.enc`) inside your local data directory (`~/.yt-intel-mcp`).
- Tokens are never returned by tools or written to logs. Revoking authorization deletes stored tokens alongside cached personal lists and local `first_observed` timestamps.

## 5. Connecting to an MCP Host

Configure your MCP host to launch `yt-intel-mcp` over stdio. Replace `/path/to/python` with the Python interpreter inside your virtual environment.

### Example MCP Server Entry (`mcpServers`)

```json
{
  "mcpServers": {
    "yt-intel-mcp": {
      "command": "/path/to/python",
      "args": ["-m", "yt_intel_mcp"],
      "env": {
        "YT_INTEL_PROVIDER": "live"
      }
    }
  }
}
```

For offline testing or demonstrations without live API calls, set `"YT_INTEL_PROVIDER": "fixture"`.

## 6. Available Tools and Resources

### `get_video_details`
Fetch sanitized objective metadata for a single video by 11 character ID or YouTube URL, including parsed timestamped chapters, human readable duration, live status, and spoken audio language.
- **Example arguments:** `{"video_id": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}`
- **Typical quota cost:** `1` unit, `0` search calls.

### `get_similar_videos`
Rank candidate videos against a seed video using TF IDF cosine similarity across title, tags, description, category, and duration with dynamic weight redistribution when seed tags or durations are absent.
- **Example arguments:** `{"video_id": "dQw4w9WgXcQ", "max_results": 10}`
- **Typical quota cost:** `<= 1` search call + `2` units.

### `get_recommendations`
Build a 90 day half life interest profile from explicit YouTube library actions (`liked_video`, `subscription`, `playlist_item`), exclude already liked or saved videos, and return recommendations with human readable reasons.
- **Example arguments:** `{"max_results": 10, "sources": ["liked_video", "subscription", "playlist_item"]}`
- **Typical quota cost:** `<= 3` search calls + `<= 25` units.

### `analyze_engagement`
Compute aggregate topic shares, duration buckets (`< 4m`, `4m to 20m`, `> 20m`, excluding live and zero duration items), monthly trends, and period comparisons with a minimum 5 dated event confidence guard.
- **Example arguments:** `{"timeframe": "90d", "compare_with_previous_period": true}`
- **Typical quota cost:** `<= 9` units, `0` search calls.

### `draft_curated_playlist`
Search objective candidates, filter by spoken audio language (`defaultAudioLanguage` only) and per video duration, and solve for an immutable 10 minute expiring draft within your target total duration window (`[T * (1 - tol), T]`). Performs zero YouTube writes.
- **Example arguments:** `{"topic": "python asyncio", "target_total_minutes": 45, "tolerance_percent": 10, "max_video_minutes": 20, "language": "en"}`
- **Typical quota cost:** `<= 3` search calls + `<= 5` list units.

### `create_curated_playlist`
Create a YouTube playlist from an existing `draft_id` after out of band trusted confirmation. Verifies draft freshness, write scope, channel presence, and exact write quota before inserting the playlist and each item with zero automatic retries.
- **Example arguments:** `{"draft_id": "<draft_id_from_draft_curated_playlist>"}`
- **Typical quota cost:** `50 + 50 * N` units for `N` videos, `0` search calls.

### `get_quota_status` and `get_auth_status`
Inspect remaining daily quota units/search calls and current OAuth authentication status (scopes and channel presence flag only, never tokens).
- **Typical quota cost:** `0` units, `0` search calls.

### Read Only MCP Resources
- `youtube://metrics/quota`: Live snapshot of daily quota usage and next Pacific Time reset (`0` quota).
- `youtube://user/context`: Privacy preserving aggregate summary of explicit library signals (`0` raw personal IDs).

## 7. Trusted Confirmation Flow

Playlist creation (`create_curated_playlist`) is a write operation and never runs from chat text alone.

1. Call `draft_curated_playlist` to inspect the proposed video list, total duration, spoken audio language labels, and quota cost.
2. Call `create_curated_playlist` with the returned `draft_id`.
3. The server initiates one of two trusted confirmation channels:
   - **MCP elicitation:** If your MCP host supports elicitation dialogs, it displays the sanitized target channel, playlist title, privacy status (`private` by default), ordered video list, total duration, and draft expiry.
   - **Local loopback page (`127.0.0.1`):** Otherwise, the server starts an ephemeral HTTP listener bound strictly to `127.0.0.1` on an unguessable path with CSRF protection and opens it for your explicit Accept or Decline action.
4. Approval mints a single use server held confirmation token bound to the exact draft ID, channel ID, ordered video IDs, title, and privacy status. Chat messages, tool arguments, and video descriptions can never approve or mint a token.

## 8. Privacy and Data Handling

- **Explicit library signals only:** Recommendations and engagement analytics use your explicit likes, subscriptions, and playlists. Watch history is never accessed.
- **Aggregates only in engagement views:** `analyze_engagement` and `youtube://user/context` omit all raw `video_id`, `channel_id`, and `playlist_id` values.
- **Prompt injection defense:** All untrusted YouTube metadata is normalized and sanitized (`NFKC`, invisible/bidi/control character stripping, URL removal, and HTML escaping on the confirmation page).

## 9. Out of Scope Exclusions

Per SRS Section 1.2, `yt-intel-mcp` intentionally excludes:
- Web scraping or unofficial YouTube APIs
- Watch history access
- Video or audio downloading and playback
- Video transcripts or audio visual content analysis
- Editing or deleting existing YouTube playlists
- Creating extra Google Cloud projects
