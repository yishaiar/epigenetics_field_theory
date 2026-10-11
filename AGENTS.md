# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

**At the start of every session, always read and follow:**

1. `.agents/AGENTS.md` — Shared agent instructions, workflows, skills, and policies.
2. `.agents/memory/MEMORY.md` — Persistent project knowledge, context, and known issues.

Both files are mandatory and must be read before performing any task.


## Overview

`scbatch` is a scientific Python monorepo for the batch-effect comparison paper and its package implementation. It has one published distribution, `scbatch`; `scbatch/pp`, `scbatch/pl`, `scbatch/datasets`, and `scbatch/tl` are internal UV workspace ownership boundaries, not separately installable applications.

## Architecture

### Scientific package architecture

This repository is a Scanpy-style scientific package, not an application monorepo. Its UV workspace members are ownership boundaries for scientific code.

```text
AnnData input
    |
    +-- scbatch.datasets  reproducible inputs and fixtures
    +-- scbatch.pp        validation, transformations, correction
    +-- scbatch.tl        graph, embedding, clustering, downstream analysis
    +-- scbatch.pl        diagnostics and publication-ready plots
```

`pp` may write documented corrected or intermediate layers and method provenance to `adata.uns`. `tl` consumes documented representations and writes graphs or embeddings to standard AnnData slots. `pl` reads results without mutation unless its public API explicitly states otherwise. `datasets` supplies deterministic, documented test and example inputs.

Use `AnnData` for data-bearing APIs and Pydantic v2 for public request, configuration, and result schemas. Validate metadata keys, shapes, and axis alignment before mutation.

### Package structure

```text
scbatch/
├── pp/        # preprocessing and batch correction
├── pl/        # diagnostics and result plotting
├── datasets/  # reproducible and synthetic AnnData datasets
└── tl/        # graph, embedding, clustering, and downstream tools
```

When creating a new scientific capability, first define the public schema and AnnData mutation contract. Then implement it in the owning member, add local tests for normal, invalid, empty, sparse, and dense inputs as applicable, and export only stable public functions through the corresponding namespace.

The generic staged-pipeline blueprint is preserved in `.agents/memory/architecture_layered_pipeline.md` for future repositories that actually have applications. Do not force that application architecture onto `scbatch`.

## Tests

Tests live beside the owning component at `scbatch/<module>/tests/test_<component>.py`. Keep setup local to the test class, use `unittest.TestCase` for synchronous code and `unittest.IsolatedAsyncioTestCase` for asynchronous code, and use `unittest.mock` for external services. Test normal behavior, invalid metadata, empty inputs, sparse and dense inputs where supported, and Pydantic validation when a public schema is introduced.

Jupyter is optional support for notebooks and exploratory verification. The `start-jupyter-server` skill checks connectivity only and must not substitute for package tests.

