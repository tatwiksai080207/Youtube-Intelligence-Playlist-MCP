---
title: Agent Skills Specification and Directory Conventions
type: reference
created: 2026-11-09
tags:
  - skills
  - agents
  - specification
  - standards
requirements:
  - SK-1
  - SK-2
  - C-11
---

# Agent Skills Specification and Directory Conventions

## Summary
Agent Skills follow the open agentskills.io format. They package repeatable workflows, domain instructions, and evaluation scripts into discoverable markdown directories that AI assistants can automatically leverage.

## Directory Structure
Each skill resides in its own subfolder within `skills/`:

```text
skills/
└── <skill-name>/
    ├── SKILL.md            (Mandatory definition and instructions)
    ├── scripts/            (Optional helper utilities and tests)
    └── references/         (Optional context and reference data)
```

## Frontmatter Requirements
The `SKILL.md` file must begin with YAML frontmatter:
1. `name`: Lowercase letters, numbers, and single hyphens only. Must exactly match the parent folder name (length 1 to 64 characters).
2. `description`: Concise explanation describing what the skill does and when an agent should trigger it (length 1 to 1024 characters).
3. Optional metadata: Version, requirements tags, and links to distilled Second Brain notes.

## Required Project Skills
- `video-to-playlist`: Multi stage product workflow turning a single seed video into a confirmed, created playlist.
- `local-check`: Validation skill verifying build, test suite execution, server initialization, and ping responses without consuming quota.
- `brain-ingest`, `brain-refine`, `brain-query`: Second Brain management and curation skills.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]

