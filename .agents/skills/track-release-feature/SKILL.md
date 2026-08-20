---
name: track-release-feature
description: |
  Add a feature, fix, or improvement to the release tracking log.
  Use when the user wants to log something for an upcoming release, says "add to release notes",
  "track this for the release", "log this feature", or "save this for the release".
---

# Release Feature Tracker

Invocation: `/track-release-feature`

## Process

1. **Determine which release this targets**

   - Run `git tag --sort=-v:refname | head -1` to find the latest released version (e.g. `v1.5`)
   - Determine if this is a **hotfix** for an already-released version, or **ongoing work** for the next release:
     - Hotfix → confirm which released version it patches, then target its next patch number (`v1.5` → `v1.5.1`; if `v1.5.1` already exists, bump to `v1.5.2`)
     - Ongoing work → target the shared **`releases/unreleased.md`** pool
   - If unclear, ask the user

2. **Determine what to log — auto-infer, skip questions when possible**

   - Use the description the user provided; if none, infer from the conversation, branch name, or recent code changes
   - Auto-detect the category based on the content:
     - New Feature → adds capability that didn't exist before
     - Improvement → enhancements to existing backend/logic/tests
     - Bug Fix → anything described as a fix or correction
     - ML → model, scoring, or ML pipeline changes
   - Write the description in release-note style — clear, past-tense, user-facing language
   - Only ask if the description or category is genuinely ambiguous and cannot be inferred

3. **Append to the tracking file** at `releases/{version}.md` (repo root — e.g. `releases/unreleased.md` or `releases/v1.5.1.md`)

   - If the file does **not** exist, create it with this skeleton first:

     ```markdown
     # Release {version} — Tracking Log

     ## New Features

     ## Improvements

     ## Bug Fixes
     ```

   - Append the new item as a bullet under the correct section header
   - Never overwrite or reorder existing entries

4. **Confirm to the user** what was saved and to which release file

## Rules

- Keep each entry concise but complete — descriptions will be expanded when generating release notes
- If a feature spans multiple categories, log it in the primary category and note the secondary one in parentheses
- Never delete or modify entries that already exist in the file
- **Run this once the PR has actually merged** — not on every commit, not at PR-open time. Invoke right after `gh pr merge` succeeds, even if the user didn't explicitly ask.
