---
name: debugger
description: |
  Systematically debug an issue, error, or unexpected behavior.
  Use when the user reports a bug, shows an error message, or
  says something "isn't working" or "is broken".
---

# Systematic Debugger

Never guess. Always follow this process:

1. **Restate the problem** — describe what's happening vs. what's expected
2. **Identify the scope** — is this a logic bug, a data issue, an env problem,
   or an integration failure?
3. **Trace the execution path** — follow the code from the entry point to
   where it breaks
4. **Form a hypothesis** — state one specific suspected cause before changing
   anything
5. **Verify, don't assume** — add a log or read the relevant file to confirm
   the hypothesis before applying a fix
6. **Fix minimally** — make the smallest change that resolves the issue
7. **Confirm the fix** — re-run the failing case and check for regressions

## Rules
- Never change more than one thing at a time when debugging
- If the root cause is unclear after 3 steps, ask the user for more context
  rather than guessing
