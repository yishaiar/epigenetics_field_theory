---
name: rebase-and-resolve
description: >
  Rebases the current branch onto a target branch and resolves any merge conflicts. Use
  when the user says "rebase", "fix conflicts", "resolve merge conflicts",
  "my branch is behind", "rebase and resolve", or when another skill needs the branch to be
  up to date before proceeding.
---

# Rebase and Conflict Resolver

You rebase the current branch onto this repo's default branch — detected via `gh repo view`
in Phase 1, and resolve any conflicts that arise. The goal is a clean, linear
history with no broken code — not just a technically conflict-free tree.

---

## Phase 1: Assess the Situation

Before running anything, determine the base branch and understand what you're working with:

```bash
# Determine the base branch once -- never hardcode a name. Use this exact
# value (written below as <base_branch>) for every git command in this skill.
gh repo view --json defaultBranchRef -q .defaultBranchRef.name

# Current branch and its upstream
git branch --show-current
git status

# How far behind are we?
git fetch origin
git log --oneline HEAD..origin/<base_branch> | wc -l   # commits in <base_branch> not in this branch
git log --oneline origin/<base_branch>..HEAD | wc -l   # commits in this branch not in <base_branch>

# What files overlap between the two sides?
git diff --name-only HEAD...origin/<base_branch>
```

Report to the user:

- Current branch name
- How many commits this branch is ahead / <base_branch> is ahead
- Which files have diverged (potential conflict zones)

If the branch is already up to date (`0` commits behind), report that and stop — no rebase needed.

---

## Phase 2: Rebase

```bash
git rebase origin/<base_branch>
```

Three outcomes:

**A — Clean rebase (no conflicts)**
Rebase completes. Skip to Phase 4.

**B — Conflicts**
Git stops mid-rebase and reports conflicting files. Proceed to Phase 3.

**C — Rebase error (untracked files, dirty working tree, etc.)**
Report the exact error to the user and ask how to proceed. Do not attempt to force through it.

---

## Phase 3: Resolve Conflicts

For each conflicting file:

### Step 1 — Understand both sides before deciding

Read the conflicting file **with the Read tool** (not `cat`) to see the full conflict markers in
context.

Then inspect both sides of the conflict. The exact syntax depends on whether you're mid-rebase
or just inspecting a branch:

**Mid-rebase (`git rebase` has stopped on a conflict):**

```bash
# The incoming commit being applied (our changes from the feature branch)
git show REBASE_HEAD -- <file>

# What the base side (<base_branch>) introduced since our branch diverged
git log --oneline ORIG_HEAD..HEAD -- <file>
git show HEAD -- <file>
```

`REBASE_HEAD` and `ORIG_HEAD` only exist while a rebase is in progress — referencing them
outside that state will fail.

**Not mid-rebase (assessing potential conflicts before running rebase):**

```bash
# What our branch changed vs <base_branch>
git diff origin/<base_branch>...HEAD -- <file>

# What <base_branch> changed since we branched
git diff HEAD...origin/<base_branch> -- <file>
```

Read both diffs in full. Never resolve a conflict by blindly picking one side.

### Step 2 — Classify the conflict

| Type                          | Description                                                 | Resolution                                                                        |
| ----------------------------- | ----------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **Independent changes**       | Both sides edited different parts of the same file          | Merge both sets of changes — keep everything                                      |
| **Same line, compatible**     | Both sides changed the same line but the intent is the same | Pick the better/more recent version, verify intent matches                        |
| **Same line, incompatible**   | Both sides changed the same logic in conflicting ways       | Understand what each side was trying to do; implement the correct combined result |
| **Deleted vs modified**       | One side deleted something the other side modified          | Decide whether the deletion or the modification should win                        |
| **Import / export conflicts** | Barrel files, index.ts exports, schema registrations        | Merge all exports — never drop either side's export                               |

### Step 3 — Check repo-specific patterns

For what conflicts actually look like in this repo — which files collide often and how to
resolve them — see `AGENTS.md`'s "Rebase Conflict Patterns" section. Do not re-encode
repo-specific patterns here; if you learn a new one, add it there instead.

### Step 4 — Resolve and verify

Edit the file to remove all `<<<<<<<`, `=======`, `>>>>>>>` markers and produce correct code.

Before moving on, show the user the conflict and how it was resolved — they need to see it to
verify the resolution is correct, not just trust that it happened. For each resolved file, report:

```
<file path>
Conflict: <what each side changed, in one line each — "ours: ...", "theirs: ..." >
Resolution: <classification from Step 2> — <what you did and why>

<the original conflict block, markers included>

→ resolved to →

<the final code that replaced it>
```

Keep this per-file — don't defer it to a single end-of-rebase summary, since the user should be
able to catch a wrong resolution before it's buried under several more commits' worth of
`git rebase --continue`.

After resolving each file, lint and format the owning `scbatch` member:

```bash
uv run ruff format scbatch/<member>
uv run ruff check scbatch/<member>
```

If the resolved file has a corresponding `test_*.py`, run it:

```bash
uv run pytest <path/to/test_file.py>
```

If there are lint errors or test failures introduced by the resolution, fix them before
continuing.

```bash
git add <resolved-file>
```

### Step 5 — Continue the rebase

After resolving all conflicts in the current commit:

```bash
git rebase --continue
```

If new conflicts appear for the next commit, repeat Step 1 through Step 5 for those files.

### Abort if needed

If a conflict is too complex to resolve safely (e.g., both sides made large structural changes to
the same module), **do not guess**. Stop and report:

```bash
git rebase --abort
```

Tell the user exactly which file and commit caused the problem and what both sides were trying to
do. Let them decide how to proceed.

---

## Phase 4: Verify the Result

After a clean rebase:

```bash
# Confirm the branch is now ahead of <base_branch> with no behind commits
git log --oneline origin/<base_branch>..HEAD
git log --oneline HEAD..origin/<base_branch>  # should be empty

# Run the full suite, not just the files touched by conflict resolution.
# Integration tests can break from changes elsewhere in the merged history.
uv run pytest
```

If tests fail after the rebase, investigate before reporting success. A clean rebase that breaks
tests is not a success.

---

## Phase 5: Report

The per-file conflict/resolution detail was already shown to the user in Step 4 as each file was
resolved — this closing summary is a short recap, not a re-listing of that detail:

```
Rebase complete.

Branch: <branch_name>
Base: origin/<base_branch>
Commits rebased: N
Conflicts resolved: M files
  - <file_1> — independent changes, merged both
  - <file_2> — import conflict, kept both exports

Tests: passed (uv run pytest)
Ready to force-push: git push --force-with-lease
```

**Do not push** unless the user explicitly asks. Always use `--force-with-lease` (never
`--force`) when pushing a rebased branch — it prevents overwriting commits you didn't see.
