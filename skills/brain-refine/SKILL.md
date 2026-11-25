---
name: brain-refine
description: Refines Second Brain inbox notes into canonical PARA folders, merges duplicates, promotes validated notes to distilled status, and repairs wikilinks, index entries, and traceability links.
---

# Brain Refine Skill

## Purpose
Distil raw research materials captured in `brain/inbox/` into their permanent PARA homes (`brain/projects/`, `brain/areas/`, `brain/resources/`, `brain/archive/`), eliminate duplicate notes, promote verified knowledge to `status: distilled`, and keep all cross references and traceability links intact per [[brain/areas/second-brain|Second Brain Architecture]] (`SK-4`, `SB-1`, `SB-3`).

## Preconditions
1. Confirm each candidate inbox note has been verified against `Final_SRS_Submission.pdf` (version 1.0) and its cited external documentation before promoting `status` to `distilled`.
2. Identify overlapping notes across `brain/inbox/` and canonical PARA folders (`brain/projects/`, `brain/areas/`, `brain/resources/`) so duplicate coverage is consolidated cleanly rather than split across two files.
3. Keep `ai-session-*.md` execution logs in `brain/inbox/` unless explicitly archiving completed stage records.

## Refinement Procedure
1. **Audit Inbox Candidates:** Review all non session markdown notes inside `brain/inbox/` and map each note to its canonical PARA folder:
   - `brain/projects/`: Active project plans, feature constraint designs, execution specifications, and stage reviews.
   - `brain/areas/`: Enduring engineering patterns, security standards, Second Brain rules, and `skill-*.md` skill notes.
   - `brain/resources/`: Reference material, API limits, quota pricing, protocol details, and mathematical models.
   - `brain/archive/`: Inactive, completed, or superseded records retained for audit history.
2. **Merge Overlapping Coverage:** When two notes cover the same requirement surface, merge all unique operational details, constants, error codes, contributors (`authors`), `requirements`, `issues`, `prs`, and dated `sources` into the canonical PARA note, then remove the redundant `brain/inbox/` file.
3. **Promote and Distill Standalone Notes:** Move each remaining verified research note into its canonical PARA destination (`git mv` or create and `git rm`), update frontmatter to `status: distilled` and `updated: YYYY-MM-DD`, preserve prior `issues` and `prs`, and append the refinement GitHub Issue and Pull Request numbers (`SB-1`).
4. **Repair Vault and Documentation Links:**
   - Replace every outdated `[[brain/inbox/<slug>]]` wikilink in existing vault notes, AI session records, and `brain/log.md` with the promoted PARA target path (removing self links created by merges).
   - Move links inside `brain/index.md` out of inbox sections into the matching PARA sections so every active note remains directly indexed.
   - Update `docs/traceability.md` to list the canonical PARA note paths instead of temporary inbox staging annotations.
5. **Validate and Review (`SB-5`):**
   - Run `scripts/validate_skills.py` and `scripts/validate_brain.py` to confirm zero schema violations, zero unresolved wikilinks, valid `SRS` requirement IDs (`scripts/srs_ids.txt`), and valid distilled citations (`SB-3`).
   - Record the refinement session in `brain/inbox/ai-session-YYYY-MM-DD-<member>-<task>.md`, append a 4 column entry to `brain/log.md`, and submit all changes through a Pull Request with human review (`SB-5`).

## Governance and Safety
Detailed operational rationale and evaluation targets for this workflow are maintained in [[brain/areas/skill-brain-refine|Skill Note: brain-refine]]. Never include secrets, OAuth credentials, or real user identifiers anywhere in refined notes or commit history (`NFR-4`, `NFR-7`).
