"""ArcSinh transformation of marker data."""

import numpy as np
import pandas as pd

from app.config.config import METADATA_COLUMNS


def arcsinh_transform(
    data: pd.DataFrame, skip_columns: list[str] | None = None
) -> tuple[pd.DataFrame, list[str]]:
    """Apply ``arcsinh(value / 5)`` to nonmetadata columns with numeric data.

    Args:
        data: Pooled table containing metadata and marker columns.
        skip_columns: Columns to preserve without transforming. Defaults to
            the project metadata exclusion list.

    Returns:
        A transformed copy and the marker columns that were transformed.

    """
    excluded = set(METADATA_COLUMNS)
    if skip_columns is not None:
        excluded.update(skip_columns)
    transformed = data.copy()
    transformed_columns = []
    for column in transformed.columns:
        if column in excluded:
            continue
        numeric = pd.Series(
            pd.to_numeric(transformed[column], errors="coerce"), index=transformed.index
        )
        if not numeric.notna().any():
            continue
        transformed[column] = np.arcsinh(numeric.astype(float) / 5)
        transformed_columns.append(column)
    return transformed, transformed_columns
