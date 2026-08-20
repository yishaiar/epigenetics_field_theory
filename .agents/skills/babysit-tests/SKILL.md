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

- `<dir>/<module>.py` → `<dir>/tests/test_<module>.py` — tests live in a
  sibling `tests/` folder at the same directory level, not literally next to
  the file (e.g. `data_cleaning/data_cleaning.py` →
  `data_cleaning/tests/test_data_cleaning.py`, `shared/utils/names.py` →
  `shared/utils/tests/test_names.py`)
- Model version dirs (`models/<type>/v<version>/`) → `models/<type>/v<version>/tests/test_model.py`
- `config.py` has no dedicated test file — grep for tests that exercise
  whichever `Config` attribute changed instead

If a changed file has no test, skip it — don't run unrelated tests.
Determine which app each test belongs to by taking the directory name
directly under `apps/` (or `shared` if under `shared/`).

## Step 3 — Run only the relevant tests

Run each test file individually:

```bash
uv run pytest <path/to/test_file.py> -v
```

Never run the whole app's suite (`uv run pytest apps/<app>`) unless explicitly asked.

## Step 4 — Diagnose and fix failures

Read each failure and categorize it:

### Auto-fix and re-run

- **Stale mock fixture** — `MockModelLoader` (`tests/mock_model_management.py`) has no spec for a newly referenced model; add it via `build_default_in_memory_models()` or the relevant mock model dir.
- **Stale fixture data** — a new field was added to `Config.TEST_PROPERTIES`/a test DataFrame; add it to the test's input with a sensible value.
- **Lint error surfaced by ruff** — run `uv run ruff check --fix <file>` for auto-fixable categories, then re-run.
- **Missing mock/patch target** — a new dependency or call was added; find how similar dependencies are mocked in the same test file and follow the exact same `unittest.mock.patch` pattern.

### Read source before fixing

- **Assertion value mismatch** — logic changed. Read the source (e.g. `feature_generation.py`/`inference.py`) to confirm the new correct value before updating the test — don't just mirror whatever pytest's failure output says.
- **DataFrame/Series comparison mismatch** — read the transformation logic to confirm expected dtype/index/column ordering before adjusting `pd.testing.assert_frame_equal`/`assert_series_equal` calls.

### Stop and report

- **Real logic regression** — the test is correct and the source is wrong. Report the suspected cause and stop.
- **Infrastructure failure** — a DB/S3 connection error, missing model file, or a dependent service not running. Report and suggest checking the dev environment.
- **More than 5 files need changes** — scope is too broad. Summarize and ask the user how to proceed.

## Step 5 — Loop

After each fix, re-run only that test file. Once all targeted tests pass, report what was fixed and what (if anything) still needs attention.

## Rules

- Never update a test to hide a real bug — if source is wrong, say so
- Never run the full suite — always target a specific test file
- Always read the source before changing an assertion value
- Do not commit anything — leave that to the user (use `/commit-workflow` when ready)
