---
name: plan-new-feature
description: |
  Plan the implementation of a new feature or module before writing any code.
  Use when the user says "implement", "create", "add a feature", or "build"
  followed by a new piece of functionality.
---

# New Feature Planner

Use Codex's Plan Mode for this — enter it (`EnterPlanMode`) if not
already active.

## Planning Process

1. **Clarify before planning** — if the requirement is ambiguous, ask 1–2
   focused questions before drafting anything
2. **Check module-specific conventions** — read the root `AGENTS.md` and the
   touched `scbatch/<module>/` package before planning
3. **Enumerate the touchpoints** — which files/layers change, in what
   order, and what new types/schemas are needed
4. **Enumerate the tests needed** — at least one happy path + one failure
   case per new function

## Requesting Approval

Write the plan file per the above, then call `ExitPlanMode`. Do not make
any code changes, and do not proceed to `/execute-new-feature`, until the
plan is explicitly approved.

## After Approval

Save the approved plan to `.agents/memory/CURRENT_PLAN.md` (overwrite if
it already exists) so `/execute-new-feature` can load it.

Tell the user:

> Plan approved. For a hands-off execution phase, consider switching your
> permission mode via Shift+Tab (`acceptEdits` or `bypassPermissions`) —
> otherwise each file edit/command will still pause for individual approval.
