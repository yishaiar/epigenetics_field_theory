# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Always read `.claude/memory/MEMORY.md` at the start of every session** — it contains persistent project knowledge and gotchas.

## Overview

Heka's **ML** repository — Python monorepo for data enrichment and contactability scoring. Five apps under `apps/`, plus shared utilities in `shared/`. The primary and most complex service is **`contactability`** (identity/activity/social-media scoring via a FastAPI ML pipeline). The other apps are supporting services: `translation`, `libpostal_parser` (address parsing), `mlflow` (experiment tracking server), and `waterfall`.

## Commands

### Installation

```bash
uv sync   # installs the full uv workspace (all apps + dev tools)
```

### Development

```bash
# Run all services via Docker
docker-compose up --build

# Run a single service via Docker
docker-compose up contactability --build

# Run contactability locally
python3 apps/contactability/main.py
```

Services & ports: `contactability` :8000, `libpostal_parser` :8002, `translation` :8004, `mlflow` :5000.

For the worktree-based local dev workflow (creating/resuming isolated Claude Code worktrees), see `documentation/developement.md`.

### Testing

```bash
# Single app
pytest apps/contactability
pytest shared

# Run a specific test file
pytest apps/contactability/tests/test_endpoints.py

# Outside Docker, set PYTHONPATH explicitly (CI sets this automatically)
PYTHONPATH=$(pwd) pytest apps/contactability
```

### Linting & Formatting

```bash

ruff format apps/contactability # Auto-format
ruff format apps/contactability --check # Check formatting
ruff check apps/contactability # Lint
ruff check # Lint All projects
```

## Architecture

### Apps Structure

Each app under `apps/` is a standalone FastAPI service. The most complex is **contactability**:

```
apps/contactability/
├── pipeline.py           # Orchestrator: loads data → generates features → runs inference
├── feature_generation.py # Automation tests (name match, DoB, location, phone type, etc.)
├── inference.py          # Loads and scores with ML models (identity, activity, social media)
├── config.py             # Field name mappings, model paths, thresholds
├── model_management.py   # Model loading/caching layer
├── endpoints.py          # FastAPI routes
├── data_cleaning/        # Per-field cleaners (names, locations)
└── models/               # Training code and model versions
    ├── identity/         # Identity model versions (v0_x_x/)
    ├── activity/         # Activity model versions
    └── social_media/identity/
```


### Apps

- **`apps/contactability`** — FastAPI service, primary app. ML pipeline for identity/activity scoring of data items (structured/unstructured). MongoDB via `motor`. S3 model storage via `boto3`/`s3fs`. Async endpoints.
- **`apps/translation`** — FastAPI translation service.
- **`apps/libpostal_parser`** — FastAPI address-parsing service (wraps libpostal), called by contactability's location cleaning.
- **`apps/mlflow`** — MLflow tracking server (backed by its own dedicated Postgres/RDS instance — unrelated to contactability's data store).
- **`apps/waterfall`** — supporting service.

### Key Modules (`apps/contactability/`)

- **`main.py`** — FastAPI entrypoint, model loading + lifespan DB init
- **`endpoints.py`** — Route definitions
- **`pipeline.py`** — End-to-end orchestrator: fetch → clean → feature-generate → infer
- **`inference.py`** — Model inference logic
- **`feature_generation.py`** — Feature engineering ("automation tests")
- **`data_cleaning/`** — Cleaning sub-modules (dob, location, name, image)
- **`models/`** — Trained model artifacts (identity, activity, social_media)
- **`db/`** — MongoDB connection pool
- **`config.py`** — Field mappings, model name/version registry, all thresholds

See `apps/contactability/CLAUDE.md` for data flow, field-mapping conventions, non-obvious domain semantics (name/location match categories, data item statuses, etc), and the layered process for adding a new signal.

### Shared Libraries (`shared/`)

- **`shared/datasets/`** — `DataItemLoader`/`LineItemLoader` for async MongoDB data access
- **`shared/utils/`** — Cross-app utilities (model management/versioning, MongoDB client lifecycle, LLM helpers)
- **`shared/metrics/`** — Model evaluation metrics

### Environment

Each app reads from its own `.env` file (via `python-dotenv`) — never commit these. Contactability's key variables: `DATABASE_URI` (MongoDB connection string), `DATABASE_PREFIX`, `LIBPOSTAL_PARSER_URL`, `TRANSLATION_URL`. MongoDB Atlas is the primary datastore across apps; Postgres/RDS is used only internally by the MLflow service for its backend store.

## Code Standards

- **Pydantic for all schemas** — use Pydantic v2 models for request/response validation. No raw dicts at API boundaries.
- **No bare `except`** — always catch specific exceptions.
- **Type hints required** — all function signatures must have type hints.
- **ruff must pass** — run `ruff check apps/contactability` before any PR (`pylint` is available but unconfigured — ruff is primary).

### Engineering Principles

- Favor modular, reusable design — structure so new features need minimal changes to existing code.
- Self-check new code for any repeated multi-line logic before presenting it as done, and extract it into a helper. Doesn't apply to intentionally-parallel sibling functions (rule below).
- Keep parallel/sibling entities (e.g. similar model types, similar endpoints) structurally consistent, even if it costs some duplication.
- Prioritize readability and explicitness over cleverness or overly condensed abstractions.
- Write tests for new code and update the corresponding tests whenever you change existing behavior (see `.claude/hooks/test-on-spec-save.sh`, which runs pytest automatically on `test_*.py` saves).

### Infrastructure

Terraform + Terraform Cloud, configs in `infra/`, targeting AWS (ECS, ALB) plus MongoDB Atlas. CI/CD via GitHub Actions + CodeBuild/CodePipeline, triggered on push/merge to `develop`, `qa`, or `master`. See `documentation/infrastructure.md` for the architecture diagram and details.

## Skills

Skills are defined in `.claude/skills/<name>/SKILL.md`. Automatically invoke the relevant skill based on the current context — do not wait for the user to explicitly call it.

Skills below cover structured processes (debugging, reviewing, testing, etc.); the per-file execution-validation loop is separately driven by `.claude/hooks/` (wired in `.claude/settings.json`):

| Event | Script | Purpose |
| --- | --- | --- |
| `PreToolUse` (Bash) | `secret-scan-on-commit.sh` | No-op unless the command is `git commit`; blocks the commit if the staged diff looks like a hardcoded credential |
| `PostToolUse` (Edit\|Write) | `format-on-save.sh` | Auto-formats the saved file (`ruff format`) |
| `PostToolUse` (Edit\|Write) | `lint-on-save.sh` | Lints the saved file (`ruff check`) |
| `PostToolUse` (Edit\|Write) | `pyright-on-save.sh` | Type-checks the saved file (basedpyright) |
| `PostToolUse` (Edit\|Write) | `debug-artifact-on-save.sh` | Flags leftover `pdb`/`breakpoint()` calls |
| `PostToolUse` (Edit\|Write) | `test-on-spec-save.sh` | Runs pytest whenever a `test_*.py` file is saved |
| `Stop` | `notify-on-stop.sh` | Fires a macOS notification naming the repo/worktree/branch when a session ends |
| `UserPromptSubmit` | `cold-eye-reminder.sh` | Re-injects the `cold-eye` objectivity reminder (external bar, counter-case, no fabrication, sycophancy reset) into every prompt |
| `UserPromptSubmit` | `plan-mode-enforce-skill.sh` | When `permission_mode` is `plan`, nudges Claude to load `plan-new-feature`'s instructions instead of following native Plan Mode generically |

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
   `.claude/memory/CURRENT_PLAN.md` (gitignored, local scratch state) and
   suggests switching permission mode (Shift+Tab → `acceptEdits`/
   `bypassPermissions`) for a hands-off execution phase

   — *clear the conversation here* —

2. `/execute-new-feature` — loads the approved plan from
   `.claude/memory/CURRENT_PLAN.md`, then implements it across all its files,
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
  this repo's `.claude/` ever had a source file for. Only relevant if a
  repo-level equivalent is wanted later.