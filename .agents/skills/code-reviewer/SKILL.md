---
name: code-reviewer
description: |
  Review code for bugs, security issues, performance problems,
  and style violations. Use when the user asks to review,
  check, or audit code, or before creating a PR.
---

# Code Reviewer

When reviewing code, always cover these areas in order:

## 1. Correctness

- Does the logic match the intended behavior?
- Are edge cases handled (nulls, empty arrays, boundary values)?
- Are errors caught and handled properly?

## 2. Security

- No hardcoded secrets, API keys, or credentials
- User inputs are validated and sanitized
- No SQL injection, XSS, or insecure direct object references

## 3. Performance

- No unnecessary loops inside loops
- No unnecessary repeated matrix conversion, copying, or materialization
- Large data sets are paginated or streamed

## 4. Module-Specific Consistency

- If the change touches a `scbatch` member, verify its AnnData mutation
  contract, public namespace export, and component-local tests are updated in
  sync.
- Check that anything the AGENTS.md flags as "must be registered" (added
  to a list/config, not just implemented) actually is — an
  implemented-but-unregistered step will silently never run.

## 5. Style & Conventions

- Follows project conventions from AGENTS.md
- Variable and function names are clear and descriptive
- No dead code or commented-out blocks

## Output Format

Summarize findings as:

- 🔴 **Must fix** — bugs or security issues
- 🟡 **Should fix** — performance or maintainability
- 🟢 **Suggestion** — style or minor improvements
