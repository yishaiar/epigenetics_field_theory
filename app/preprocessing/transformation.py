"""Marker arcsinh transformation extracted from main1.ipynb cell 23."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.metadata import METADATA_EXCLUSION_COLUMNS

METADATA_COLUMNS = METADATA_EXCLUSION_COLUMNS
CSV_INDEX_ARTIFACT_COLUMNS = ("Unnamed: 0",)


def arcsinh_transform(
    data: pd.DataFrame, metadata_columns: list[str] | None = None
) -> tuple[pd.DataFrame, list[str]]:
    """Apply ``arcsinh(value / 5)`` to numeric marker columns.

    Args:
        data: Table containing unique ``cell_id`` values and marker columns.
        metadata_columns: Columns to preserve without transforming. Defaults
            to the project metadata exclusion list.

    Returns:
        A transformed copy of the table and the marker columns transformed.

    Raises:
        ValueError: If ``cell_id`` is absent or contains duplicate values.
    """
    if "cell_id" not in data.columns:
        raise ValueError("cell_id column missing")
    if not data["cell_id"].is_unique:
        raise ValueError("cell_id is not unique")
    excluded = METADATA_COLUMNS if metadata_columns is None else metadata_columns
    index_artifacts = [column for column in data.columns if column in CSV_INDEX_ARTIFACT_COLUMNS]
    transformed = data.drop(columns=index_artifacts).copy()
    marker_columns = [column for column in transformed.columns if column not in excluded]
    transformed_columns = []
    for column in marker_columns:
        numeric = pd.Series(
            pd.to_numeric(pd.Series(transformed[column]), errors="coerce"), dtype=float
        )
        if numeric.notna().sum() == 0:
            continue
        transformed[column] = np.arcsinh(numeric / 5)
        transformed_columns.append(column)
    return transformed, transformed_columns


def process_arcsinh_files(gated_dir: Path, output_dir: Path) -> pd.DataFrame:
    """Transform gated CSV files and preserve their relative directory layout.

    Args:
        gated_dir: Root containing ``*_GATED.csv`` files.
        output_dir: Destination root for transformed files and the summary CSV.

    Returns:
        A summary table of input files, output files, and transformed columns.

    Raises:
        FileNotFoundError: If the input directory or matching files are absent.
    """
    if not gated_dir.exists():
        raise FileNotFoundError(f"GATED folder not found: {gated_dir}")
    files = sorted(gated_dir.rglob("*_GATED.csv"))
    if not files:
        raise FileNotFoundError(f"No gated CSV files found in: {gated_dir}")
    rows = []
    for csv_file in files:
        data = pd.read_csv(csv_file, low_memory=False)
        transformed, columns = arcsinh_transform(data)
        relative = csv_file.relative_to(gated_dir)
        target = (output_dir / relative).with_name(
            relative.name.replace("_GATED.csv", "_ARCSINH_5.csv")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        transformed.to_csv(target, index=False)
        rows.append(
            {
                "input_gated_file": str(csv_file),
                "output_arcsinh_file": str(target),
                "n_cells": len(data),
                "n_columns_total": data.shape[1],
                "n_marker_columns_transformed": len(columns),
                "transformed_columns": " | ".join(columns),
            }
        )
    summary = pd.DataFrame(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "ARCSINH_5_summary.csv", index=False)
    return summary
