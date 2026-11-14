"""Marker arcsinh transformation extracted from main1.ipynb cell 23."""

from pathlib import Path

import pandas as pd

from app.config.config import METADATA_COLUMNS
from app.preprocessing.arcsinh_transform import arcsinh_transform


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
        transformed, columns = arcsinh_transform(data, skip_columns=METADATA_COLUMNS)
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
