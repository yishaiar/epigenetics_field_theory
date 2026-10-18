"""Per-experiment z-scoring and pooled output from cells 33 and 36."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.metadata import METADATA_EXCLUSION_COLUMNS

METADATA_COLS = METADATA_EXCLUSION_COLUMNS
ALL_MARKERS = [
    "ACSS2",
    "CD109",
    "CD133",
    "CD24",
    "CD44",
    "CD45",
    "CXCR4",
    "DNA",
    "E-cadherin",
    "EZH2",
    "EpCAM",
    "GAL4",
    "GATA6",
    "GFP",
    "H2A",
    "H2AK119ub",
    "H2BK5ac",
    "H3",
    "H3.3",
    "H3K27ac",
    "H3K27me2",
    "H3K27me3",
    "H3K36me2",
    "H3K36me3",
    "H3K4me1",
    "H3K4me2",
    "H3K4me3",
    "H3K9ac",
    "H3K9me2",
    "H3K9me3",
    "H3S28p",
    "H4",
    "H4K16ac",
    "H4K20me3",
    "KI67",
    "KRT17",
    "KRT5",
    "MBD",
    "MHC-II",
    "Pan-KRT",
    "S100A4",
    "SLC44A4",
    "TSPAN8",
    "Vimentin",
    "pH2A.X",
    "pRb",
]


def zscore_markers(
    data: pd.DataFrame,
    all_markers: list[str] = ALL_MARKERS,
    metadata_columns: list[str] = METADATA_COLS,
) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    """Z-score usable marker columns while preserving metadata columns.

    Population standard deviation (``ddof=0``) is used. Usable zero-variance
    markers are set to zero.

    Args:
        data: Input table to copy and scale.
        all_markers: Candidate marker names eligible for scaling.
        metadata_columns: Columns excluded from marker scaling.

    Returns:
        The scaled table, scaled marker names, skipped nonnumeric markers, and
        zero-variance markers.
    """
    df_z = data.copy()
    marker_cols = [
        column
        for column in data.columns
        if column in all_markers and column not in metadata_columns
    ]
    valid_marker_cols = []
    skipped_marker_cols = []
    for column in marker_cols:
        values = _numeric_series(data, column)
        if values.notna().sum() == 0:
            skipped_marker_cols.append(column)
        else:
            valid_marker_cols.append(column)

    zero_variance_markers = []
    for column in valid_marker_cols:
        values = _numeric_series(data, column)
        mean = values.mean()
        standard_deviation = values.std(ddof=0)
        if pd.isna(standard_deviation) or standard_deviation == 0:
            df_z[column] = 0
            zero_variance_markers.append(column)
        else:
            df_z[column] = (values - mean) / standard_deviation
    return df_z, valid_marker_cols, skipped_marker_cols, zero_variance_markers


def process_scaling_files(
    balanced_dir: Path, output_dir: Path, experiments: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Scale available balanced experiment files and save diagnostic tables.

    Args:
        balanced_dir: Directory containing balanced experiment CSV files.
        output_dir: Destination for scaled files and proof tables.
        experiments: Experiment names to process, in output order.

    Returns:
        The per-experiment summary and per-marker scaling proof tables.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    marker_summary_rows = []
    for experiment in experiments:
        input_file = balanced_dir / f"{experiment}_GFP_high_BALANCED.csv"
        if not input_file.exists():
            continue
        summary, proofs = _process_one_experiment(input_file, output_dir, experiment)
        summary_rows.append(summary)
        marker_summary_rows.extend(proofs)

    zscore_summary = pd.DataFrame(summary_rows)
    marker_zscore_proof = pd.DataFrame(marker_summary_rows)
    zscore_summary.to_csv(output_dir / "GFP_high_ZSCORE_summary_per_experiment.csv", index=False)
    marker_zscore_proof.to_csv(
        output_dir / "GFP_high_ZSCORE_marker_proof_per_experiment.csv", index=False
    )
    return zscore_summary, marker_zscore_proof


def _numeric_series(data: pd.DataFrame, column: str) -> Any:
    """Expose Pandas numeric conversion to the type checker as its runtime Series."""
    return pd.to_numeric(data[column], errors="coerce")


def _process_one_experiment(
    input_file: Path, output_dir: Path, experiment: str
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Scale one experiment's cells and assemble its diagnostic records.

    Args:
        input_file: Balanced CSV for the experiment.
        output_dir: Destination for the scaled CSV.
        experiment: Experiment identifier used in the output name and records.

    Returns:
        The experiment summary record and its per-marker proof records.
    """
    data = pd.read_csv(input_file, low_memory=False)
    zscored, valid, skipped, zero_variance = zscore_markers(data)
    output_file = output_dir / f"{experiment}_GFP_high_BALANCED_ZSCORED.csv"
    zscored.to_csv(output_file, index=False)
    proofs = _marker_proof_rows(experiment, zscored, valid, zero_variance)
    diagnostics = _zscore_diagnostics(zscored, valid, zero_variance)
    return (
        {
            "experiment": experiment,
            "input_file": str(input_file),
            "output_file": str(output_file),
            "n_cells": len(zscored),
            "n_markers_zscored": len(valid),
            "markers_zscored": ", ".join(valid),
            "markers_skipped_no_numeric_data": ", ".join(skipped),
            "zero_variance_markers_set_to_0": ", ".join(zero_variance),
            **diagnostics,
        },
        proofs,
    )


def _marker_proof_rows(
    experiment: str,
    zscored: pd.DataFrame,
    valid: list[str],
    zero_variance: list[str],
) -> list[dict[str, object]]:
    """Build post-scaling statistics for each usable marker.

    Args:
        experiment: Experiment identifier recorded in each row.
        zscored: Table containing the scaled marker values.
        valid: Marker columns included in scaling.
        zero_variance: Scaled markers set to zero because their input variance
            was zero.

    Returns:
        One record per marker with its post-scaling mean, standard deviation,
        nonmissing count, and zero-variance status.
    """
    rows = []
    for marker in valid:
        values = _numeric_series(zscored, marker)
        rows.append(
            {
                "experiment": experiment,
                "marker": marker,
                "mean_after_zscore": values.mean(),
                "sd_after_zscore_ddof0": values.std(ddof=0),
                "n_non_na": values.notna().sum(),
                "zero_variance_marker": marker in zero_variance,
            }
        )
    return rows


def _zscore_diagnostics(
    zscored: pd.DataFrame, valid: list[str], zero_variance: list[str]
) -> dict[str, object]:
    """Measure whether scaled markers meet the readiness tolerances.

    Args:
        zscored: Table containing the scaled marker values.
        valid: Marker columns included in scaling.
        zero_variance: Markers set to zero because their input variance was zero.

    Returns:
        Maximum absolute mean and standard-deviation deviations, plus the
        resulting ``ready_for_umap`` flag.
    """
    max_abs_mean = max(abs(_numeric_series(zscored, marker).mean()) for marker in valid)
    nonconstant = [marker for marker in valid if marker not in zero_variance]
    max_abs_sd_minus_1 = (
        max(abs(_numeric_series(zscored, marker).std(ddof=0) - 1) for marker in nonconstant)
        if nonconstant
        else np.nan
    )
    ready = (
        len(valid) > 0
        and max_abs_mean < 1e-10
        and (pd.isna(max_abs_sd_minus_1) or max_abs_sd_minus_1 < 1e-10)
    )
    return {
        "max_abs_mean_after_zscore": max_abs_mean,
        "max_abs_sd_minus_1_after_zscore": max_abs_sd_minus_1,
        "ready_for_umap": ready,
    }


def combine_scaled_experiments(zscored_dir: Path, experiments: list[str]) -> pd.DataFrame:
    """Concatenate scaled experiment tables and save the pooled CSV.

    Args:
        zscored_dir: Directory containing scaled experiment CSV files.
        experiments: Experiment names to concatenate, in desired row order.

    Returns:
        The combined table, with its index reset.
    """
    frames = []
    for experiment in experiments:
        input_file = zscored_dir / f"{experiment}_GFP_high_BALANCED_ZSCORED.csv"
        frames.append(pd.read_csv(input_file, low_memory=False).copy())
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(zscored_dir / "all_GFP_high_BALANCED_ZSCORED.csv", index=False)
    return combined
