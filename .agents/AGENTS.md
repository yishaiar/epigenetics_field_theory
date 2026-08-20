# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

> **Always read `.agents/memory/MEMORY.md` at the start of every session** — it contains persistent project knowledge and gotchas.

## Overview

Yishai's **ML** repository — Python monorepo for data enrichment and scoring. Multiple apps under `apps/`, plus shared utilities in `shared/`.

## Commands

### Installation

```bash
uv sync   # installs the full uv workspace (all apps + dev tools)
```

### Testing

```bash
# Single app
uv run pytest apps/<app>
uv run pytest shared

# Run a specific test file (example)
uv run pytest apps/<app>/tests/test_preprocessing.py

# set PYTHONPATH explicitly (CI sets this automatically)
PYTHONPATH=$(pwd) uv run pytest apps/<app>
```

### Linting & Formatting

```bash

ruff format apps/<app> # Auto-format
ruff format apps/<app> --check # Check formatting
ruff check apps/<app> # Lint
ruff check # Lint All projects
```

### Environment

All apps reads from `apps/dotenv/params.env` file (via `python-dotenv`) — never commit these.

## Code Standards

- **Pydantic for all API schemas** — use Pydantic v2 models for request/response validation. No raw dicts at API boundaries.
- **No bare `except`** — always catch specific exceptions.
- **Type hints required** — all function signatures must have type hints.
- **ruff must pass** — run `ruff check apps/<app>` before any PR (`pylint` is available but unconfigured — ruff is primary).

### Engineering Principles

- Favor modular, reusable design — structure so new features need minimal changes to existing code.
- Self-check new code for any repeated multi-line logic before presenting it as done, and extract it into a helper. Doesn't apply to intentionally-parallel sibling functions (rule below).
- Keep parallel/sibling entities (e.g. similar model types, similar endpoints) structurally consistent, even if it costs some duplication.
- Prioritize readability and explicitness over cleverness or overly condensed abstractions.
- Write tests for new code and update the corresponding tests whenever you change existing behavior (see `.agents/hooks/test-on-spec-save.sh`, which runs `uv run pytest` automatically on `test_*.py` saves).


## Skills

Skills are defined in `.agents/skills/<name>/SKILL.md`. Automatically invoke the relevant skill based on the current context — do not wait for the user to explicitly call it.

Skills below cover structured processes (debugging, reviewing, testing, etc.); the per-file execution-validation loop is separately driven by `.agents/hooks/` (wired in `.codex/hooks.json`):

| Event | Script | Purpose |
| --- | --- | --- |
| `PreToolUse` (Bash) | `secret-scan-on-commit.sh` | No-op unless the command is `git commit`; blocks the commit if the staged diff looks like a hardcoded credential |
| `PostToolUse` (Edit\|Write) | `format-on-save.sh` | Auto-formats the saved file (`ruff format`) |
| `PostToolUse` (Edit\|Write) | `lint-on-save.sh` | Lints the saved file (`ruff check`) |
| `PostToolUse` (Edit\|Write) | `pyright-on-save.sh` | Type-checks the saved file (basedpyright) |
| `PostToolUse` (Edit\|Write) | `debug-artifact-on-save.sh` | Flags leftover `pdb`/`breakpoint()` calls |
| `PostToolUse` (Edit\|Write) | `test-on-spec-save.sh` | Runs `uv run pytest` whenever a `test_*.py` file is saved |
| `Stop` | `notify-on-stop.sh` | Fires a macOS notification naming the repo/worktree/branch when a session ends |
| `UserPromptSubmit` | `cold-eye-reminder.sh` | Re-injects the `cold-eye` objectivity reminder (external bar, counter-case, no fabrication, sycophancy reset) into every prompt |
| `UserPromptSubmit` | `plan-mode-enforce-skill.sh` | When `permission_mode` is `plan`, nudges Codex to load `plan-new-feature`'s instructions instead of following native Plan Mode generically |

| Trigger                                                  | Skill          |
| --------------------------------------------------------- | -------------- |
| *(always active — reinforced every turn via the `UserPromptSubmit` hook, not a phrase trigger)* | `cold-eye` |
| User reports a bug, error, or something "isn't working"   | `/debugger`    |
| User asks to implement, create, add, or build a new feature | `/plan-new-feature` |
| User says "start implementing" or "execute the plan" (once a plan already exists and is approved) | `/execute-new-feature` |
| User asks to refactor, clean up, simplify, or improve code | `/refactor`    |
| User asks to review, check, or audit code, or is preparing a PR | `/code-reviewer` |
| User asks to write/format a commit message, or is ready to commit | `/commit-workflow` |
| User says "rebase", "fix conflicts", or "my branch is behind" | `/rebase-and-resolve` |
| User asks to add tests or increase coverage | `/write-tests` |
| User asks to create, open, or draft a PR | `/create-pr` |
| User asks what code does or wants to understand it before changing it | `/explain-code` |
| After resolving a bug, learning a pattern, or making an architectural decision | `/update-memory` |
| User wants to log/track a feature, fix, or improvement for a release | `/track-release-feature` |
| User says "run tests", "fix tests", "make tests green", or after code changes | `/babysit-tests` |
| User shares or pastes a skill file, asks if it's safe, or wants to audit one | `/skill-scanner` |
| User finishes or pauses work on a complex feature and wants to save context | `/save-feature-context` |

### New-Feature Flow

For implementing a new feature end-to-end, skills chain in this order. These
are three **separate pipelines** — `/clear` between each step for fresh
context; every step reads from persisted state, not conversation history.

1. `/plan-new-feature` — plans in Plan Mode; on approval, saves the plan to
   `.agents/memory/CURRENT_PLAN.md` (gitignored, local scratch state) and
   suggests switching permission mode (Shift+Tab → `acceptEdits`/
   `bypassPermissions`) for a hands-off execution phase

   — *clear the conversation here* —

2. `/execute-new-feature` — loads the approved plan from
   `.agents/memory/CURRENT_PLAN.md`, then implements it across all its files,
   phase by phase (types → logic → error handling → tests → docs), hook-validated as it goes;
   invokes `/write-tests`, and finally invokes `/babysit-tests` to verify everything passes

   — *clear the conversation here* —

3. `/create-pr` — `/commit-workflow` if needed, invokes `/rebase-and-resolve`
   (no-op if already up to date), runs `/code-reviewer` against the
   resulting diff, drafts the PR description, and merge (once asked to)
   then invokes `/track-release-feature`

Push and opening the PR always require your explicit go-ahead — that gate
isn't skill-controlled.

### Rebase Conflict Patterns

- **`apps/<app>/config.py`** — field mapping / threshold / model-registry entries. Both
  branches typically add new entries; this file is additive by nature, so keep entries from
  both sides rather than dropping either.
- **Layered pipeline files** (`data_cleaning/`, `feature_generation.py`, `inference.py`) — per
  this file's own layered-signal convention (`Config → DataCleaning → FeatureGeneration →
  Inference`), check after merging that all four layers are still updated in sync for *each*
  signal; keeping both signals' `Config` entries but only one's `Inference` wiring is a bug.
- **`shared/utils/`** — cross-app helper conflicts. Keep both sides' additions; check no app's
  import of an existing helper was accidentally dropped.
- **`models/<identity|activity|social_media>/` version pins** — don't blindly take either side.
  Which model version is "current" for a signal is a product decision, not a syntactic merge;
  surface it to the user rather than guessing.
- **`pyproject.toml`** — merge changed entries (`[tool.ruff]`, `dev-dependencies`, etc.) from
  both sides rather than picking one wholesale. `uv.lock` is gitignored here (not tracked), so
  there's no lockfile to merge — just run `uv sync` after to regenerate it locally.

### Future Skills (not yet built)

- **`/generate-release-notes`** — expand the raw bullets accumulated by
  `/track-release-feature` (in `releases/{version}.md`) into polished,
  final release notes at actual release-cut time. No source to port from
  (referenced in `CLAUDE_shani.md`'s table but has no matching command
  file there either).
- **`/personal:update-work-log`** — from `CLAUDE_shani.md` line 163
  ("add to work log", "log this", "update the work log", "add to T5T").
  Personal tooling in the original (namespaced `personal:`), not something
  this repo's `.agents/` ever had a source file for. Only relevant if a
  repo-level equivalent is wanted later.

## Architecture

### Architecture blueprint

This repository's ML layout is a concrete implementation of the reusable
[stages pipeline architecture](.agents/memory/architecture_layered_pipeline.md).

When creating a new app, read that file before choosing its structure - it defines the development flow: start with `config.py`, use `pipeline.py` only
as the orchestrator, model each processing stage independently, and introduce
Level 3 dispatch or composed helpers only when the stage's complexity requires it.
Use the stage names and domain concepts that fit the app. In this repository,
those stages are currently preprocessing and inference.

### Apps Structure

Each app under `apps/` is a standalone service:

```
apps/<app>/
├── AGENTS.md           # for data flow, field-mapping conventions, non-obvious domain semantics (data item statuses, etc), and the layered process for adding a new feature.
├── pipeline.py           # Orchestrator: End-to-end orchestrator loads data & preprocessing → runs inference
├── preprocess.py # data loading, features preprocessing
├── inference.py          # Loads and scores with ML models (rbm, xgboost)
├── config.py             # Field name mappings, model name/version paths, thresholds
├── preprocess/        # Per-field feature preprocess (names, locations)
└── models/               # Training code and model versions artifacts
    ├── rbm/         # rbm model versions (v0_x_x/)
    ├── xgboost/         # xgboost model versions

```



### Shared Libraries (`shared/`)

- **`shared/datasets/`** — Cross-app data loading
- **`shared/utils/`** — Cross-app utilities (model management/versioning)
- **`shared/metrics/`** — Model evaluation metrics
