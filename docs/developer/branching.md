# Branching, Commits, Pull Requests and Release Strategy

## 1. Branching Model
- `main` is the single protected integration branch. **No direct pushes to `main`.**
- Every task or defect fix starts from an up to date `main` on a short lived branch:
  - Feature or task: `<member>/<TASK-ID>-<short-slug>` (for example, `tatwik/TS-01-brain-to-spec`)
  - Defect fix: `<member>/fix-<issue#>-<short-slug>` (must include regression test and `docs/testing/defect-log.md` update)
- One GitHub Issue maps to one branch and one Pull Request.

## 2. Commit Convention
Format: `<type>(<scope>): <summary> [<TASK-ID>] (<REQ-IDs>)`  
Types: `feat`, `fix`, `test`, `docs`, `ci`, `chore`, `refactor`, `brain`, `skill`.

## 3. Pull Request and Review Policy
- Every change (code, tests, docs, `skills/`, `brain/`) merges via PR with:
  - Linked GitHub Issue (`Closes #<n>`)
  - Passing CI (`lint-and-validate`)
  - At least **1 human approval** (2 approvals for contract, schema, or CI gate changes)
  - Disclosure of AI assisted sections; human author and reviewer verify comprehension.
- Default review rotation: Tatwik -> Farhan, Shiva -> Tatwik, Farhan -> Shiva.

## 4. Releases and Changelog
- Annotated tags on `main` at each stage completion: `stage-1` (`v0.1.0`), `stage-2` (`v0.2.0`), `stage-3` (`v0.3.0`), and final `v1.0.0`.
- All releases are documented in `CHANGELOG.md` (Keep a Changelog format).
