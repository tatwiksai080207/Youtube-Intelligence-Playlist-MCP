Closes #<issue-number>

## Summary
- **Task / Defect:** `<TASK-ID or fix-#n>`
- **Requirements:** <FR/NFR/SK/SDLC IDs>
- **Invariants Preserved:** <INV-xx>
- **What & Why:** <2–4 bullets>

## Verification Results
- `ruff check` / `ruff format --check`: PASS | FAIL | NOT RUN (<reason>)
- `mypy src`: PASS | FAIL | NOT RUN (<reason>)
- `pytest -m "not live" --cov=yt_intel_mcp`: PASS (<coverage>%) | FAIL | NOT RUN (<reason>)
- `validate_skills.py` / `validate_brain.py`: PASS | FAIL | NOT RUN (<reason>)
- **SRS Tests Added:** <e.g., `UT_SIM`, `NT_VID`>

## AI-Assisted Development Disclosure (SDLC Section 6)
- **AI-Assisted Parts:** <describe what AI drafted>
- **Human Author Review:** I reviewed every line and can explain this change in project reviews.

## Reviewer Checklist (Human Approval Required)
- [ ] Acceptance criteria and SRS invariants are satisfied
- [ ] No secrets, tokens, or real personal data included
- [ ] No out-of-scope additions (`agent_code/` not tracked)
- [ ] `docs/traceability.md` and brain notes back-linked where applicable
- [ ] I understand this diff and can explain it
