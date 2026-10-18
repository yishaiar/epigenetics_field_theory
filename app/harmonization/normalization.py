"""Per-file CyTOF normalization extracted from main1.ipynb cell 28."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from app.metadata import METADATA_EXCLUSION_COLUMNS

CONTROL_MARKERS = ["H3.3", "H4"]
NORMALIZATION_MARKERS = [
    "ACSS2",
    "EZH2",
    "GAL4",
    "GATA6",
    "H2AK119ub",
    "H2BK5ac",
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
    "H4K16ac",
    "H4K20me3",
    "KI67",
    "KRT17",
    "KRT5",
    "MBD",
    "Pan-KRT",
    "S100A4",
    "Vimentin",
    "pH2A.X",
    "pRb",
]


def col_has_real_data(series: Any) -> bool:
    """Check whether a series contains any value convertible to a number.

    Args:
        series: Values to coerce to numeric form.

    Returns:
        True if at least one coerced value is nonmissing.
    """
    numeric: Any = pd.to_numeric(series, errors="coerce")
    return numeric.notna().sum() > 0


def get_normalization_result(result: object) -> pd.DataFrame:
    """Return a copy of the corrected DataFrame from a transform result.

    Args:
        result: A DataFrame or an object exposing a ``corrected`` DataFrame.

    Returns:
        A copy of the corrected DataFrame.

    Raises:
        TypeError: If the result contains no DataFrame in either supported form.
    """
    if hasattr(result, "corrected"):
        return getattr(result, "corrected").copy()
    if isinstance(result, pd.DataFrame):
        return result.copy()
    raise TypeError(
        "Unexpected output from cytof_transform_global. "
        "Expected result.corrected or a pandas DataFrame."
    )


def _select_normalization_markers(
    data: pd.DataFrame,
    control_markers: list[str],
    normalization_markers: list[str],
    source: Path | None,
) -> list[str]:
    """Validate sample identifiers and select usable biological markers.

    Args:
        data: Sample table to validate.
        control_markers: Required control columns.
        normalization_markers: Candidate columns eligible for normalization.
        source: Optional path included in validation errors.

    Returns:
        Available, numeric markers selected for normalization.

    Raises:
        ValueError: If cell identity, controls, or marker availability is invalid.
    """
    if "cell_id" not in data.columns:
        raise ValueError(f"cell_id column missing in file: {source}")
    if not data["cell_id"].is_unique:
        raise ValueError(f"cell_id is not unique in file: {source}")
    _require_controls(data.columns, control_markers, source)
    markers = [
        marker
        for marker in normalization_markers
        if marker in data.columns
        and marker not in METADATA_EXCLUSION_COLUMNS
        and marker not in control_markers
        and col_has_real_data(data[marker])
    ]
    if not markers:
        raise ValueError(f"No markers to normalize in file: {source}")
    return markers


def _restore_annotation_columns(data: pd.DataFrame, normalized: pd.DataFrame) -> pd.DataFrame:
    """Check normalized row identity and restore annotation provenance columns.

    Args:
        data: Original sample table.
        normalized: Table returned by the normalization implementation.

    Returns:
        The normalized table with original annotation columns restored.

    Raises:
        ValueError: If normalization changes the cell count, identity, or order.
    """
    if len(normalized) != len(data):
        raise ValueError("Normalization changed the number of cells")
    if "cell_id" not in normalized or not data["cell_id"].reset_index(drop=True).equals(
        normalized["cell_id"].reset_index(drop=True)
    ):
        raise ValueError("Normalization changed cell identity or order")
    for column in ("cell_uid", "labels", "leiden_cluster", "annotation_present"):
        if column in data.columns:
            normalized[column] = data[column].to_numpy()
    return normalized


def normalize_sample(
    data: pd.DataFrame,
    config_factory: Callable[..., object] | None = None,
    transform: Callable[[pd.DataFrame, object], object] | None = None,
    control_markers: list[str] = CONTROL_MARKERS,
    normalization_markers: list[str] = NORMALIZATION_MARKERS,
    source: Path | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize one sample while preserving cell identity and annotation data.

    Args:
        data: Sample table containing unique ``cell_id`` values.
        config_factory: Optional constructor for the normalization config.
        transform: Optional normalization function accepting a table and config.
        control_markers: Required control columns used by normalization.
        normalization_markers: Candidate columns to normalize.
        source: Optional source path included in input validation errors.

    Returns:
        The normalized table and the marker columns actually normalized.

    Raises:
        ValueError: If cell identity, required controls, or marker availability
            do not meet the normalization contract.
    """
    markers = _select_normalization_markers(data, control_markers, normalization_markers, source)

    # Configure and run the injected or optional normalization implementation.
    config_type, transform_fn = _resolve_cytof_dependencies(config_factory, transform)
    config = config_type(
        control_markers=control_markers,
        markers_to_correct=markers,
        use_compartments=False,
        n_pcs_for_T=1,
        anchor_to_median=True,
        zscore=False,
    )
    result = transform_fn(data.copy(), config)
    normalized = get_normalization_result(result)

    normalized = _restore_annotation_columns(data, normalized)
    return normalized, markers


def process_normalization_files(
    files_dir: Path,
    output_dir: Path,
    config_factory: Callable[..., object] | None = None,
    transform: Callable[[pd.DataFrame, object], object] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize corrected CSV files and save results with summary tables.

    Args:
        corrected_dir: Root containing corrected ``*_ARCSINH_5.csv`` files.
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
    input_rows = [_normalization_input_row(file) for file in files]
    input_table = pd.DataFrame(input_rows)
    summary_rows = []
    for file in files:
        summary_rows.append(_normalize_file(file, files_dir, output_dir, config_factory, transform))
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "NORMALIZED_summary.csv", index=False)
    input_table.to_csv(output_dir / "NORMALIZATION_input_table.csv", index=False)
    return summary, input_table


def _normalization_input_row(file: Path) -> dict[str, object]:
    """Summarize sample metadata and candidate markers from an input CSV.

    Args:
        file: Corrected input CSV to inspect.

    Returns:
        A record of sample metadata, controls, and candidate normalization
        markers.

    Raises:
        ValueError: If required control markers are missing.
    """
    header = pd.read_csv(file, nrows=0).columns.tolist()
    first = pd.read_csv(file, nrows=1, low_memory=False)
    _require_controls(header, CONTROL_MARKERS, file)
    markers = [marker for marker in NORMALIZATION_MARKERS if marker in header]
    return {
        "experiment": first["experiment"].iloc[0],
        "condition": first["condition"].iloc[0],
        "sample_name": first["sample_name"].iloc[0],
        "gfp_group": "GFP_high" if "GFP_high" in str(file) else "GFP_low",
        "input_file": str(file),
        "control_markers": " | ".join(CONTROL_MARKERS),
        "n_markers_to_correct": len(markers),
        "markers_to_correct": " | ".join(markers),
    }


def _normalize_file(
    file: Path,
    corrected_dir: Path,
    output_dir: Path,
    config_factory: Callable[..., object] | None,
    transform: Callable[[pd.DataFrame, object], object] | None,
) -> dict[str, object]:
    """Normalize one corrected CSV and save it at the matching output path.

    Args:
        file: Corrected input CSV to normalize.
        corrected_dir: Root used to preserve the input's relative path.
        output_dir: Root for normalized files.
        config_factory: Optional normalization config constructor.
        transform: Optional normalization function.

    Returns:
        A summary record with source metadata, output path, and correction
        counts.
    """
    data = pd.read_csv(file, low_memory=False)
    normalized, markers = normalize_sample(
        data, config_factory=config_factory, transform=transform, source=file
    )
    target = output_dir / file.relative_to(corrected_dir)
    target = target.with_name(target.name.replace("_ARCSINH_5.csv", "_NORMALIZED.csv"))
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(target, index=False)
    return {
        "experiment": data["experiment"].iloc[0],
        "condition": data["condition"].iloc[0],
        "sample_name": data["sample_name"].iloc[0],
        "gfp_group": "GFP_high" if "GFP_high" in str(file) else "GFP_low",
        "input_arcsinh_file": str(file),
        "output_normalized_file": str(target),
        "control_markers": " | ".join(CONTROL_MARKERS),
        "n_cells": len(data),
        "n_markers_corrected": len(markers),
        "markers_corrected": " | ".join(markers),
    }


def _require_controls(columns: Any, controls: list[str], source: Path | None) -> None:
    """Raise the cell-28 error for missing normalization control markers."""
    missing = [marker for marker in controls if marker not in columns]
    if missing:
        raise ValueError(f"Missing control markers in file:\n{source}\n{missing}")


def _resolve_cytof_dependencies(
    config_factory: Callable[..., object] | None,
    transform: Callable[[pd.DataFrame, object], object] | None,
) -> tuple[Callable[..., object], Callable[[pd.DataFrame, object], object]]:
    """Resolve injected normalization dependencies or import their defaults.

    Args:
        config_factory: Optional normalization configuration constructor.
        transform: Optional normalization callable.

    Returns:
        The configuration constructor and normalization callable.
    """
    if config_factory is not None and transform is not None:
        return config_factory, transform
    from cytof_helper.cytof_transform import (  # type: ignore[reportMissingImports]
        CytofTransformConfig,
        cytof_transform_global,
    )

    return config_factory or CytofTransformConfig, transform or cytof_transform_global
