---
name: execute-new-notebook-code
description: |
  Execute an approved notebook implementation plan. Use when the user says
  "execute the notebook plan", "create the notebook", "add notebook code",
  "change notebook cells", or similar, once a plan already exists and has
  been approved.
---

# New Notebook Code Executor

Load the approved notebook plan from `documentation/CURRENT_PLAN.md` before
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

## Organize opening cells and verify provenance

Keep the first three code cells separate:
1. Environment/setup: locate the checkout, configure `sys.path`, and verify
   that the imported project package resolves inside that checkout or worktree.
2. Imports: third-party packages and project APIs.
3. Run variables: paths, experiments, markers, and thresholds.

4. Keep validation, data loading, and computation in later cells.
5. Stay silent when the provenance check passes; on failure, raise a clear
   error. Treat provenance as an executable contract, not a source-only check.

## Keep scope and hand off

1. Keep notebook, helper-code, and documentation changes within the plan.
2. Use `apply_patch` for repository files.
3. Check notebook structure and source-level invariants only.
4. Do not claim the notebook passes before `/validate-notebook` completes.
5. Require a fresh Run All with no cell errors to call the notebook passing.
