---
name: brain-query
description: Queries the Second Brain vault to answer engineering questions with wikilink citations, refuses to guess when facts are missing, and drafts SRS or ADR sections strictly from distilled notes.
---

# Brain Query Skill

## Purpose
Retrieve grounded project knowledge from `brain/` to answer engineering questions with explicit `[[wikilink]]` citations and draft formal specification sections (SRS clauses, ADRs, architecture notes, and developer docs) without fabricating unverified facts (`SK-5`, `SB-3`). Governed by [[brain/areas/second-brain|Second Brain Architecture]], [[brain/resources/agent-skills-specification|Agent Skills Specification]], and [[brain/areas/skill-brain-query|Skill Note: brain-query]].

## Mode 1: Grounded Vault Question Answering
1. **Locate Candidate Notes:** Start at [[brain/index|Second Brain Index]] to map the user's question to canonical PARA folders (`brain/resources/`, `brain/projects/`, `brain/areas/`, `brain/archive/`) and check `brain/inbox/` session records only when historical context is requested.
2. **Prefer Distilled Knowledge (`SB-3`):** Prioritize notes with `status: distilled`. If a relevant fact only appears in a `status: inbox` note, label it explicitly as unrefined inbox context (`status: inbox`) and note that `brain-refine` has not distilled it yet.
3. **Cite Every Claim Inline:** Attach a valid `[[brain/<path>|<Title>]]` wikilink (with optional `#Section` anchor) to every factual statement, constant, constraint, or error mapping in the answer.
4. **Refuse When Absent or Ambiguous:** If the requested threshold, API behavior, error code, or decision is missing from `brain/`, or if notes disagree without a resolved decision:
   - **STOP and refuse to guess.** Never fill gaps from general training memory.
   - Report `Not found in the Second Brain vault` alongside the exact vault notes inspected and any adjacent facts that do exist.
   - Recommend verifying the primary baseline (`Final_SRS_Submission.pdf` or official documentation) and ingesting the missing knowledge via `brain-ingest` (`SK-3`).

## Mode 2: SRS, ADR, and Technical Document Drafting
1. **Gather Grounded Sources:** Collect all relevant `status: distilled` notes via [[brain/index|Second Brain Index]], verify requirement identifiers against `scripts/srs_ids.txt`, and cross check active Issue/PR numbers (`SB-1`) and Decision Register items in `docs/plan/development-plan.md`.
2. **Draft with Explicit Provenance (`SB-3`):**
   - For **SRS sections**, preserve exact numeric targets, error codes, and scope exclusions with inline `[[brain/...]]` source citations.
   - For **ADRs**, populate `Context`, `Decision`, `Alternatives Considered`, `Consequences`, and a `Distilled Brain Sources` section citing each underlying `status: distilled` note.
3. **Mark Vault Gaps Visibly:** Whenever a required parameter, decision, or test target is not recorded in `brain/`, insert an explicit `[MISSING FROM VAULT]` placeholder rather than inventing a numeric default.
4. **Keep Queries Read Only:** Answering a question never modifies vault notes. Any drafted SRS, ADR, or documentation artifact must be reviewed and merged through a Pull Request (`SB-5`) and pass `scripts/validate_skills.py` and `scripts/validate_brain.py`.

## Governance and Safety
Never output secrets, OAuth tokens, client JSON contents, or real personal data when quoting or summarizing vault notes (`NFR-4`, `NFR-7`). Never cite an inbox note as the sole authority for an ADR or skill (`SB-3`).
