---
name: brain-ingest
description: Ingests reference materials, technical documentation, and AI session summaries into the Second Brain inbox with standard YAML frontmatter and wikilinks.
---

# Brain Ingest Skill

## Purpose
Collect incoming research, API specifications, and architectural patterns into the Second Brain using consistent metadata and linking standards.

## Ingest Procedure
1. Create a markdown note in `brain/inbox/<note-slug>.md` or the appropriate PARA folder.
2. Add YAML frontmatter containing:
   - `title`: Clean note title.
   - `type`: Category (`reference`, `decision`, `concept`, or `session`).
   - `created`: Date in YYYY-MM-DD format.
   - `tags`: Array of relevant keywords.
   - `requirements`: Array of associated requirement IDs (for example `[FR-1, FR-6]`).
3. Ensure the body begins with a concise summary followed by detailed findings.
4. Add at least one [[wikilink]] connecting the note to existing notes or the index.
5. Append an entry to `brain/log.md`.

