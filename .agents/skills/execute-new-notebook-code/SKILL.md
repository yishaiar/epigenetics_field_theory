---
name: execute-new-notebook-code
description: |
  Execute an approved notebook implementation plan. Use when the user says
  "execute the notebook plan", "create the notebook", "add notebook code",
  "change notebook cells", or similar, once a plan already exists and has
  been approved.
---

# New Notebook Code Executor

Load the approved notebook plan from `.agents/memory/CURRENT_PLAN.md` before
doing anything else. If it is absent or does not describe a notebook, ask the
user to run `/plan-new-feature` first. Do not infer a plan from conversation
context unless the user explicitly authorizes proceeding without one. Do not
add work beyond the approved notebook scope.

Do not invoke this skill because a repository contains a notebook or because a
code change may affect a notebook. It requires an explicit user request for
notebook work or an explicitly approved notebook plan.

## Create or update

1. Read the notebook's imported public APIs and local repository instructions.
2. Create or update a valid nbformat 4 notebook with clear Markdown context.
3. Use deterministic code cells and minimal realistic inputs.
4. Use public APIs and state unsupported behavior beside the relevant cell.
5. Add type hints to every function implemented in notebook code cells.
6. Do not present a scaffold as a completed implementation.

## Add runtime provenance

1. Make the first executable cell a runtime-provenance cell.
2. Print the kernel executable and current working directory.
3. Print the imported package path when local package code is imported.
4. In a worktree, fail when that path is outside the intended worktree.
5. Treat this as an executable contract, not a source-only check.

## Keep scope and hand off

1. Keep notebook, helper-code, and documentation changes within the plan.
2. Use `apply_patch` for repository files.
3. Check notebook structure and source-level invariants only.
4. Do not claim the notebook passes before `/validate-notebook` completes.
5. Require a fresh Run All with no cell errors to call the notebook passing.
