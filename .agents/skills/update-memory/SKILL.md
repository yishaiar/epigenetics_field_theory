---
name: update-memory
description: |
  Update the project memory file with new insights, patterns, or decisions
  discovered during the current session. Use after resolving a non-obvious bug,
  learning a project-specific pattern, or making an architectural decision.
---

# Memory Updater

Memory file location: `.agents/memory/MEMORY.md` (tracked in the repo)

## When to Update

- A non-obvious bug was found and fixed — add it to Gotchas & Insights
- A recurring pattern was identified — add it to Important File Patterns or Code Conventions
- An architectural decision was made — add it to Key Architecture
- A new module or service was added — update the relevant section
- A previous memory entry turned out to be wrong — correct or remove it
- A topic has grown too large for a bullet (a full feature's data flow, a complex decision tree) — write it up in its own file under `.agents/memory/<topic>.md` and add a one-line pointer under Feature Memory Files instead of inlining it

## Process

1. **Read the current MEMORY.md** before writing anything — including the Feature Memory Files index, to check whether a deep-dive file already covers this topic
2. **Find the right section** — update existing entries rather than duplicating
3. **Be concise** — one bullet per insight, plain English; if it needs more than a few lines, it belongs in its own `.agents/memory/<topic>.md` file instead
4. **Remove outdated entries** — stale memory is worse than no memory

## Rules

- Never exceed 200 lines total in `MEMORY.md` itself — promote long entries to `.agents/memory/<topic>.md` and link them instead of letting the flat file grow
- No session-specific details (current task, temporary state)
- No speculation — only confirmed, stable knowledge
- Prefer updating an existing bullet (or an existing `.agents/memory/` file) over adding a new one
- Scope is the product codebase only — patterns, architecture, and gotchas
- Never record changes to agent tooling (skills, hooks, instruction files, or settings)
