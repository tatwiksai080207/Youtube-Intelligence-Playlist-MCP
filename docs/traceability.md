# Traceability Matrix (SE-5)

Chain: **Requirement -> GitHub Issue -> PR -> Test -> Skill -> Brain Note**  
Rule: Fill Issue and PR **only with real GitHub numbers** once created. Until then write `pending (<TASK-ID>)`. Use `n/a — <reason>` where a column genuinely does not apply.

## Functional Requirements
| Req | Owner | Task(s) | Issue | PR | Tests (SRS IDs) | Skill | Brain Note |
|---|---|---|---|---|---|---|---|
| FR-1.1 | Tatwik | TS-06, TS-10 | #48 (TS-06), #76 (TS-10) | #49 (TS-06), #77 (TS-10) | UT_ID, NT_VAL | video-to-playlist | brain/resources/tfidf-cosine-similarity.md |
| FR-1.2 | Tatwik | TS-08, TS-10 | #56 (TS-08), #76 (TS-10) | #57 (TS-08), #77 (TS-10) | UT_SIM, ST_FR1, X_PERF_SCORE | video-to-playlist | brain/resources/tfidf-cosine-similarity.md |
| FR-1.3 | Tatwik | TS-10 | #76 (TS-10) | #77 (TS-10) | UT_SIM | video-to-playlist | brain/resources/tfidf-cosine-similarity.md |
| FR-1.4 | Tatwik | TS-09, TS-10 | #64 (TS-09), #76 (TS-10) | #65 (TS-09), #77 (TS-10) | NT_VID | video-to-playlist | brain/resources/tfidf-cosine-similarity.md |
| FR-2.1 | Tatwik | TS-02, TS-04, TS-06, TS-11 | #6 (TS-02), #27 (TS-04), #28 (G-01 decision), #48 (TS-06) | #14 (TS-02), #29 (TS-04), #49 (TS-06), pending (TS-11) | UT_ID, NT_VAL, ST_FR2 | n/a — no skill uses FR-2 (SRS Section 6.2) | brain/resources/channel-similarity.md |
| FR-2.2 | Tatwik | TS-02, TS-08, TS-11 | #6 (TS-02), #56 (TS-08), pending (TS-11) | #14 (TS-02), #57 (TS-08), pending (TS-11) | UT_SIM | n/a — no skill uses FR-2 (SRS Section 6.2) | brain/resources/channel-similarity.md |
| FR-3.1 | Tatwik | TS-02, TS-12 | #6 (TS-02), pending (TS-12) | #14 (TS-02), pending | UT_PROF, UT_STAT_TS | n/a — no skill uses FR-3 (SRS Section 6.2) | brain/resources/youtube-event-timestamps.md |
| FR-3.2 | Tatwik | TS-02, TS-12 | #6 (TS-02), pending (TS-12) | #14 (TS-02), pending | UT_PROF, UT_STAT_TS | n/a — no skill uses FR-3 (SRS Section 6.2) | brain/resources/youtube-event-timestamps.md |
| FR-3.3 | Tatwik | TS-02, TS-13 | #6 (TS-02), pending (TS-13) | #14 (TS-02), pending | ST_FR3, NT_SIG | n/a — no skill uses FR-3 (SRS Section 6.2) | brain/resources/youtube-event-timestamps.md |
| FR-4.1 | Tatwik | TS-02, TS-07, TS-14 | #6 (TS-02), #52 (TS-07), pending (TS-14) | #14 (TS-02), #53 (TS-07), pending (TS-14) | ST_FR4, UT_STAT_BUCKET, UT_DUR | video-to-playlist (step 5) | brain/projects/engagement-analysis.md |
| FR-4.2 | Tatwik | TS-02, TS-14 | #6 (TS-02), pending (TS-14) | #14 (TS-02), pending | ST_FR4, UT_STAT_ZERO | n/a — playlist analysis has no period compare | brain/projects/engagement-analysis.md |
| FR-4.3 | Tatwik | TS-02, TS-14 | #6 (TS-02), pending (TS-14) | #14 (TS-02), pending | SEC_PII, UT_STAT_TS | n/a — playlist analysis has no raw user lists | brain/projects/engagement-analysis.md |
| FR-5.1 | Farhan | MF-03, MF-04, MF-08, MF-11 | #7 (MF-03), #34 (MF-04), #54 (MF-08), #62 (MF-11) | #17 (MF-03), #35 (MF-04), #55 (MF-08), #63 (MF-11) | ST_FR5, UT_SOLV_WINDOW | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.1a | Farhan | MF-03, MF-04, MF-09 | #7 (MF-03), #34 (MF-04), #58 (MF-09) | #17 (MF-03), #35 (MF-04), #59 (MF-09) | UT_LANG, NT_LANG | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.2 | Farhan | MF-03, MF-04, MF-10 | #7 (MF-03), #34 (MF-04), #60 (MF-10) | #17 (MF-03), #35 (MF-04), #61 (MF-10) | UT_SOLV, UT_DUR, X_PERF_SELECT | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.3 | Farhan | MF-04, MF-11 | #34 (MF-04), #62 (MF-11) | #35 (MF-04), #63 (MF-11) | ST_FR5 | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.4 | Farhan | MF-03, MF-04, MF-12, MF-13 | #7 (MF-03), #34 (MF-04), #70 (MF-12), #72 (MF-13) | #17 (MF-03), #35 (MF-04), #71 (MF-12), #73 (MF-13) | NT_HITL, NT_HITL_UNAVAIL, ST_FR5_CONFIRM | video-to-playlist | brain/resources/mcp-elicitation-confirmation.md |
| FR-5.5 | Farhan | MF-03, MF-04, MF-14 | #7 (MF-03), #34 (MF-04), pending (MF-14) | #17 (MF-03), #35 (MF-04), pending (MF-14) | IT_DRAFT, IT_DRAFT_PARTIAL, NT_DRAFT_STALE | video-to-playlist | brain/projects/partial-playlist-outcomes.md |
| FR-6.1 | Shiva | SR-02, SR-05, SR-10 | #5 (SR-02), #30 (SR-05), #44 (SR-10) | #15 (SR-02), #31 (SR-05), #45 (SR-10) | UT_QUOTA | video-to-playlist | brain/resources/youtube-quota-costs.md |
| FR-6.2 | Shiva | SR-02, SR-04, SR-05, MF-04, SR-10, MF-11, MF-14 | #5 (SR-02), #25 (SR-04), #30 (SR-05), #34 (MF-04), #44 (SR-10), #62 (MF-11) | #15 (SR-02), #26 (SR-04), #31 (SR-05), #35 (MF-04), #45 (SR-10), #63 (MF-11) | QT_1, QT_2, QT_3, CT_1 | video-to-playlist | brain/resources/youtube-quota-costs.md |
| FR-6.3 | Shiva | SR-02, SR-05, SR-11 | #5 (SR-02), #30 (SR-05), #46 (SR-11) | #15 (SR-02), #31 (SR-05), #47 (SR-11) | IT_CACHE, NT_QUOTA | video-to-playlist | brain/resources/youtube-quota-costs.md |
| FR-7.1 | Shiva | SR-02, SR-05, SR-13 | #5 (SR-02), #30 (SR-05), #68 (SR-13) | #15 (SR-02), #31 (SR-05), #69 (SR-13) | SEC_OAUTH | local-check | brain/resources/google-oauth-testing-mode.md |
| FR-7.2 | Shiva | SR-02, SR-05, SR-12, SR-13 | #5 (SR-02), #30 (SR-05), #66 (SR-12), #68 (SR-13) | #15 (SR-02), #31 (SR-05), #67 (SR-12), #69 (SR-13) | NT_AUTH, SEC_OAUTH | local-check | brain/resources/google-oauth-testing-mode.md |
| FR-7.3 | Shiva | SR-02, SR-05, SR-13, MF-14 | #5 (SR-02), #30 (SR-05), #68 (SR-13), pending (MF-14) | #15 (SR-02), #31 (SR-05), #69 (SR-13), pending (MF-14) | NT_ACC | local-check | brain/resources/google-oauth-testing-mode.md |
| FR-8.1 | Shiva | SR-02, SR-04, SR-08, SR-14, SR-15 | #5 (SR-02), #25 (SR-04), #40 (SR-08), #74 (SR-14) | #15 (SR-02), #26 (SR-04), #41 (SR-08), #75 (SR-14) | IT_PROV, CT_1 | local-check | brain/areas/engineering/provider-interface-pattern.md |
| FR-8.2 | Shiva | SR-02, SR-08 | #5 (SR-02), #40 (SR-08) | #15 (SR-02), #41 (SR-08) | SEC_PII | local-check | brain/areas/engineering/provider-interface-pattern.md |

## Agent Skills
| Req | Owner | Task(s) | Issue | PR | Tests | Skill | Brain Note |
|---|---|---|---|---|---|---|---|
| SK-1 | Farhan | TS-09, MF-15 | #64 (TS-09), pending (MF-15) | #65 (TS-09), pending (MF-15) | SE_EVAL_SUM, TQ-7, NFR-2 run | video-to-playlist | brain/areas/skill-video-to-playlist.md |
| SK-2 | Farhan | MF-05, MF-16 | #23 (MF-05), pending (MF-16) | #24 (MF-05), pending (MF-16) | TQ-7, SE-LOCAL-01..03 | local-check | brain/areas/skill-local-check.md |
| SK-3 | Tatwik | TS-01 | #3 | #13 | TQ-7, brain validation | brain-ingest | brain/areas/second-brain.md |
| SK-4 | Tatwik | TS-05 | #19 | #20 | TQ-7, brain validation | brain-refine | brain/areas/second-brain.md, brain/areas/skill-brain-refine.md |
| SK-5 | Shiva | SR-06 | #32 (SR-06) | #33 (SR-06) | TQ-7, SE-QRY-01..04 | brain-query | brain/areas/second-brain.md, brain/areas/skill-brain-query.md |

## Non-Functional Requirements
| Req | Owner | Task(s) | Issue | PR | Tests | Skill | Brain Note |
|---|---|---|---|---|---|---|---|
| NFR-1 | Tatwik / Farhan / Shiva | SR-02, TS-08, MF-04, MF-06, MF-10, SR-11 | #5 (SR-02), #34 (MF-04), #36 (MF-06), #46 (SR-11), #56 (TS-08), #60 (MF-10) | #15 (SR-02), #35 (MF-04), #37 (MF-06), #47 (SR-11), #57 (TS-08), #61 (MF-10) | X_PERF_SCORE, X_PERF_SELECT, IT_CACHE | n/a — performance target | brain/resources/nfr-targets.md |
| NFR-2 | Shiva / Farhan | SR-02, MF-04, MF-06, SR-10, SR-16, MF-15 | #5 (SR-02), #34 (MF-04), #36 (MF-06), #44 (SR-10) | #15 (SR-02), #35 (MF-04), #37 (MF-06), #45 (SR-10) | QT_1..3, SK-1 budget, live cap | video-to-playlist | brain/resources/nfr-targets.md |
| NFR-3 | Shiva | SR-02, SR-05, SR-12, SR-13 | #5 (SR-02), #30 (SR-05), #66 (SR-12), #68 (SR-13) | #15 (SR-02), #31 (SR-05), #67 (SR-12), #69 (SR-13) | SEC_OAUTH | n/a — auth storage | brain/resources/nfr-targets.md |
| NFR-4 | Farhan | MF-02, TS-00 | #1, #8 | #10 (TS-00), #16 (MF-02) | Gitleaks CI | n/a — repo hygiene | brain/resources/nfr-targets.md |
| NFR-5 | Tatwik | TS-06, TS-04, MF-04 | #27 (TS-04), #34 (MF-04), #48 (TS-06) | #29 (TS-04), #35 (MF-04), #49 (TS-06) | NT_VAL, UT_ID | n/a — input validation | brain/resources/nfr-targets.md |
| NFR-6 | Farhan | MF-03, MF-04, MF-07, MF-13 | #7 (MF-03), #34 (MF-04), #50 (MF-07), #72 (MF-13) | #17 (MF-03), #35 (MF-04), #51 (MF-07), #73 (MF-13) | NFR_6 (test_sanitize), NT_HITL injection | video-to-playlist | brain/areas/security/prompt-injection-defence.md |
| NFR-7 | Shiva / Tatwik | SR-02, SR-05, SR-08, SR-12, TS-14 | #5 (SR-02), #30 (SR-05), #40 (SR-08), #66 (SR-12) | #15 (SR-02), #31 (SR-05), #41 (SR-08), #67 (SR-12) | SEC_PII | n/a — privacy | brain/resources/nfr-targets.md |
| NFR-8 | Shiva / Farhan | SR-02, SR-04, MF-04, SR-14, MF-14 | #5 (SR-02), #25 (SR-04), #34 (MF-04), #74 (SR-14) | #15 (SR-02), #26 (SR-04), #35 (MF-04), #75 (SR-14) | IT_PROV retry, IT_DRAFT_PARTIAL, CT_1 | n/a — reliability | brain/resources/nfr-targets.md |
| NFR-9 | Farhan / all | TS-04, TS-07, MF-04, SR-17, TS-16 | #27 (TS-04), #34 (MF-04), #52 (TS-07) | #29 (TS-04), #35 (MF-04), #53 (TS-07) | Tool reference CI check, UT_DUR | n/a — usability | brain/resources/nfr-targets.md |
| NFR-10 | Farhan / Shiva | SR-01, SR-02, SR-03, SR-04, MF-02, MF-06, SR-15, MF-18 | #2 (SR-01), #5 (SR-02), #21 (SR-03), #25 (SR-04), #8 (MF-02), #36 (MF-06) | #11 (SR-01), #15 (SR-02), #22 (SR-03), #26 (SR-04), #16 (MF-02), #37 (MF-06), pending (SR-15, MF-18) | CI coverage >=85%, lint, mypy, import-lint | n/a — maintainability | brain/resources/nfr-targets.md |

## SDLC Process Requirements (R-2)
| Req | Owner | Task(s) | Evidence Location |
|---|---|---|---|
| SE-1 SRS | Shiva (maintainer) | done | `Final_SRS_Submission.pdf` (commit `a51c14e`) |
| SE-2 Architecture & UML/ER | Shiva, Tatwik, Farhan | SR-05 (#30, PR #31), TS-04 (#27, PR #29), MF-04 (#34, PR #35) | `docs/architecture/` (`overview.md`, `analysis.md`, `playlist.md`) |
| SE-3 ADRs | All | SR-03 (#21, PR #22), SR-04 (#25, PR #26), SR-05 (#30, PR #31), TS-04 (#27, PR #29), MF-04 (#34, PR #35) | `docs/adr/` (`0001-runtime-and-toolchain.md`, `0002-provider-and-errors.md`, `0003-similarity-scoring.md`, `0004-trusted-confirmation.md`, `0005-playlist-selection.md`, `0006-token-storage-and-persistence.md`, `0007-interest-profile.md`) |
| SE-4 Dev plan & breakdown | Tatwik | TS-00 (#1, PR #10) | `docs/plan/development-plan.md` |
| SE-5 Traceability | All | TS-00..SR-18 (#1, PR #10) | `docs/traceability.md` |
| SE-6 Provider interface | Shiva | SR-04 (#25, PR #26), SR-15 | `src/yt_intel_mcp/provider/base.py` |
| SE-7 User & Developer docs | Tatwik, Shiva | SR-04 (#25, PR #26), SR-09 (#42, PR #43), TS-16, SR-17 | `docs/user/`, `docs/developer/` (`docs/developer/fixtures.md`, `docs/developer/testing.md`) |
| SB-1..SB-6 Second Brain | All | TS-01 (#3, PR #13), TS-02 (#6, PR #14), SR-02 (#5, PR #15), MF-03 (#7, PR #17), TS-03 (#9, PR #18), TS-04 (#27, PR #29), TS-05 (#19, PR #20), SR-05 (#30, PR #31), SR-06 (#32, PR #33), MF-04 (#34, PR #35), MF-06 (#36, PR #37), SR-07 (#38, PR #39), SR-08 (#40, PR #41), SR-09 (#42, PR #43), SR-10 (#44, PR #45), SR-11 (#46, PR #47), TS-06 (#48, PR #49), MF-07 (#50, PR #51), TS-07 (#52, PR #53), MF-08 (#54, PR #55), TS-08 (#56, PR #57), MF-09 (#58, PR #59), MF-10 (#60, PR #61), MF-11 (#62, PR #63), TS-09 (#64, PR #65), SR-12 (#66, PR #67), SR-13 (#68, PR #69), MF-12 (#70, PR #71), MF-13 (#72, PR #73) | `brain/` & git history (`brain/projects/stage-1-review.md`, `brain/projects/stage-2-review.md`, `[[brain/inbox/ai-session-2026-11-25-tatwik-TS-03]]`, `[[brain/inbox/ai-session-2026-11-25-tatwik-TS-05]]`, `[[brain/inbox/ai-session-2026-11-26-tatwik-TS-04]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-05]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-06]]`, `[[brain/inbox/ai-session-2026-11-26-farhan-MF-04]]`, `[[brain/inbox/ai-session-2026-11-26-farhan-MF-06]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-07]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-08]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-09]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-10]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-11]]`, `[[brain/inbox/ai-session-2026-11-26-tatwik-TS-06]]`, `[[brain/inbox/ai-session-2026-11-26-farhan-MF-07]]`, `[[brain/inbox/ai-session-2026-11-26-tatwik-TS-07]]`, `[[brain/inbox/ai-session-2026-11-26-farhan-MF-08]]`, `[[brain/inbox/ai-session-2026-11-26-tatwik-TS-08]]`, `[[brain/inbox/ai-session-2026-11-26-farhan-MF-09]]`, `[[brain/inbox/ai-session-2026-11-26-farhan-MF-10]]`, `[[brain/inbox/ai-session-2026-11-26-farhan-MF-11]]`, `[[brain/inbox/ai-session-2026-11-26-tatwik-TS-09]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-12]]`, `[[brain/inbox/ai-session-2026-11-27-shiva-SR-13]]`, `[[brain/inbox/ai-session-2026-11-27-farhan-MF-12]]`, `[[brain/inbox/ai-session-2026-11-27-farhan-MF-13]]`) |
| SB-1, SB-3 Validator checks | Farhan | MF-01 (#4, PR #12) | `scripts/validate_brain.py`, `scripts/validate_skills.py`, `tests/unit/test_validators.py` (TQ-1, TQ-4), [[brain/inbox/ai-session-2026-11-23-farhan-MF-01]] |
| SB-6 Farhan's Stage 1 research notes | Farhan | MF-03 (#7, PR #17) | [[brain/inbox/ai-session-2026-11-25-farhan-MF-03]] |
| TQ-5 Fixture CI | Farhan | MF-02 (#8, PR #16), SR-08 (#40, PR #41) | `.github/workflows/ci.yml`, `src/yt_intel_mcp/provider/fixture.py`, [[brain/inbox/ai-session-2026-11-25-farhan-MF-02]], [[brain/inbox/ai-session-2026-11-26-shiva-SR-08]] |
| TQ-7 Skill evaluations | All | TS-03 (#9, PR #18), TS-05 (#19, PR #20), MF-05 (#23, PR #24), SR-06 (#32, PR #33), SR-07 (#38, PR #39), MF-17 | `docs/testing/skill-evals.md` |
| TQ-1..TQ-8 Test plan & defect log | Farhan / Fixer | MF-06 (#36, PR #37), ongoing | `docs/testing/test-plan.md`, `docs/testing/defect-log.md`, [[brain/inbox/ai-session-2026-11-26-farhan-MF-06]] |
| TQ-3 System Test Harness | Shiva | SR-09 (#42, PR #43) | `tests/system/conftest.py`, `tests/system/test_harness.py`, `docs/developer/testing.md`, [[brain/inbox/ai-session-2026-11-26-shiva-SR-09]] |
