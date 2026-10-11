---
name: commit-workflow
description: |
  Run pre-commit checks and format the commit message using Conventional
  Commits. Use when the user mentions committing, git message, or asks to
  format/write a commit message, or says they're ready to commit.
---

# Commit Workflow

Before committing, always format, test, and lint every changed file. Only commit if all three pass.

## Pre-Commit Checks

### 1. Determine affected workspace members

Map each changed file to its app by taking the directory name directly
under `scbatch/` (e.g. `scbatch/pp/...` → `pp`).

### 2. Run tests for changed files only

For each changed file that has a corresponding `test_*.py`, run it individually:

```bash
uv run pytest <path/to/test_file.py>
```

Never run the whole suite unless explicitly asked; run the owning workspace
member's local tests.

### 3. Run the formatter for changed files

```bash
uv run ruff format scbatch/<member>
```

Safe to auto-apply — purely cosmetic, same as the `format-on-save.sh` hook. Re-stage any files it touches.

### 4. Run lint for affected workspace members

```bash
uv run ruff check scbatch/<member>
```

Run lint for every member or directory that has at least one changed file.

### 5. Fix before committing

- **Lint errors** — fix them. Common: unused imports, trailing whitespace, missing type hints.
- **Test failures** — follow the `babysit-tests` skill rules: fix if it's a stale assertion or missing mock fixture; stop and report if it's a real regression.
- Do not commit if any check is still failing.

---

## Commit Format

`<type>(<scope>): <description>`

### Rules

- Imperative mood, lowercase, no period, max 72 chars
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Breaking changes: add `!` after type/scope

### Branch Naming

`<type>/<short-description>` — lowercase, hyphen-separated

- `feature/rare-name-threshold`
- `fix/dob-match-window`
- `chore/update-dependencies`

### Examples

Input: "added a threshold for rare name matching"
Output: `feat(matching): add rare-name threshold`

Input: "fixed the dob mismatch bug"
Output: `fix(matching): resolve dob mismatch on username-derived dates`

---

Always append to the commit message:

```
Co-Authored-By: Codex GPT-5.6 Terra <noreply@openai.com>
```

(Update this line if the model in use changes — it should match whatever Codex model is actually generating the commit.)
