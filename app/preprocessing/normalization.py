"""Normalize pooled CyTOF data one source CSV at a time.

Flow, following the normalization cell in ``main1.ipynb``:

1. ``normalize_pooled_dataframe`` receives the pooled dataframe and groups
   rows by their originating ``path``.
2. For each source file, ``_select_normalization_markers`` selects numeric
   columns, excluding controls and metadata.
3. ``normalize_sample`` builds ``CytofTransformConfig`` for that source with
   the source normalization settings.
4. ``normalize_sample`` passes a copy of the group and its config to
   ``cytof_transform_global``, then returns the transformed dataframe and
   selected marker names.
5. ``normalize_pooled_dataframe`` concatenates the transformed groups in
   their original row order and returns the complete dataframe plus the union
   of selected marker names.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from app.config.config import CONTROL_MARKERS, METADATA_COLUMNS


def _select_normalization_markers(
    data: pd.DataFrame,
    control_markers: list[str],
    skip_columns: list[str],
) -> list[str]:
    """Select every numeric column except controls and metadata."""
    excluded = set(METADATA_COLUMNS).union(skip_columns, control_markers)
    return [
        column
        for column in data.columns
        if column not in excluded
        and pd.Series(pd.to_numeric(data[column], errors="coerce")).notna().any()
    ]


def normalize_sample(
    data: pd.DataFrame,
    config_factory: Callable[..., object] | None = None,
    transform: Callable[[pd.DataFrame, object], object] | None = None,
    control_markers: list[str] = CONTROL_MARKERS,
    source: Path | None = None,
    skip_columns: list[str] = METADATA_COLUMNS,
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize a sample or pooled table while preserving cell identity and metadata.

    Args:
        data: Sample or pooled table containing cell IDs and source metadata.
        config_factory: Optional constructor for the normalization config.
        transform: Optional normalization function accepting a table and config.
        control_markers: Required control columns used by normalization.
        source: Optional source path included in input validation errors.
        skip_columns: Columns that must not be normalized.

    Returns:
        The normalized table and the marker columns actually normalized.

    Raises:
        ValueError: If cell identity, required controls, or marker availability
            do not meet the normalization contract.
    """
    missing_controls = [marker for marker in control_markers if marker not in data]
    if missing_controls:
        raise ValueError(f"Missing control markers in file:\n{source}\n{missing_controls}")
    markers = _select_normalization_markers(data, control_markers, skip_columns)
    if not markers:
        raise ValueError(f"No markers to normalize in file: {source}")

    if config_factory is None or transform is None:
        from cytof_helper.cytof_transform import (  # type: ignore[reportMissingImports]
            CytofTransformConfig,
            cytof_transform_global,
        )

        config_factory = config_factory or CytofTransformConfig
        transform = transform or cytof_transform_global
    config = config_factory(
        control_markers=control_markers,
        markers_to_correct=markers,
        use_compartments=False,
        n_pcs_for_T=1,
        anchor_to_median=True,
        zscore=False,
    )
    result = transform(data.copy(), config)
    if isinstance(result, pd.DataFrame):
        normalized = result.copy()
    else:
        corrected = getattr(result, "corrected", None)
        if not isinstance(corrected, pd.DataFrame):
            raise TypeError(
                "Unexpected output from cytof_transform_global. "
                "Expected result.corrected or a pandas DataFrame."
            )
        normalized = corrected.copy()

    return normalized, markers


def normalize_pooled_dataframe(
    df: pd.DataFrame,
    skip_columns: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize each sample CSV independently in the pooled table.

    Args:
        df: Pooled table with experiment, sample, and GFP-group metadata.
        skip_columns: Columns to preserve without normalization.

    Returns:
        The complete normalized pooled table and marker names selected across
        input sample files.
    """
    if df.empty:
        raise ValueError("Pooled normalization requires at least one cell")
    if "path" in df:
        group_columns = ["path"]
    elif "source_file" in df:
        group_columns = ["source_file"]
    else:
        group_columns = ["experiment", "sample_name", "gfp_group"]
        missing_columns = [column for column in group_columns if column not in df]
        if missing_columns:
            raise ValueError(
                f"Pooled normalization requires sample grouping columns: {missing_columns}"
            )
    if df[group_columns].isna().to_numpy().any():
        raise ValueError("Pooled normalization grouping columns must not contain nulls")
    normalized_groups = []
    normalized_columns = []
    grouping: str | list[str] = group_columns[0] if len(group_columns) == 1 else group_columns
    for _, source_data in df.groupby(grouping, sort=False, dropna=False):
        normalized, markers = normalize_sample(source_data, skip_columns=skip_columns)
        normalized.index = source_data.index
        normalized_groups.append(normalized)
        normalized_columns.extend(marker for marker in markers if marker not in normalized_columns)
    return pd.concat(normalized_groups).sort_index(), normalized_columns


def process_normalization_files(
    files_dir: Path,
    output_dir: Path,
    config_factory: Callable[..., object] | None = None,
    transform: Callable[[pd.DataFrame, object], object] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize corrected CSV files and save results with summary tables.

    Args:
        files_dir: Root containing corrected ``*_ARCSINH_5.csv`` files.
        output_dir: Directory for normalized files and CSV summaries.
        config_factory: Optional normalization config constructor.
        transform: Optional normalization function.

    Returns:
        The per-file normalization summary and input marker table.

    Raises:
        FileNotFoundError: If no corrected input files are found.
    """
    files = sorted(files_dir.rglob("*_ARCSINH_5.csv"))
    if not files:
        raise FileNotFoundError(f"No files found in: {files_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    input_rows = []
    summary_rows = []
    for file in files:
        data = pd.read_csv(file, low_memory=False)
        missing_controls = [marker for marker in CONTROL_MARKERS if marker not in data]
        if missing_controls:
            raise ValueError(f"Missing control markers in file:\n{file}\n{missing_controls}")
        markers = _select_normalization_markers(data, CONTROL_MARKERS, METADATA_COLUMNS)
        first = data.iloc[0]
        group = "GFP_high" if "GFP_high" in str(file) else "GFP_low"
        input_rows.append(
            {
                "experiment": first["experiment"],
                "condition": first["condition"],
                "sample_name": first["sample_name"],
                "gfp_group": group,
                "input_file": str(file),
                "control_markers": " | ".join(CONTROL_MARKERS),
                "n_markers_to_correct": len(markers),
                "markers_to_correct": " | ".join(markers),
            }
        )
        normalized, corrected_markers = normalize_sample(
            data,
            config_factory=config_factory,
            transform=transform,
            source=file,
        )
        target = output_dir / file.relative_to(files_dir)
        target = target.with_name(target.name.replace("_ARCSINH_5.csv", "_NORMALIZED.csv"))
        target.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(target, index=False)
        summary_rows.append(
            {
                "experiment": first["experiment"],
                "condition": first["condition"],
                "sample_name": first["sample_name"],
                "gfp_group": group,
                "input_arcsinh_file": str(file),
                "output_normalized_file": str(target),
                "control_markers": " | ".join(CONTROL_MARKERS),
                "n_cells": len(data),
                "n_markers_corrected": len(corrected_markers),
                "markers_corrected": " | ".join(corrected_markers),
            }
        )
    summary = pd.DataFrame(summary_rows)
    input_table = pd.DataFrame(input_rows)
    summary.to_csv(output_dir / "NORMALIZED_summary.csv", index=False)
    input_table.to_csv(output_dir / "NORMALIZATION_input_table.csv", index=False)
    return summary, input_table
