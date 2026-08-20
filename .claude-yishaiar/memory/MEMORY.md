# Project Memory — ML

> Read this at the start of every session.

## Project Overview

Heka's data enrichment and contactability scoring platform. Python monorepo:
FastAPI services (`contactability`, `translation`, `libpostal_parser`,
`mlflow`, `waterfall`), shared utilities in `shared/`.

## Key Architecture

- `contactability` is the primary service — a layered pipeline (data load →
  clean → feature-generate → infer), not a generic CRUD API
- MongoDB Atlas is the primary datastore across apps; Postgres/RDS exists
  only as MLflow's internal backend store — unrelated to app data
- `uv` workspace at repo root manages dependencies; `ruff` is the linter/formatter

## Important File Patterns

- `apps/contactability/config.py` is the single source of truth for field
  mappings, model names, and thresholds — read before touching feature logic
- Contactability signals are threaded through 4 layers in order: `Config` →
  `DataCleaning` → `FeatureGeneration` → `Inference` (see
  `apps/contactability/CLAUDE.md`)

## Code Conventions

- Pydantic v2 for all API schemas — no raw dicts at boundaries
- Type hints required on all function signatures; no bare `except`
- Tests: `unittest.TestCase` / `unittest.IsolatedAsyncioTestCase`, no
  `conftest.py`, `MockModelLoader` for model-dependent tests

## Feature Memory Files

- [Layered Orchestrator Pattern](architecture_layered_pipeline.md) —
  reusable pipeline architecture (orchestrator inheritance + stage
  composition), generalized beyond this repo
