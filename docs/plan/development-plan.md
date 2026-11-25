# Development Plan, Task Breakdown and Decision Register (SE-4)

**Product:** YouTube Video Intelligence MCP Server (`yt-intel-mcp`)  
**Team Whatsup:** Molleti Tatwik Sai (`BT2024200`), Madire Shiva Reddy (`BT2024218`), Mohammed Farhan (`BT2024140`)  
**Product Baseline:** `Final_SRS_Submission.pdf` (version 1.0)

## 1. Team Ownership Allocation (54 Incremental Tasks)
| Member | Primary Areas | Task IDs |
|---|---|---|
| **Molleti Tatwik Sai** (`tatwiksai080207`) | Repo workflow, FR-1 to FR-4, `get_video_details`, ID/duration/TF-IDF modules, `brain-ingest`/`brain-refine`, host compatibility, user guide, Stage 1 and Stage 4 reviews | `TS-00` to `TS-17` (18 tasks) |
| **Madire Shiva Reddy** (`Shiva0025`) | Package skeleton, shared contracts, FR-6 quota/cache, FR-7 OAuth/token store, FR-8 fixture and live providers, `brain-query`, scheduled live CI, developer docs, Stage 2 review and `v1.0.0` release | `SR-01` to `SR-18` (18 tasks) |
| **Mohammed Farhan** (`farhan4599`) | CI hardening, skill/brain validators, NFR-6 sanitisation, FR-5 constraints/language/solver/drafts/trusted confirmation/writer, `video-to-playlist`, `local-check`, test plan and defect log, Stage 3 review and final audit | `MF-01` to `MF-18` (18 tasks) |

## 2. Stage Milestones and Release Tags
| Stage | Deliverable Focus | Tasks | Tag |
|---|---|---|---|
| **Stage 1 — Requirements** | SRS baseline, PARA vault aligned to SRS v1.0, notes from all 3 members, `brain-ingest`, package skeleton, gating CI, Stage 1 review | `TS-00..03`, `SR-01..02`, `MF-01..03` | `stage-1` / `v0.1.0` |
| **Stage 2 — Design** | ADRs 0001–0007, UML/ER diagrams, frozen contracts and JSON Schemas, `brain-refine`, `brain-query`, `local-check` v1, test plan, Stage 2 review | `SR-03..07`, `TS-04..05`, `MF-04..06` | `stage-2` / `v0.2.0` |
| **Stage 3 — Testing and CI** | Incremental FR-1 to FR-8 implementation, full unit/integration/system/negative/security/quota/perf tests, `video-to-playlist`, `local-check` v2, live CI, docs, defect log, Stage 3 review | `SR-08..17`, `TS-06..16`, `MF-07..17` | `stage-3` / `v0.3.0` |
| **Stage 4 — Review and Demo** | Final quality audit, live MCP client demo, end to end traceability walkthrough, Stage 4 review, final release | `MF-18`, `TS-17`, `SR-18` | `v1.0.0` |

## 3. Architectural Decision and Conflict Register
| ID | Type | Summary | Resolution / Target | Owner | Status |
|---|---|---|---|---|---|
| `D-01` | Decision | Repository location | `tatwiksai080207/Youtube-Intelligence-Playlist-MCP` | Tatwik | RESOLVED |
| `D-02` | Decision | Runtime stack (SRS Section 2.3) | Python 3.11+ and official `mcp` SDK (`ADR-0001`, `#21`) | Shiva | RESOLVED |
| `C-01` | Conflict | R-1 single 10k quota vs. SRS C-2 dual budget | Follow SRS C-2 (both budgets configurable); re-check R-5 in `SR-10` | Shiva | RESOLVED (SRS) |
| `C-02` | Conflict | `src/mcp/schemas/` vs. Python `mcp` SDK package name | Use `src/yt_intel_mcp/schemas/` (`ADR-0001`, `#21`) | Shiva | RESOLVED |
| `C-03` | Conflict | R-2 SE-7 "e.g., OpenAPI" vs. stdio MCP server | Generate `docs/developer/tool-reference.md` from JSON Schemas (`SR-17`) | Shiva | PROPOSED |
| `G-01` | Gap | Error code for nonexistent channel in FR-2 | Team vote open in Issue `#28` (`INVALID_ARGUMENT` vs `CHANNEL_UNAVAILABLE`) before `TS-11` negative test | Tatwik | OPEN |
| `G-02` | Gap | Step order inside `create_curated_playlist` | Freeze in ADR-0004 (`MF-04`) | Farhan | OPEN |
| `G-03` | Gap | Draft-time write-cost preflight before count is known | Freeze in ADR-0005 (`MF-04`) | Farhan | OPEN |
| `G-04` | Gap | Scheduled live CI (`TQ-5`) vs. 7-day Testing token and no delete | Read only live workflow; decide via `type:decision` issue before `SR-16` | Shiva | OPEN |
| `G-05` | Gap | Optional `first_observed` store (FR-3.2 vs FR-4.3) | Frozen in `docs/adr/0007-interest-profile.md` (`TS-04`, `#27`): neutral `0.5` weight in `FR-3.2`, tracked separately in `FR-4.3` | Tatwik | RESOLVED |
| `G-06` | Gap | Fixed neutral weight value for undated items (FR-3.2) | Frozen in `docs/adr/0007-interest-profile.md` (`TS-04`, `#27`): `ProfileConfig.undated_weight = 0.5` | Tatwik | RESOLVED |
| `G-07` | Conflict | Existing note proposes "clickbait penalty" absent from SRS FR-1.2 | Mark "not adopted — not in SRS FR-1.2" in `TS-01` | Tatwik | RESOLVED |
| `G-08` | Conflict | Existing notes cite draft IDs (`NFR-SEC-1`, `C-11`, etc.) | Map to SRS v1.0 IDs in `TS-01` | Tatwik | RESOLVED |
| `G-09` | Gap | Existing 10 notes lack `status`/`authors`/`sources`; 1 author | Fix schema in `TS-01`; add notes from all 3 members (`SR-02`, `TS-02`, `MF-03`) | Tatwik | RESOLVED |
