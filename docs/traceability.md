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
| FR-2.1 | Tatwik | TS-02, TS-06, TS-11 | #6 (TS-02), pending (TS-06) | pending | ST_FR2 | n/a — no skill uses FR-2 (SRS Section 6.2) | brain/inbox/channel-similarity.md (target: brain/resources/channel-similarity.md) |
| FR-2.2 | Tatwik | TS-02, TS-08, TS-11 | #6 (TS-02), pending (TS-08) | pending | UT_SIM | n/a — no skill uses FR-2 (SRS Section 6.2) | brain/inbox/channel-similarity.md (target: brain/resources/channel-similarity.md) |
| FR-3.1 | Tatwik | TS-02, TS-12 | #6 (TS-02), pending (TS-12) | pending | UT_PROF, UT_STAT_TS | n/a — no skill uses FR-3 (SRS Section 6.2) | brain/inbox/youtube-event-timestamps.md (target: brain/resources/youtube-event-timestamps.md) |
| FR-3.2 | Tatwik | TS-02, TS-12 | #6 (TS-02), pending (TS-12) | pending | UT_PROF, UT_STAT_TS | n/a — no skill uses FR-3 (SRS Section 6.2) | brain/inbox/youtube-event-timestamps.md (target: brain/resources/youtube-event-timestamps.md) |
| FR-3.3 | Tatwik | TS-02, TS-13 | #6 (TS-02), pending (TS-13) | pending | ST_FR3, NT_SIG | n/a — no skill uses FR-3 (SRS Section 6.2) | brain/inbox/youtube-event-timestamps.md (target: brain/resources/youtube-event-timestamps.md) |
| FR-4.1 | Tatwik | TS-02, TS-07, TS-14 | #6 (TS-02), pending (TS-07) | pending | ST_FR4, UT_STAT_BUCKET | video-to-playlist (step 5) | brain/inbox/engagement-analysis.md (target: brain/projects/engagement-analysis.md) |
| FR-4.2 | Tatwik | TS-02, TS-14 | #6 (TS-02), pending (TS-14) | pending | ST_FR4, UT_STAT_ZERO | n/a — playlist analysis has no period compare | brain/inbox/engagement-analysis.md (target: brain/projects/engagement-analysis.md) |
| FR-4.3 | Tatwik | TS-02, TS-14 | #6 (TS-02), pending (TS-14) | pending | SEC_PII, UT_STAT_TS | n/a — playlist analysis has no raw user lists | brain/inbox/engagement-analysis.md (target: brain/projects/engagement-analysis.md) |
| FR-5.1 | Farhan | MF-08, MF-11 | pending (MF-08) | pending | ST_FR5, UT_SOLV_WINDOW | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.1a | Farhan | MF-09 | pending (MF-09) | pending | UT_LANG, NT_LANG | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.2 | Farhan | MF-10 | pending (MF-10) | pending | UT_SOLV, UT_DUR, X_PERF_SELECT | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.3 | Farhan | MF-11 | pending (MF-11) | pending | ST_FR5 | video-to-playlist | brain/projects/playlist-constraints.md |
| FR-5.4 | Farhan | MF-12, MF-13 | pending (MF-12) | pending | NT_HITL, NT_HITL_UNAVAIL, ST_FR5_CONFIRM | video-to-playlist | brain/resources/mcp-elicitation-confirmation.md |
| FR-5.5 | Farhan | MF-14 | pending (MF-14) | pending | IT_DRAFT, IT_DRAFT_PARTIAL, NT_DRAFT_STALE | video-to-playlist | brain/projects/partial-playlist-outcomes.md |
| FR-6.1 | Shiva | SR-10 | pending (SR-10) | pending | UT_QUOTA | video-to-playlist | brain/resources/youtube-quota-costs.md |
| FR-6.2 | Shiva | SR-10, MF-11, MF-14 | pending (SR-10) | pending | QT_1, QT_2, QT_3 | video-to-playlist | brain/resources/youtube-quota-costs.md |
| FR-6.3 | Shiva | SR-11 | pending (SR-11) | pending | IT_CACHE, NT_QUOTA | video-to-playlist | brain/resources/youtube-quota-costs.md |
| FR-7.1 | Shiva | SR-13 | pending (SR-13) | pending | SEC_OAUTH | local-check | brain/resources/google-oauth-testing-mode.md |
| FR-7.2 | Shiva | SR-12, SR-13 | pending (SR-12) | pending | NT_AUTH, SEC_OAUTH | local-check | brain/resources/google-oauth-testing-mode.md |
| FR-7.3 | Shiva | SR-13, MF-14 | pending (SR-13) | pending | NT_ACC | local-check | brain/resources/google-oauth-testing-mode.md |
| FR-8.1 | Shiva | SR-04, SR-08, SR-14, SR-15 | pending (SR-04) | pending | IT_PROV | local-check | brain/areas/engineering/provider-interface-pattern.md |
| FR-8.2 | Shiva | SR-08 | pending (SR-08) | pending | SEC_PII | local-check | brain/areas/engineering/provider-interface-pattern.md |

## Agent Skills
| Req | Owner | Task(s) | Issue | PR | Tests | Skill | Brain Note |
|---|---|---|---|---|---|---|---|
| SK-1 | Farhan | TS-09, MF-15 | pending (TS-09) | pending | SE_EVAL_SUM, TQ-7, NFR-2 run | video-to-playlist | brain/areas/skill-video-to-playlist.md |
| SK-2 | Farhan | MF-05, MF-16 | pending (MF-05) | pending | TQ-7 | local-check | brain/areas/skill-local-check.md |
| SK-3 | Tatwik | TS-01 | #3 | pending | TQ-7, brain validation | brain-ingest | brain/areas/second-brain.md |
| SK-4 | Tatwik | TS-05 | pending (TS-05) | pending | TQ-7, brain validation | brain-refine | brain/areas/second-brain.md |
| SK-5 | Shiva | SR-06 | pending (SR-06) | pending | TQ-7 | brain-query | brain/areas/second-brain.md |

## Non-Functional Requirements
| Req | Owner | Task(s) | Issue | PR | Tests | Skill | Brain Note |
|---|---|---|---|---|---|---|---|
| NFR-1 | Tatwik / Farhan / Shiva | TS-08, MF-10, SR-11 | pending (TS-08) | pending | X_PERF_SCORE, X_PERF_SELECT, IT_CACHE | n/a — performance target | brain/resources/nfr-targets.md |
| NFR-2 | Shiva / Farhan | SR-10, SR-16, MF-15 | pending (SR-10) | pending | QT_1..3, SK-1 budget, live cap | video-to-playlist | brain/resources/nfr-targets.md |
| NFR-3 | Shiva | SR-12, SR-13 | pending (SR-12) | pending | SEC_OAUTH | n/a — auth storage | brain/resources/nfr-targets.md |
| NFR-4 | Farhan | MF-02, TS-00 | #1, #8 | pending | Gitleaks CI | n/a — repo hygiene | brain/resources/nfr-targets.md |
| NFR-5 | Tatwik | TS-06, TS-04, MF-04 | pending (TS-06) | pending | NT_VAL | n/a — input validation | brain/resources/nfr-targets.md |
| NFR-6 | Farhan | MF-07, MF-13 | pending (MF-07) | pending | NT_HITL injection | video-to-playlist | brain/areas/security/prompt-injection-defence.md |
| NFR-7 | Shiva / Tatwik | SR-08, SR-12, TS-14 | pending (SR-08) | pending | SEC_PII | n/a — privacy | brain/resources/nfr-targets.md |
| NFR-8 | Shiva / Farhan | SR-14, MF-14 | pending (SR-14) | pending | IT_PROV retry, IT_DRAFT_PARTIAL | n/a — reliability | brain/resources/nfr-targets.md |
| NFR-9 | Farhan / all | TS-04, MF-04, SR-17, TS-16 | pending (TS-04) | pending | Tool reference CI check | n/a — usability | brain/resources/nfr-targets.md |
| NFR-10 | Farhan / Shiva | MF-02, SR-15, MF-18 | #8 | pending | CI coverage >=85%, lint, mypy, import-lint | n/a — maintainability | brain/resources/nfr-targets.md |

## SDLC Process Requirements (R-2)
| Req | Owner | Task(s) | Evidence Location |
|---|---|---|---|
| SE-1 SRS | Shiva (maintainer) | done | `Final_SRS_Submission.pdf` (commit `a51c14e`) |
| SE-2 Architecture & UML/ER | Shiva, Tatwik, Farhan | SR-05, TS-04, MF-04 | `docs/architecture/` |
| SE-3 ADRs | All | SR-03, SR-04, SR-05, TS-04, MF-04 | `docs/adr/` |
| SE-4 Dev plan & breakdown | Tatwik | TS-00 (#1) | `docs/plan/development-plan.md` |
| SE-5 Traceability | All | TS-00..SR-18 (#1) | `docs/traceability.md` |
| SE-6 Provider interface | Shiva | SR-04, SR-15 | `src/yt_intel_mcp/provider/base.py` |
| SE-7 User & Developer docs | Tatwik, Shiva | TS-16, SR-17 | `docs/user/`, `docs/developer/` |
| SB-1..SB-6 Second Brain | All | TS-01 (#3, PR #13), TS-02 (#6), SR-02 (#5), MF-03 (#7), TS-05, reviews | `brain/` & git history (`channel-similarity.md`, `youtube-event-timestamps.md`, `engagement-analysis.md`, `[[brain/inbox/ai-session-2026-11-25-tatwik-TS-02]]`) |
| SB-1, SB-3 Validator checks | Farhan | MF-01 (#4, PR #12) | `scripts/validate_brain.py`, `scripts/validate_skills.py`, `tests/unit/test_validators.py` (TQ-1, TQ-4), [[brain/inbox/ai-session-2026-11-23-farhan-MF-01]] |
| TQ-7 Skill evaluations | All | TS-03 (#9), SR-07, MF-17 | `docs/testing/skill-evals.md` |
| TQ-8 Defect log & regressions | Fixer | MF-06, ongoing | `docs/testing/defect-log.md` |
