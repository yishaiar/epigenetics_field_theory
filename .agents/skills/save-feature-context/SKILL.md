---
name: save-feature-context
description: |
  Save the current feature's context as a reusable skill file.
  Use when finishing or pausing work on a complex feature so the
  knowledge is available in future sessions without re-exploring.
---

# Feature Context Saver

Invocation: `/save-feature-context <feature-name>`
Example: `/save-feature-context rare-name-threshold`

## Process

1. **Collect context from the current session**
   - Which files were created or modified (with paths)
   - Key architectural or design decisions made, and why
   - Patterns and conventions specific to this feature
   - Known gotchas, edge cases, or tricky parts
   - Any TODOs or next steps left open

2. **Write the skill file**
   Create `.agents/skills/<feature-name>/SKILL.md` with this structure:

   ```markdown
   ---
   name: <feature-name>
   description: |
     Context and conventions for the <feature-name> feature.
     Auto-load when the user resumes work on <feature-name>.
   ---

   # <Feature Name> — Saved Context

   ## Overview
   <What this feature does and why it exists>

   ## Key Files
   - `path/to/file.py` — <role>
   - `path/to/other.py` — <role>

   ## Architecture Decisions
   - <Decision>: <Reason>

   ## Patterns & Conventions
   - <Pattern used in this feature>

   ## Gotchas
   - <Known issue or tricky part>

   ## Next Steps / TODOs
   - [ ] <Open task>
   ```

3. **Register it in `.agents/AGENTS.md`**
   Add a row to the Skills table:
   ```
   | User resumes work on <feature-name> | `/<feature-name>` |
   ```

## Rules
- Only include information confirmed during this session — no guesses
- Keep each section concise; bullet points over prose
- If the feature name is not provided as an argument, ask for it before proceeding
