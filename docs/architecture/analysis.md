# Analysis Subsystem Architecture and Data Flows (`FR-1`..`FR-4`)

- **Task:** `TS-04` (`SE-2`)
- **Owner:** Molleti Tatwik Sai
- **Requirements:** `FR-1.1`..`FR-1.4`, `FR-2.1`..`FR-2.2`, `FR-3.1`..`FR-3.3`, `FR-4.1`..`FR-4.3`, `NFR-1`, `NFR-5`, `NFR-7`, `NFR-9`, `SE-2`, `SE-6`
- **Related ADRs:**
  - `docs/adr/0002-provider-and-errors.md` (`YouTubeProvider` and `QuotaGuard` boundary)
  - `docs/adr/0003-similarity-scoring.md` (objective TF IDF scoring, redistribution, diversity)
  - `docs/adr/0007-interest-profile.md` (half life decay, `G-05`/`G-06`, cadence and privacy guards)

## Architectural Boundaries

All four analysis tools (`get_video_details`, `get_similar_videos`, `get_similar_channels`, `get_recommendations`, `analyze_engagement`) share strict boundary invariants:

1. **Strict Input Validation Before Quota (`INV-02`, `NFR-5`):** Every MCP call validates JSON arguments against strict `additionalProperties: false` schemas in `src/yt_intel_mcp/schemas/` and parses video/channel IDs locally via `yt_intel_mcp.validation` before calling `QuotaGuard.preflight` or dispatching any provider call.
2. **Provider Isolation (`SE-6`, `INV-19`):** Domain modules (`validation`, `analysis`, `sanitize`) accept and return frozen dataclasses (`VideoMeta`, `ChannelMeta`, `UserEvent`) and invoke only async methods on `YouTubeProvider`. HTTP clients never enter analysis modules.
3. **Objective Metadata Only (`INV-01`):** `VideoMeta`, `ChannelMeta`, JSON Schemas, similarity scorers, and MCP response envelopes exclude `viewCount`, `likeCount`, `subscriberCount`, and `statistics`.
4. **Metadata Sanitization (`INV-22`, `NFR-6`):** Untrusted video titles, tags, and descriptions pass through `yt_intel_mcp.sanitize` before exposure or prompt formatting.

## Component Structure (`SE-2`)

```mermaid
flowchart LR
    Client["MCP Client Host"] -->|JSON args| Server["MCPServer Tool Handlers"]
    Server -->|Schema check NFR-5| Schemas["yt_intel_mcp.schemas JSON Schemas"]
    Server -->|Pre-quota parse| Valid["yt_intel_mcp.validation.ids"]
    Server -->|Preflight and charge| Quota["QuotaGuard SQLite Ledger"]
    Server -->|Orchestrate FR-1..FR-4| Analysis["yt_intel_mcp.analysis"]

    subgraph Domain["Pure Objective Domain Modules"]
        Valid
        Analysis --> Sim["similarity.py FR-1 / FR-2"]
        Analysis --> Stats["engagement.py FR-4"]
        Analysis --> Prof["profile.py FR-3"]
        Analysis --> Recs["recommendations.py FR-3"]
        Analysis --> Agg["privacy_aggregate.py INV-09"]
        San["sanitize.py INV-22"]
        Analysis --> San
    end

    Analysis -->|Async protocol SE-6| Prov["YouTubeProvider Protocol"]
    Prov -->|YT_INTEL_PROVIDER=fixture| Fix["FixtureProvider"]
    Prov -->|YT_INTEL_PROVIDER=live| Live["LiveYouTubeProvider"]
```

## Video, Channel, and Interest Flow (`FR-1`..`FR-4`)

### 1. Video Details and Similarity Flow (`FR-1`, `FR-2`)

```mermaid
sequenceDiagram
    autonumber
    participant Client as MCP Client
    participant Tool as Analysis Tool Handler
    participant Val as Validation and Schema
    participant Guard as QuotaGuard
    participant Prov as YouTubeProvider
    participant Score as Similarity Scorer
    participant San as Sanitizer

    Client->>Tool: call get_similar_videos or get_similar_channels
    Tool->>Val: validate schema NFR-5, extract ID/handle, check weights sum > 0
    alt Invalid input or empty/zero scoring_weights
        Val-->>Tool: ToolError INVALID_ARGUMENT
        Tool-->>Client: error_response zero quota consumed
    else Valid input
        Tool->>Guard: preflight estimated units and search_calls
        alt Daily cap exceeded
            Guard-->>Tool: ToolError QUOTA_BUDGET_INSUFFICIENT
            Tool-->>Client: error_response zero upstream dispatch
        else Budget sufficient
            Tool->>Prov: fetch seed video/channel and candidate metadata
            Tool->>Guard: charge actual units and search_calls consumed
            Tool->>Score: normalize active objective weights + TF IDF cosine + MMR
            Tool->>San: sanitize returned titles, descriptions, and tags
            Tool-->>Client: success_response summary, ranked items, quota_used
        end
    end
```

### 2. Personalized Recommendations and Engagement Analytics Flow (`FR-3`, `FR-4`)

```mermaid
sequenceDiagram
    autonumber
    participant Client as MCP Client
    participant Tool as FR-3 / FR-4 Tool Handler
    participant Guard as QuotaGuard
    participant Prov as YouTubeProvider
    participant Prof as Interest Profile Builder
    participant Agg as Recommendations / Engagement Engine

    Client->>Tool: call get_recommendations or analyze_engagement
    Tool->>Guard: preflight read budget for selected explicit sources
    Tool->>Prov: fetch liked_video, subscription, and playlist_item signals
    Tool->>Guard: charge read units
    Tool->>Prof: tag EventTimeKind DATED, UNDATED, FIRST_OBSERVED
    alt Total deduplicated events == 0
        Prof-->>Tool: ToolError INSUFFICIENT_USER_SIGNAL
        Tool-->>Client: error_response zero search dispatch
    else Signals present
        alt get_recommendations FR-3
            Tool->>Guard: preflight <= 3 search.list + <= 25 metadata units
            Tool->>Prov: search_videos with synthesized queries + get_videos enrich
            Tool->>Guard: charge search and video units
            Tool->>Agg: exclude library items, score objectively, attach reasons
            Tool-->>Client: success_response sanitized recommendations
        else analyze_engagement FR-4
            Tool->>Agg: apply timeframe window and previous window comparison INV-07
            Tool->>Agg: classify short/medium/long buckets and cadence guard INV-08
            Tool->>Agg: strip raw video_id and channel_id lists INV-09
            Tool-->>Client: success_response aggregate analytics and coverage counts
        end
    end
```

## Module Responsibilities Summary

| Module | Owner Task | Primary Responsibility | Strict Boundary Invariants |
|---|---|---|---|
| `src/yt_intel_mcp/schemas/` | `TS-04` | Strict draft 2020-12 JSON Schemas with `additionalProperties: false` | `NFR-5`, `INV-01` |
| `src/yt_intel_mcp/validation/ids.py` | `TS-06` | Extract video IDs, channel IDs/handles, and playlist IDs locally | `INV-02`, zero provider calls |
| `src/yt_intel_mcp/analysis/similarity.py` | `TS-08` | Sublinear TF IDF, duration closeness, redistribution, MMR diversity | `INV-01`, `NFR-1` (`<= 150 ms`) |
| `src/yt_intel_mcp/analysis/engagement.py` | `TS-07`, `TS-14` | Duration buckets, zero division comparison guard, cadence guard, aggregates | `INV-07`, `INV-08`, `INV-09` |
| `src/yt_intel_mcp/analysis/profile.py` | `TS-12` | Deduplicate explicit signals, decay dated events, `0.5` undated weight | `INV-04`, `INV-05`, `INV-06` |
| `src/yt_intel_mcp/analysis/tools.py` | `TS-10`..`TS-14` | Orchestrate preflight, provider reads, scoring, sanitization, envelopes | `INV-02`, `INV-19`, `INV-22` |
