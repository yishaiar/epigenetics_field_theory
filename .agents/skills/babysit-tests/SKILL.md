---
name: babysit-tests
description: |
  Run tests only for files that changed, automatically fix common failures,
  and loop until all relevant tests pass. Use when the user says "run tests",
  "fix tests", "tests are failing", "make tests green", or after making code
  changes. Never runs the full test suite — only tests tied to changed files.
---

# Babysit Tests

Find which files changed, run only their tests, fix failures, repeat until green.

Complements `.agents/hooks/test-on-spec-save.sh` (which reruns a single test
file on save) by covering every changed file at once, on demand.

## Step 1 — Find changed files

```bash
git diff --name-only HEAD
```

Also include staged files:

```bash
git diff --name-only --cached
```

## Step 2 — Map changed files to test files

For each changed `.py` file, find its corresponding test:

- `scbatch/<member>/<module>.py` →
  `scbatch/<member>/tests/test_<module>.py`

If a changed file has no test, skip it — don't run unrelated tests. Determine
the owning member from the directory directly under `scbatch/`.

## Step 3 — Run only the relevant tests

Run each test file individually:

```bash
uv run pytest <path/to/test_file.py> -v
```

Never run the whole suite unless explicitly asked; run the owning member's
test directory instead.

## Step 4 — Diagnose and fix failures

Read each failure and categorize it:

### Auto-fix and re-run

- **Stale fixture** — an AnnData fixture lacks a newly required observation, variable, layer, or `uns` entry; add a biologically sensible test value.
- **Stale fixture data** — a public schema or AnnData metadata field changed; add the required value to the local test fixture.
- **Lint error surfaced by ruff** — run `uv run ruff check --fix <file>` for auto-fixable categories, then re-run.
- **Missing mock/patch target** — a new dependency or call was added; find how similar dependencies are mocked in the same test file and follow the exact same `unittest.mock.patch` pattern.

### Read source before fixing

- **Assertion value mismatch** — logic changed. Read the scientific transformation or public API implementation to confirm the correct value before updating the test — don't just mirror whatever pytest's failure output says.
- **Matrix or metadata comparison mismatch** — read the transformation logic to confirm expected shape, dtype, AnnData alignment, and sparse or dense representation before changing an assertion.

### Stop and report

- **Real logic regression** — the test is correct and the source is wrong. Report the suspected cause and stop.
- **Infrastructure failure** — a required external dataset, file, or service is unavailable. Report and suggest checking the development environment.
- **More than 5 files need changes** — scope is too broad. Summarize and ask the user how to proceed.

## Step 5 — Loop

After each fix, re-run only that test file. Once all targeted tests pass, report what was fixed and what (if anything) still needs attention.

## Rules

- Never update a test to hide a real bug — if source is wrong, say so
- Never run the full suite — always target a specific test file
- Always read the source before changing an assertion value
- Do not commit anything — leave that to the user (use `/commit-workflow` when ready)
