# model
## Purpose
`model` is the repository's Python model package. It currently provides two
callable placeholders for loading and representing a model prediction.
## Implementation

`ModelPred()` is implemented in `model_pred.py` and returns `"ModelPred"`.
`Model()` is defined in both `__init__.py` and `model.py`; each imports
`ModelPred` and returns `"loaded Model"`.
## Public API

```python
from app.model import Model, ModelPred

Model()      # "loaded Model"
ModelPred()  # "ModelPred"
```
## Configuration and usage

The package is named `model`, is version `0.1.0`, requires Python 3.11 or
newer, and has no runtime dependencies.

## Development

From the repository root, run `uv sync` to install dependencies. Run
`uv run ruff format app/model`, `uv run ruff check app/model`, and
`uv run basedpyright app/model` to verify the package. There are currently no test files for this package.
