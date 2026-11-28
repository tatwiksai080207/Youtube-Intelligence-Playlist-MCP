---
title: "AI Session TS-16 User Guide"
type: ai-session
status: inbox
authors:
  - Molleti Tatwik Sai
created: 2026-11-28
updated: 2026-11-28
tags:
  - ai-session
  - documentation
  - user-guide
  - se-7
requirements:
  - SE-7
  - NFR-9
  - SB-1
issues:
  - "#90"
prs:
  - "#91"
sources:
  - "Final_SRS_Submission.pdf (v1.0, Section 1.2)"
  - "src/yt_intel_mcp/server.py"
---

# AI Session TS-16 User Guide

## Summary
Authored `docs/user/guide.md` for `TS-16` (`SE-7`, `NFR-9`) on branch `tatwik/TS-16-user-guide` (Issue `#90`).

- Documented local installation, fixture vs live mode, single project Google Cloud OAuth Desktop client and Testing mode test user setup, and 7 day refresh token reauthorization with encrypted local storage.
- Documented MCP host stdio configuration, all 8 MCP tools (`get_video_details`, `get_similar_videos`, `get_recommendations`, `analyze_engagement`, `draft_curated_playlist`, `create_curated_playlist`, `get_quota_status`, `get_auth_status`) and both MCP resources (`youtube://metrics/quota`, `youtube://user/context`) with examples and quota costs.
- Documented the out of band trusted confirmation flow (MCP elicitation and `127.0.0.1` loopback page), privacy guarantees, and SRS Section 1.2 out of scope exclusions.

## Related Notes
- [[brain/resources/google-oauth-testing-mode]]
- [[brain/resources/mcp-elicitation-confirmation]]
- [[brain/resources/youtube-quota-costs]]
