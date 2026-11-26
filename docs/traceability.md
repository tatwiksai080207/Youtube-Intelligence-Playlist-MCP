# Traceability Matrix (SE-5)

Chain: **Requirement -> GitHub Issue -> PR -> Test -> Skill -> Brain Note**  
Rule: Fill Issue and PR **only with real GitHub numbers** once created. Until then write `pending (<TASK-ID>)`. Use `n/a — <reason>` where a column genuinely does not apply.

## Functional Requirements
| Req | Owner | Task(s) | Issue | PR | Tests (SRS IDs) | Skill | Brain Note |
|---|---|---|---|---|---|---|---|
| FR-1.1 | Tatwik | TS-06, TS-10 | pending (TS-06) | pending | UT_ID, NT_VAL | video-to-playlist | brain/resources/tfidf-cosine-similarity.md |
| FR-1.2 | Tatwik | TS-08, TS-10 | pending (TS-08) | pending | UT_SIM, ST_FR1, X_PERF_SCORE | video-to-playlist | brain/resources/tfidf-cosine-similarity.md |
| FR-1.3 | Tatwik | TS-10 | pending (TS-10) | pending | UT_SIM | video-to-playlist | brain/resources/tfidf-cosine-similarity.md |
| FR-1.4 | Tatwik | TS-09, TS-10 | pending (TS-09) | pending | NT_VID | video-to-playlist | brain/resources/tfidf-cosine-similarity.md |
| FR-2.1 | Tatwik | TS-02, TS-04, TS-06, TS-11 | #6 (TS-02), #27 (TS-04), #28 (G-01 decision), pending (TS-06) | #14 (TS-02), #29 (TS-04), pending | ST_FR2 | n/a — no skill uses FR-2 (SRS Section 6.2) | brain/resources/channel-similarity.md |
| FR-2.2 | Tatwik | TS-02, TS-08, TS-11 | #6 (TS-02), pending (TS-08) | #14 (TS-02), pending | UT_SIM | n/a — no skill uses FR-2 (SRS Section 6.2) | brain/resources/channel-similarity.md |
| FR-3.1 | Tatwik | TS-02, TS-12 | #6 (TS-02), pending (TS-12) | #14 (TS-02), pending | UT_PROF, UT_STAT_TS | n/a — no skill uses FR-3 (SRS Section 6.2) | brain/resources/youtube-event-timestamps.md |
| FR-3.2 | Tatwik | TS-02, TS-12 | #6 (TS-02), pending (TS-12) | #14 (TS-02), pending | UT_PROF, UT_STAT_TS | n/a — no skill uses FR-3 (SRS Section 6.2) | brain/resources/youtube-event-timestamps.md |
| FR-3.3 | Tatwik | TS-02, TS-13 | #6 (TS-02), pending (TS-13) | #14 (TS-02), pending | ST_FR3, NT_SIG | n/a — no skill uses FR-3 (SRS Section 6.2) | brain/resources/youtube-event-timestamps.md |
| FR-4.1 | Tatwik | TS-02, TS-07, TS-14 | #6 (TS-02), pending (TS-07) | #14 (TS-02), pending | ST_FR4, UT_STAT_BUCKET | video-to-playlist (step 5) | brain/projects/engagement-analysis.md |
| FR-4.2 | Tatwik | TS-02, TS-14 | #6 (TS-02), pending (TS-14) | #14 (TS-02), pending | ST_FR4, UT_STAT_ZERO | n/a — playlist analysis has no period compare | brain/projects/engagement-analysis.md |
| FR-4.3 | Tatwik | TS-02, TS-14 | #6 (TS-02), pending (TS-14) | #14 (TS-02), pending | SEC_PII, UT_STAT_TS | n/a — playlist analysis has no raw user lists | brain/projects/engagement-analysis.md |
| FR-5.1 | Farhan | MF-03, MF-04, MF-08, MF-11 | #7 (MF-03), #34 (MF-04), pending (MF-08) | #17 (MF-03), #35 (MF-04), pending (MF-08) | ST_FR5, UT_SOLV_WINDOW | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.1a | Farhan | MF-03, MF-04, MF-09 | #7 (MF-03), #34 (MF-04), pending (MF-09) | #17 (MF-03), #35 (MF-04), pending (MF-09) | UT_LANG, NT_LANG | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.2 | Farhan | MF-03, MF-04, MF-10 | #7 (MF-03), #34 (MF-04), pending (MF-10) | #17 (MF-03), #35 (MF-04), pending (MF-10) | UT_SOLV, UT_DUR, X_PERF_SELECT | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.3 | Farhan | MF-04, MF-11 | #34 (MF-04), pending (MF-11) | #35 (MF-04), pending (MF-11) | ST_FR5 | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.4 | Farhan | MF-03, MF-04, MF-12, MF-13 | #7 (MF-03), #34 (MF-04), pending (MF-12) | #17 (MF-03), #35 (MF-04), pending (MF-12) | NT_HITL, NT_HITL_UNAVAIL, ST_FR5_CONFIRM | video-to-playlist | brain/resources/mcp-elicitation-confirmation.md |
| FR-5.5 | Farhan | MF-03, MF-04, MF-14 | #7 (MF-03), #34 (MF-04), pending (MF-14) | #17 (MF-03), #35 (MF-04), pending (MF-14) | IT_DRAFT, IT_DRAFT_PARTIAL, NT_DRAFT_STALE | video-to-playlist | brain/projects/partial-playlist-outcomes.md |
| FR-6.1 | Shiva | SR-02, SR-05, SR-10 | #5 (SR-02), #30 (SR-05), pending (SR-10) | #15 (SR-02), #31 (SR-05), pending (SR-10) | UT_QUOTA | video-to-playlist | brain/resources/youtube-quota-costs.md |
| FR-6.2 | Shiva | SR-02, SR-04, SR-05, MF-04, SR-10, MF-11, MF-14 | #5 (SR-02), #25 (SR-04), #30 (SR-05), #34 (MF-04), pending (SR-10) | #15 (SR-02), #26 (SR-04), #31 (SR-05), #35 (MF-04), pending (SR-10) | QT_1, QT_2, QT_3, CT_1 | video-to-playlist | brain/resources/youtube-quota-costs.md |
| FR-6.3 | Shiva | SR-02, SR-05, SR-11 | #5 (SR-02), #30 (SR-05), pending (SR-11) | #15 (SR-02), #31 (SR-05), pending (SR-11) | IT_CACHE, NT_QUOTA | video-to-playlist | brain/resources/youtube-quota-costs.md |
| FR-7.1 | Shiva | SR-02, SR-05, SR-13 | #5 (SR-02), #30 (SR-05), pending (SR-13) | #15 (SR-02), #31 (SR-05), pending (SR-13) | SEC_OAUTH | local-check | brain/resources/google-oauth-testing-mode.md |
| FR-7.2 | Shiva | SR-02, SR-05, SR-12, SR-13 | #5 (SR-02), #30 (SR-05), pending (SR-12) | #15 (SR-02), #31 (SR-05), pending (SR-12) | NT_AUTH, SEC_OAUTH | local-check | brain/resources/google-oauth-testing-mode.md |
| FR-7.3 | Shiva | SR-02, SR-05, SR-13, MF-14 | #5 (SR-02), #30 (SR-05), pending (SR-13) | #15 (SR-02), #31 (SR-05), pending (SR-13) | NT_ACC | local-check | brain/resources/google-oauth-testing-mode.md |
| FR-8.1 | Shiva | SR-02, SR-04, SR-08, SR-14, SR-15 | #5 (SR-02), #25 (SR-04) | #15 (SR-02), #26 (SR-04) | IT_PROV, CT_1 | local-check | brain/areas/engineering/provider-interface-pattern.md |
| FR-8.2 | Shiva | SR-02, SR-08 | #5 (SR-02), pending (SR-08) | #15 (SR-02), pending | SEC_PII | local-check | brain/areas/engineering/provider-interface-pattern.md |

## Agent Skills
| Req | Owner | Task(s) | Issue | PR | Tests | Skill | Brain Note |
|---|---|---|---|---|---|---|---|
| SK-1 | Farhan | TS-09, MF-15 | pending (TS-09) | pending | SE_EVAL_SUM, TQ-7, NFR-2 run | video-to-playlist | brain/areas/skill-video-to-playlist.md |
| SK-2 | Farhan | MF-05, MF-16 | #23 (MF-05), pending (MF-16) | #24 (MF-05), pending (MF-16) | TQ-7, SE-LOCAL-01..03 | local-check | brain/areas/skill-local-check.md |
| SK-3 | Tatwik | TS-01 | #3 | #13 | TQ-7, brain validation | brain-ingest | brain/areas/second-brain.md |
| SK-4 | Tatwik | TS-05 | #19 | #20 | TQ-7, brain validation | brain-refine | brain/areas/second-brain.md, brain/areas/skill-brain-refine.md |
| SK-5 | Shiva | SR-06 | #32 (SR-06) | #33 (SR-06) | TQ-7, SE-QRY-01..04 | brain-query | brain/areas/second-brain.md, brain/areas/skill-brain-query.md |

## Non-Functional Requirements
| Req | Owner | Task(s) | Issue | PR | Tests | Skill | Brain Note |
|---|---|---|---|---|---|---|---|
| NFR-1 | Tatwik / Farhan / Shiva | SR-02, TS-08, MF-04, MF-10, SR-11 | #5 (SR-02), #34 (MF-04), pending (TS-08) | #15 (SR-02), #35 (MF-04), pending (TS-08) | X_PERF_SCORE, X_PERF_SELECT, IT_CACHE | n/a — performance target | brain/resources/nfr-targets.md |
| NFR-2 | Shiva / Farhan | SR-02, MF-04, SR-10, SR-16, MF-15 | #5 (SR-02), #34 (MF-04), pending (SR-10) | #15 (SR-02), #35 (MF-04), pending (SR-10) | QT_1..3, SK-1 budget, live cap | video-to-playlist | brain/resources/nfr-targets.md |
| NFR-3 | Shiva | SR-02, SR-05, SR-12, SR-13 | #5 (SR-02), #30 (SR-05), pending (SR-12) | #15 (SR-02), #31 (SR-05), pending (SR-12) | SEC_OAUTH | n/a — auth storage | brain/resources/nfr-targets.md |
| NFR-4 | Farhan | MF-02, TS-00 | #1, #8 | #10 (TS-00), #16 (MF-02) | Gitleaks CI | n/a — repo hygiene | brain/resources/nfr-targets.md |
| NFR-5 | Tatwik | TS-06, TS-04, MF-04 | #27 (TS-04), #34 (MF-04), pending (TS-06) | #29 (TS-04), #35 (MF-04), pending (TS-06) | NT_VAL | n/a — input validation | brain/resources/nfr-targets.md |
| NFR-6 | Farhan | MF-03, MF-04, MF-07, MF-13 | #7 (MF-03), #34 (MF-04), pending (MF-07) | #17 (MF-03), #35 (MF-04), pending (MF-07) | NT_HITL injection | video-to-playlist | brain/areas/security/prompt-injection-defence.md |
| NFR-7 | Shiva / Tatwik | SR-02, SR-05, SR-08, SR-12, TS-14 | #5 (SR-02), #30 (SR-05), pending (SR-08) | #15 (SR-02), #31 (SR-05), pending (SR-08) | SEC_PII | n/a — privacy | brain/resources/nfr-targets.md |
| NFR-8 | Shiva / Farhan | SR-02, SR-04, MF-04, SR-14, MF-14 | #5 (SR-02), #25 (SR-04), #34 (MF-04), pending (SR-14) | #15 (SR-02), #26 (SR-04), #35 (MF-04), pending (SR-14) | IT_PROV retry, IT_DRAFT_PARTIAL, CT_1 | n/a — reliability | brain/resources/nfr-targets.md |
| NFR-9 | Farhan / all | TS-04, MF-04, SR-17, TS-16 | #27 (TS-04), #34 (MF-04) | #29 (TS-04), #35 (MF-04) | Tool reference CI check | n/a — usability | brain/resources/nfr-targets.md |
| NFR-10 | Farhan / Shiva | SR-01, SR-02, SR-03, SR-04, MF-02, SR-15, MF-18 | #2 (SR-01), #5 (SR-02), #21 (SR-03), #25 (SR-04), #8 (MF-02) | #11 (SR-01), #15 (SR-02), #22 (SR-03), #26 (SR-04), #16 (MF-02), pending (SR-15, MF-18) | CI coverage >=85%, lint, mypy, import-lint | n/a — maintainability | brain/resources/nfr-targets.md |

## SDLC Process Requirements (R-2)
| Req | Owner | Task(s) | Evidence Location |
|---|---|---|---|
| SE-1 SRS | Shiva (maintainer) | done | `Final_SRS_Submission.pdf` (commit `a51c14e`) |
| SE-2 Architecture & UML/ER | Shiva, Tatwik, Farhan | SR-05 (#30, PR #31), TS-04 (#27, PR #29), MF-04 (#34, PR #35) | `docs/architecture/` (`overview.md`, `analysis.md`, `playlist.md`) |
| SE-3 ADRs | All | SR-03 (#21, PR #22), SR-04 (#25, PR #26), SR-05 (#30, PR #31), TS-04 (#27, PR #29), MF-04 (#34, PR #35) | `docs/adr/` (`0001-runtime-and-toolchain.md`, `0002-provider-and-errors.md`, `0003-similarity-scoring.md`, `0004-trusted-confirmation.md`, `0005-playlist-selection.md`, `0006-token-storage-and-persistence.md`, `0007-interest-profile.md`) |
| SE-4 Dev plan & breakdown | Tatwik | TS-00 (#1, PR #10) | `docs/plan/development-plan.md` |
| SE-5 Traceability | All | TS-00..SR-18 (#1, PR #10) | `docs/traceability.md` |
| SE-6 Provider interface | Shiva | SR-04 (#25, PR #26), SR-15 | `src/yt_intel_mcp/provider/base.py` |
| SE-7 User & Developer docs | Tatwik, Shiva | SR-04 (#25, PR #26), TS-16, SR-17 | `docs/user/`, `docs/developer/` (`docs/developer/fixtures.md`) |
| SB-1..SB-6 Second Brain | All | TS-01 (#3, PR #13), TS-02 (#6, PR #14), SR-02 (#5, PR #15), MF-03 (#7, PR #17), TS-03 (#9, PR #18), TS-04 (#27, PR #29), TS-05 (#19, PR #20), SR-05 (#30, PR #31), SR-06 (#32, PR #33), MF-04 (#34, PR #35) | `brain/` & git history (`brain/projects/stage-1-review.md`, `[[brain/inbox/ai-session-2026-11-25-tatwik-TS-03]]`, `[[brain/inbox/ai-session-2026-11-25-tatwik-TS-05]]`, `[[brain/inbox/ai-session-2026-11-26-tatwik-TS-04]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-05]]`, `[[brain/inbox/ai-session-2026-11-26-shiva-SR-06]]`, `[[brain/inbox/ai-session-2026-11-26-farhan-MF-04]]`) |
| SB-1, SB-3 Validator checks | Farhan | MF-01 (#4, PR #12) | `scripts/validate_brain.py`, `scripts/validate_skills.py`, `tests/unit/test_validators.py` (TQ-1, TQ-4), [[brain/inbox/ai-session-2026-11-23-farhan-MF-01]] |
| SB-6 Farhan's Stage 1 research notes | Farhan | MF-03 (#7, PR #17) | [[brain/inbox/ai-session-2026-11-25-farhan-MF-03]] |
| TQ-5 Fixture CI | Farhan | MF-02 (#8, PR #16) | `.github/workflows/ci.yml`, [[brain/inbox/ai-session-2026-11-25-farhan-MF-02]] |
| TQ-7 Skill evaluations | All | TS-03 (#9, PR #18), TS-05 (#19, PR #20), SR-06 (#32, PR #33), SR-07, MF-17 | `docs/testing/skill-evals.md` |
| TQ-8 Defect log & regressions | Fixer | MF-06, ongoing | `docs/testing/defect-log.md` |
