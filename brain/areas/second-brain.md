---
title: Second Brain Architecture and Knowledge Management
type: architecture
status: distilled
authors:
  - Molleti Tatwik Sai
created: 2026-11-23
updated: 2026-11-23
tags:
  - second-brain
  - para
  - standards
  - sdlc
requirements:
  - SB-1
  - SB-2
  - SB-3
  - SB-4
  - SB-5
  - SB-6
issues:
  - "#3"
prs:
  - "#10"
sources:
  - "The AI-Assisted Software Development Life Cycle (SDLC) Section 1"
  - "Building a Second Brain (Tiago Forte)"
---

# Second Brain Architecture and Knowledge Management

## 1. Overview
The Second Brain serves as the persistent, explicit knowledge vault for the YouTube Video Intelligence MCP Server project. It maintains research, engineering decisions, architectural patterns, and execution records following the PARA organization system.

## 2. PARA Structure
Notes are organized strictly by actionability:
- `brain/inbox/`: Unsorted notes, incoming literature, research findings, and AI assisted session records.
- `brain/projects/`: Active deliverables with deadlines (project overview, stage review notes).
- `brain/areas/`: Long term standards, engineering responsibilities, security patterns, and governance.
- `brain/resources/`: Reference materials, algorithm specifications, API limitations, and quota models.
- `brain/archive/`: Inactive records, completed project stages, and superseded designs.

Entry points:
- `brain/index.md`: The single navigational entry point linking every active note in the vault.
- `brain/log.md`: Chronological log recording all runs, ingestions, and maintenance operations.

## 3. Engineering Rules and Compliance
- **SB-1**: Every note links to related notes using `[[wikilinks]]`, and cites valid SRS v1.0 requirement IDs, real GitHub issue numbers, and pull request numbers.
- **SB-2**: At the end of each development stage, author a stage review note analyzing successes, failures, and needed process corrections.
- **SB-3**: Every Architecture Decision Record (ADR) and Agent Skill must cite at least one distilled note (`status: distilled`).
- **SB-4**: The repository root maintains an authoritative `AGENTS.md` defining architectural boundaries.
- **SB-5**: All vault modifications, including notes authored with AI assistance, must merge through pull requests with human review.
- **SB-6**: Every team member must author notes directly in commit history.

## 4. Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/agent-skills-specification|Agent Skills Specification]]
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
