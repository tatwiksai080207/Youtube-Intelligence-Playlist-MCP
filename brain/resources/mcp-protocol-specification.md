---
title: Model Context Protocol Architecture and Primitives
type: reference
status: distilled
authors:
  - Molleti Tatwik Sai
  - Madire Shiva Reddy
created: 2026-11-09
updated: 2026-11-25
tags:
  - mcp
  - protocol
  - architecture
  - tools
  - elicitation
requirements:
  - FR-5
  - FR-5.4
  - NFR-5
  - NFR-9
  - NFR-10
  - SB-1
  - SB-6
issues:
  - "#1"
  - "#2"
  - "#5"
prs:
  - "#10"
  - "#11"
  - "#15"
sources:
  - "Model Context Protocol Specification 2025-06-18: https://modelcontextprotocol.io/specification/2025-06-18 (checked 2026-11-25)"
  - "Model Context Protocol Elicitation Specification 2025-06-18: https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation (checked 2026-11-25)"
  - "Final_SRS_Submission.pdf Section 2.1, 2.3, 3.1, 3.3, 4.5, 5 (checked 2026-11-25)"
---

# Model Context Protocol Architecture and Primitives

## Summary
The Model Context Protocol (MCP, revision `2025-06-18`) standardises JSON-RPC 2.0 communication between AI host applications, embedded MCP clients, and local servers exposing tools, read-only resources, and user elicitation dialogs. In Python (`mcp>=2.3,<3`), `yt-intel-mcp` builds on `mcp.server.mcpserver.MCPServer` over `stdio`.

## Core Protocol Concepts and SRS Mapping
1. **Host, Client, and Server (`SRS Section 2.1`):** The MCP host (e.g., Claude Desktop/Code) runs the LLM and embeds the MCP client connected to `yt-intel-mcp`.
2. **Transports (`SRS Section 3.3`):**
   - `stdio` (primary): JSON-RPC 2.0 frames travel on `stdin`/`stdout`; all diagnostic logs MUST write exclusively to `stderr`.
   - `Streamable HTTP` (optional): Bound strictly to `localhost` only, validating `Origin` headers to defend against DNS rebinding.
3. **Primitives (`SRS Section 3.1`):**
   - **Tools:** Nine strictly typed tools (`get_video_details`, `get_similar_videos`, `get_similar_channels`, `get_recommendations`, `analyze_engagement`, `draft_curated_playlist`, `create_curated_playlist`, `get_quota_status`, `get_auth_status`). Descriptions state purpose, side effects, and typical quota cost (`NFR-9`).
   - **Resources:** URI-addressed read-only views for `youtube://metrics/quota` (both quota budgets and reset time) and `youtube://user/context` (aggregated user profile only, no raw personal lists).
   - **Elicitation (`2025-06-18`, `FR-5.4`):** When the MCP client declares the `elicitation` capability during `initialize`, `create_curated_playlist(draft_id)` prompts the user directly through the host via Form-mode elicitation (message + JSON Schema `requestedSchema`) and inspects explicit `accept` / `decline` / `cancel` outcomes. If the host does not support elicitation, the server falls back to its one-time confirmation page bound strictly to `127.0.0.1`, or rejects with `CONFIRMATION_UNAVAILABLE` if neither channel is available.

## Schema & Output Conventions (`NFR-5`, `NFR-9`)
- Strict JSON Schema inputs (`"additionalProperties": false`, validated ID formats, URL host allow-lists, and integer bounds before any API call).
- Structured JSON results returned alongside concise human-readable summaries, formatted durations, and exact `quota_used` (`units` and `search_calls`).

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]
- [[brain/inbox/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]
- [[brain/inbox/oauth-scopes-and-token-storage|OAuth Scopes, PKCE and Encrypted Token Storage]]
- [[brain/areas/second-brain|Second Brain Architecture]]
