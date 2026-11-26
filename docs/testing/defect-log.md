# Defect and Regression Log (`TQ-8`)

- **Task:** `MF-06`
- **Owner:** Mohammed Farhan (`@farhan4599`)
- **Reviewer:** Madire Shiva Reddy (`@Shiva0025`)
- **GitHub Issue:** `#36`
- **GitHub PR:** pending (`MF-06`)
- **Requirements:** `TQ-8`, `SE-5`, `NFR-10`, `SB-1`

## 1. Defect Handling Protocol (`TQ-8`)

Whenever a real defect is discovered during integration testing, system testing, host compatibility verification (`TS-15`), CI runs, or manual usage:

1. Never bury a real defect fix inside an unrelated feature Pull Request.
2. Open a dedicated GitHub Issue labelled `type:defect`, `stage:<n>`, and `req:<ID>` using `.github/ISSUE_TEMPLATE/defect.md`.
3. Create a fix branch named `<member>/fix-<issue#>-<short-slug>` from an up to date `main`.
4. Add a dedicated regression test (verified to fail before the fix and pass after the fix).
5. Record the defect below with real GitHub Issue and PR numbers, root cause, affected requirement, and exact regression test identifier.
6. Merge via Pull Request (`Closes #<issue#>`) after CI passes and at least one teammate approves.

## 2. Recorded Defects

| Defect ID / Issue | Date Found | Stage | Found By | Affected Req(s) | Root Cause Summary | Fix Branch & PR | Regression Test (`TQ-8`) | Status |
|---|---|---|---|---|---|---|---|---|
| *(None logged yet as of Stage 2 initialization in `MF-06`)* | — | — | — | — | — | — | — | — |

*(Note: Pre existing Windows `Path.relative_to` backslash vs POSIX slash assertion mismatch in `tests/unit/test_validators.py` observed on Windows local runs is documented in `docs/testing/skill-evals.md` and `docs/testing/test-plan.md`; Linux `ubuntu-latest` CI passes cleanly. If prioritized for Windows parity, track via a dedicated `type:defect` issue and fix PR under this log.)*

## 3. Defect Entry Template (`TQ-8`)

Copy and fill this block for every new defect entry alongside adding a row to Section 2:

```markdown
### Defect `#<issue-number>` — `<Short Defect Title>`
- **Date Found:** `YYYY-MM-DD`
- **Stage / Found By:** `Stage <1|2|3|4>` / `<Member Full Name>`
- **Affected Requirements & Invariants:** `<FR/NFR/SK/TQ IDs>`, `<INV-xx>`
- **Reproduction:** `<Minimal steps or failing command>`
- **Root Cause:** `<Concise technical explanation>`
- **Fix Branch / PR:** `<member>/fix-<issue#>-<short-slug>` | `PR #<pr-number>`
- **Regression Test:** `<tests/.../test_file.py::test_function_name>` (verified failing before fix, passing after fix)
```
