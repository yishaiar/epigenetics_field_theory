---
name: execute-new-feature
description: |
  Execute an approved feature implementation plan. Use when the user says
  "execute the plan", "start implementing", "go ahead", "build it", or
  similar, once a plan already exists and has been approved.
---

# New Feature Executor

Load the approved plan from `.agents/memory/CURRENT_PLAN.md` before doing
anything else. If it doesn't exist, stop and ask the user to run
`/plan-new-feature` first — don't improvise a plan from conversation
context alone, unless the user has explicitly said to proceed without
one (e.g. "skip the plan file, just go with what we discussed").

Implement the approved plan in this order, across every file it touches —
not file by file, but phase by phase across the whole feature:

1. **Define types first** — type hints, dataclasses, or Pydantic models
   (for request/response schemas) across every file in the plan, before
   writing any logic
2. **Write the logic** — implement the functions, methods, or services
   according to the plan (respecting the plan's dependency order, such as
   the layered pipeline sequence)
3. **Add error handling** — never leave happy-path-only code; catch
   specific exceptions, never a bare `except`
4. **Write tests** — invoke `/write-tests` for this phase and follow its
   guidance
5. **Update docs** — add a docstring to every new public function
6. **Verify everything passes** — invoke `/babysit-tests` across all
   changed files
7. **Diagnose against the plan** — both the implementation and its new
   tests were just written, don't default to blaming either; fix
   whichever doesn't match the plan's intent

Each `Edit`/`Write` automatically triggers `.agents/hooks/` (format/lint/
test-on-save) — fix whatever they surface before moving on.

## Rules

- Never write a function longer than 40 lines — split if needed
- Type hints required on every function signature
- Every async function must handle exceptions explicitly
- Follow the approved plan's file list and order — don't improvise scope beyond it
