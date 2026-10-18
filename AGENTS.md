# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

**At the start of every session, always read and follow:**

1. `.agents/AGENTS.md` — Shared agent instructions, workflows, skills, and policies.
2. `documentation/MEMORY.md` — Persistent project knowledge, context, and known issues.

Both files are mandatory and must be read before performing any task.


## Overview

This repository contains the `epigenetics-field-theory` Python distribution and a staged CyTOF analysis workflow. The installable Python package is `app`. Reusable code is organized by workflow stage, and the numbered notebooks in `notebooks/` orchestrate those stages.

## Architecture

### CyTOF workflow

The current workflow passes tabular data and CSV artifacts between stages:

```text
input CSV files
    |
    +-- app.preprocessing  loading, gating, filtering, and arcsinh transformation
    +-- app.harmonization  normalization, balancing, batch correction, and scaling
    +-- app.annotation     UMAP, clustering, labels, and staining plots
    +-- app.analysis       biological comparisons and distribution analyses
```

The notebooks `01_preprocessing.ipynb`, `02_harmonization.ipynb`, `03_annotation.ipynb`, and `04_analysis.ipynb` correspond to those stages. Keep file boundaries, output paths, and table schemas explicit when passing data between stages. Workflow CSVs should be written without an implicit index unless a specific artifact contract requires one.

Current workflow functions primarily accept and return pandas DataFrames or filesystem paths. Raw input CSVs live in the local, Git-ignored `raw_data/` directory; generated workflow outputs remain under `results/experiment_<ddmmyy>/`. Validate required columns before processing, preserve row and marker alignment, and keep public function signatures typed. Use Pydantic v2 when introducing public request, configuration, or result schemas.

### Source structure

```text
app/
├── preprocessing/  # raw loading, filtering, gating, and transformation
├── harmonization/  # normalization, balancing, correction, and scaling
├── annotation/     # embeddings, clustering, labeling, and plots
└── analysis/       # biological comparisons and KDE analyses
notebooks/          # one notebook per workflow stage
raw_data/           # local, Git-ignored raw CSV inputs
results/            # generated, experiment-scoped outputs
```

Keep a new function in the stage that owns its behavior. Export stable functions through that stage's `app/<stage>/__init__.py` and add tests beside the implementation. Preserve `main1.ipynb` as the source reference; do not modify or delete it.

The project distribution metadata and runtime/development dependencies live in the root `pyproject.toml`. Development dependencies are exposed through its `dev` extra.

## Tests

Tests live beside the owning component at `app/<stage>/tests/test_<component>.py`. Keep setup local to the test class, use `unittest.TestCase` for synchronous code and `unittest.IsolatedAsyncioTestCase` for asynchronous code, and use `unittest.mock` for external services. Test normal behavior, invalid columns and values, empty inputs, and CSV/file boundary behavior as applicable.

Jupyter notebooks are part of the staged research workflow. Notebook validation is separate from package tests; a server connection or static source inspection does not prove that a notebook executed successfully.

