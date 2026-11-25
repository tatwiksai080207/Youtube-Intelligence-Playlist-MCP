# Agent Skill Evaluations (`TQ-7`)

This document records formal evaluations of every Agent Skill before each stage submission, satisfying requirement `TQ-7` and `SDLC` Section 5.

## Evaluation Summary

| Stage | Skill ID | Skill Name | Evaluation Date | Evaluator | Result | Evidence |
|---|---|---|---|---|---|---|
| Stage 1 | `SK-3` | `brain-ingest` | 2026-11-25 | Molleti Tatwik Sai | **PASS** | `scripts/validate_skills.py`, `scripts/validate_brain.py`, CI run `45619944133` |
| Stage 2 | `SK-4` | `brain-refine` | 2026-11-25 | Molleti Tatwik Sai | **PASS** | `scripts/validate_skills.py`, `scripts/validate_brain.py`, Issue `#19`, PR `#20` |
| Stage 2 | `SK-2` | `local-check` v1 | 2026-11-25 | Mohammed Farhan | **PASS** for v1 | `scripts/local_check.py`, `tests/unit/test_local_check.py`, Issue `#23` |

---

## Stage 1 Evaluation: `brain-ingest` (`SK-3`)

**Skill Path:** `skills/brain-ingest/SKILL.md`  
**Distilled Brain Citation (`SB-3`):** `[[brain/areas/second-brain|Second Brain Architecture]]`  
**Tasks Exercising Skill:** `TS-01` (`#3`, PR `#13`), `TS-02` (`#6`, PR `#14`), `SR-02` (`#5`, PR `#15`), `MF-03` (`#7`, PR `#17`), `TS-03` (`#9`, PR `#18`)

### Test Cases and Observed Results

| Case ID | Scenario | Expected Behaviour | Observed Result | Status |
|---|---|---|---|---|
| `SE-ING-01` | Skill frontmatter and `SB-3` citation check | `name` matches folder (`brain-ingest`), `description` is 1 to 1,024 chars, and body cites a `status: distilled` brain note | `python scripts/validate_skills.py` printed `Skill validation passed.` | **PASS** |
| `SE-ING-02` | Multi member ingestion into `brain/inbox/` (`SB-6`) | All 3 members ingest research notes into `brain/inbox/` with `status: inbox`, valid SRS v1.0 IDs, dated sources, `[[wikilinks]]`, and `index.md` links | Tatwik (`TS-02`: 3 research notes), Shiva (`SR-02`: 2 research notes), and Farhan (`MF-03`: 3 research notes) plus 7 AI session notes all merged and validated | **PASS** |
| `SE-ING-03` | Vault integrity across all notes (`SB-1`) | Every note passes YAML frontmatter schema, `scripts/srs_ids.txt` allow list, zero broken `[[wikilinks]]`, and direct indexing in `brain/index.md` | `python scripts/validate_brain.py` printed `Brain validation passed.` across all 31 vault markdown files | **PASS** |
| `SE-ING-04` | Rejection of invalid metadata and missing citations (`TQ-4`) | Malformed frontmatter, draft requirement IDs, missing `sources`/`authors`, unindexed notes, and non distilled citations fail validation | Verified by `tests/unit/test_validators.py` (`55 passed` in CI `ubuntu-latest` run `45619944133`) | **PASS** |
| `SE-ING-05` | Secret and PII hygiene (`NFR-4`, `NFR-7`) | Zero tokens, client secrets, credentials, or real personal identifiers in ingested notes | `gitleaks/gitleaks-action@v2` passed on all Stage 1 PRs (`#10` through `#17`) | **PASS** |

### Observations and Adjustments from Stage 1 Evaluation
1. **Log Format Alignment (`SKILL.md` vs `brain/log.md`):** During `TS-02` and `SR-02`, `skills/brain-ingest/SKILL.md` step 6 documented a 5 column log example starting with `brain-ingest` before `<Full Member Name>`, whereas `brain/log.md` defines 4 columns (`| Timestamp | Actor | Action | Output / Notes |`). In `TS-03`, `skills/brain-ingest/SKILL.md` step 6 was updated to match the 4 column table, and `brain/log.md` entries were normalized so the team member appears under `Actor` and the `brain-ingest` task appears under `Action`.
2. **Windows Local Validator Unit Tests (`tests/unit/test_validators.py`):** Running `pytest` directly on Windows reports 28 path separator assertion mismatches in `test_validators.py` because test fixtures compare `brain/...` with forward slashes against Windows `Path.relative_to` backslashes in stderr, whereas Linux CI (`ubuntu-latest`) runs and passes all 55 tests with 100 percent coverage. CLI execution of `validate_brain.py` and `validate_skills.py` passes cleanly on both Windows and Linux.

---

## Stage 2 Evaluation: `brain-refine` (`SK-4`)

**Skill Path:** `skills/brain-refine/SKILL.md`  
**Distilled Brain Citations (`SB-3`):** `[[brain/areas/second-brain|Second Brain Architecture]]`, `[[brain/areas/skill-brain-refine|Skill Note: brain-refine]]`  
**Tasks Exercising Skill:** `TS-05` (`#19`, PR `#20`)

### Test Cases and Observed Results

| Case ID | Scenario | Expected Behaviour | Observed Result | Status |
|---|---|---|---|---|
| `SE-REF-01` | Skill schema and `SB-3` distilled citation | `name` matches folder (`brain-refine`), `description` within 1 to 1,024 chars, and body cites `status: distilled` notes | `py -3.11 scripts/validate_skills.py` printed `Skill validation passed.` | **PASS** |
| `SE-REF-02` | Duplicate OAuth note consolidation | Merge unique PKCE, `get_auth_status`, `ADR-0006`, `#5`, and `#15` details from `brain/inbox/oauth-scopes-and-token-storage.md` into `brain/resources/google-oauth-testing-mode.md` and remove duplicate | Content consolidated cleanly into `google-oauth-testing-mode.md` and redundant inbox file deleted | **PASS** |
| `SE-REF-03` | PARA promotion and `status: distilled` transition | Promote remaining 7 Stage 1 research notes to canonical `brain/resources/` and `brain/projects/` destinations with `status: distilled` while keeping `ai-session-*.md` in `brain/inbox/` | All 7 notes promoted (4 resources, 3 projects) alongside `brain/areas/skill-brain-refine.md` and `ai-session-2026-11-25-tatwik-TS-05.md` | **PASS** |
| `SE-REF-04` | Vault wikilink repair and `docs/traceability.md` cleanup (`SB-1`) | Replace all stale `[[brain/inbox/...]]` links across notes, AI session records, `brain/index.md`, `brain/log.md`, and `docs/traceability.md` | `py -3.11 scripts/validate_brain.py` printed `Brain validation passed.` across all 32 vault markdown files | **PASS** |

## Stage 2 Evaluation of `local-check` v1 (`SK-2`)

- **Skill path** `skills/local-check/SKILL.md`
- **Distilled citation** `[[brain/areas/skill-local-check|Local Check Skill]]`
- **Execution** `python scripts/local_check.py` on macOS with Python 3.14.2

| Case ID | Scenario | Observed result | Status |
|---|---|---|---|
| `SE-LOCAL-01` | Build, tests, and MCP initialization | Built the wheel, ran 59 tests, and initialized the fixture-mode server over stdio | **PASS** |
| `SE-LOCAL-02` | Fetch unavailable in v1 | Reported `NOT RUN: no read-only fetch tool registered yet` and summarized three passes, zero failures, and one step not run | **PASS** for v1 |
| `SE-LOCAL-03` | Test and handshake failures | Automated test verified nonzero exit, the failed checks, the dependent fetch skip, and the final failure count | **PASS** |

The read-only fixture tool invocation remains pending MF-16. The v1 evaluation used zero live YouTube quota.
