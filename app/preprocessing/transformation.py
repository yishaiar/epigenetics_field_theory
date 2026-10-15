"""Marker arcsinh transformation extracted from main1.ipynb cell 23."""

from pathlib import Path

import numpy as np
import pandas as pd


METADATA_COLUMNS = [
    "cell_id",
    "experiment",
    "sample_name",
    "condition",
    "replicate",
    "source_file",
    "source_path",
    "raw_row_id",
    "Line",
    "batch",
]
CSV_INDEX_ARTIFACT_COLUMNS = ("Unnamed: 0",)


def arcsinh_transform(
    data: pd.DataFrame, metadata_columns: list[str] | None = None
) -> tuple[pd.DataFrame, list[str]]:
    """Apply source cell 23's arcsinh(x/5) loop to numeric nonmetadata columns."""
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
        numeric = pd.to_numeric(transformed[column], errors="coerce")
        if numeric.notna().sum() == 0:
            continue
        transformed[column] = np.arcsinh(numeric / 5)
        transformed_columns.append(column)
    return transformed, transformed_columns


def process_arcsinh_files(gated_dir: Path, output_dir: Path) -> pd.DataFrame:
    """Reload sorted gated CSVs, preserve relative paths, and save index-free outputs."""
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
