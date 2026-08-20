---
name: create-pr
description: |
  Write a pull request description for the current branch changes.
  Use when the user asks to create, open, or draft a PR, or says
  "I'm ready to merge" or "write the PR description".
---

# PR Description Writer

## Process
1. **Commit first** — if anything's uncommitted, invoke `commit-workflow`
2. **Sync if needed** — invoke `rebase-and-resolve` (target: the repo's default branch, `<base>` below); it reports and stops on its own if already up to date
3. **Code review** — invoke `code-reviewer` on the diff vs base; fix any Must-fix/Should-fix findings in a follow-up commit
4. **Review the diff** — `git diff origin/<base>...HEAD` (every commit since diverging, not just the latest)
5. **Identify the type of change**:
   - `feat` — new functionality
   - `fix` — bug fix
   - `refactor` — no behavior change
   - `chore` — tooling, deps, config
6. **Write the description** using the structure below
7. **Push and open the PR** — only with the user's explicit go-ahead;
   never push or run `gh pr create` on your own initiative
8. **Merge, when asked** — only run `gh pr merge` with explicit go-ahead;
   right after it succeeds, invoke `track-release-feature`

## PR Structure

### Title
`<type>(<scope>): <short description>` — max 72 chars, same as Conventional Commits

### Description Template
```
## What
<1–3 sentences describing what changed and why>

## Changes
- <file or module>: <what changed>
- <file or module>: <what changed>

## How to Test
1. <Step to reproduce or verify the feature/fix>
2. <Expected result>

## Notes
<Breaking changes, migrations needed, env vars added, or leave empty>
```

## Rules
- "What" explains the problem being solved, not just what files changed
- "Changes" is one line per file/module, single clause — no multi-sentence
  bullets, the diff itself has the detail
- "How to Test" must be specific enough for a reviewer who wasn't involved
- Flag breaking changes explicitly — schema changes, API contract changes, env var additions
- If a migration is needed, say so in Notes
- Keep it factual — no filler phrases like "various improvements"
