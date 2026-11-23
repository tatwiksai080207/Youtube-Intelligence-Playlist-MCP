---
name: brain-ingest
description: Ingests reference materials, technical documentation, and AI session summaries into the Second Brain inbox with standard YAML frontmatter and wikilinks.
---

# Brain Ingest Skill

## Purpose
Collect incoming research, API specifications, and architectural patterns into the Second Brain vault using consistent metadata, valid requirement IDs, and linking standards defined in [[brain/areas/second-brain|Second Brain Architecture]].

## Ingest Procedure
1. Create a new markdown note in `brain/inbox/<note-slug>.md`.
2. Add mandatory YAML frontmatter matching the Second Brain schema:
   - `title`: Clean descriptive title string.
   - `type`: Note classification (`reference`, `concept`, `architecture`, `security`, `project`, `decision`, `session`, `ai-session`, `stage-review`, `skill-note`).
   - `status`: Default to `inbox` for freshly ingested material.
   - `authors`: Array containing the full names of contributing team members.
   - `created`: Ingestion date in `YYYY-MM-DD` format.
   - `updated`: Modification date in `YYYY-MM-DD` format.
   - `tags`: Array of relevant searchable keywords.
   - `requirements`: Array of valid SRS v1.0 requirement IDs (listed in `scripts/srs_ids.txt`), or `["n/a"]` with an explicit reason in the body.
   - `issues`: Array of related GitHub issue references (such as `["#3"]`), or empty list.
   - `prs`: Array of related GitHub pull request references (such as `["#10"]`), or empty list.
   - `sources`: Array of verifiable sources with dated consultation checkpoints.
3. Ensure the note body begins with a clear summary section followed by detailed technical analysis.
4. Add at least one [[wikilink]] connecting the note to existing vault notes or `brain/index.md`.
5. Update `brain/index.md` so the new note is immediately discoverable.
6. Append a formatted entry to `brain/log.md`:
   `| YYYY-MM-DD | brain-ingest | <Full Member Name> | <notes touched> | <PR/Issue or pending> |`

## Governance and Quality
Every ingested note must be reviewed and merged through a pull request per requirement SB-5. Never commit secrets, tokens, or personal identifiers into ingested notes.
