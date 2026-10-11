---
name: refactor
description: |
  Refactor existing code for readability, maintainability, or
  performance. Use when the user asks to refactor, clean up,
  simplify, or improve existing code without changing behavior.
---

# Safe Refactor Guide

## Golden Rule
Refactoring must not change observable behavior. If tests break, stop.

## Preserve the Current Version
Before editing, inspect the current file and treat its contents, including
manual user edits, as authoritative. Never replace newer changes with an older
version recalled from memory or conversation. Change user-edited code when the
request requires it; if that intent is unclear, ask before replacing it.

## Process
1. **Understand before touching** — read the full function/module first
2. **Identify the smell** — name the specific problem:
   - Too long / does too many things
   - Duplicated logic
   - Unclear naming
   - Deeply nested conditionals
   - Magic numbers or strings
3. **Apply one change at a time** — don't combine multiple refactors
4. **Run tests after each change** — not just at the end
5. **Rename with intent** — new names should make comments unnecessary

## Common Patterns
- Long function → extract smaller, named functions
- Repeated code → extract to a shared utility
- Nested ifs → early returns (guard clauses)
- Magic values → named constants
- Complex condition → extract to a well-named boolean variable

## Do Not
- Change behavior as part of a refactor
- Add new features during a refactor session
- Refactor files unrelated to the task
