"""Per-file CyTOF normalization extracted from main1.ipynb cell 28."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pandas as pd

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


def col_has_real_data(series: pd.Series) -> bool:
    """Return the source helper's test for at least one numeric nonmissing value."""
    numeric: Any = pd.to_numeric(series, errors="coerce")
    return numeric.notna().sum() > 0


def get_normalization_result(result: object) -> pd.DataFrame:
    """Extract `.corrected` or a direct DataFrame as in source cell 28."""
    if hasattr(result, "corrected"):
        return getattr(result, "corrected").copy()
    if isinstance(result, pd.DataFrame):
        return result.copy()
    raise TypeError(
        "Unexpected output from cytof_transform_global. "
        "Expected result.corrected or a pandas DataFrame."
    )


def normalize_sample(
    data: pd.DataFrame,
    config_factory: Callable[..., object] | None = None,
    transform: Callable[[pd.DataFrame, object], object] | None = None,
    control_markers: list[str] = CONTROL_MARKERS,
    normalization_markers: list[str] = NORMALIZATION_MARKERS,
    source: Path | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize one file using the exact per-sample cell-28 settings."""
    if "cell_id" not in data.columns:
        raise ValueError(f"cell_id column missing in file: {source}")
    if not data["cell_id"].is_unique:
        raise ValueError(f"cell_id is not unique in file: {source}")
    _require_controls(data.columns, control_markers, source)
    markers = [
        marker
        for marker in normalization_markers
        if marker in data.columns
        and marker not in control_markers
        and col_has_real_data(cast(pd.Series, data[marker]))
    ]
    if not markers:
        raise ValueError(f"No markers to normalize in file: {source}")
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
    return get_normalization_result(result), markers


def process_normalization_files(
    corrected_dir: Path,
    output_dir: Path,
    config_factory: Callable[..., object] | None = None,
    transform: Callable[[pd.DataFrame, object], object] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reload, normalize, and export every file as the cell-28 workflow does."""
    files = sorted(corrected_dir.rglob("*_ARCSINH_5.csv"))
    if not files:
        raise FileNotFoundError(f"No ARCSINH_5 files found in: {corrected_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    input_rows = [_normalization_input_row(file) for file in files]
    input_table = pd.DataFrame(input_rows)
    summary_rows = []
    for file in files:
        summary_rows.append(
            _normalize_file(file, corrected_dir, output_dir, config_factory, transform)
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "NORMALIZED_summary.csv", index=False)
    input_table.to_csv(output_dir / "NORMALIZATION_input_table.csv", index=False)
    return summary, input_table


def _normalization_input_row(file: Path) -> dict[str, object]:
    """Build the source notebook's pre-normalization input record."""
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
    """Normalize and save one corrected CSV, returning its source summary row."""
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
    """Import the same optional helper names as cell 28 when not injected."""
    if config_factory is not None and transform is not None:
        return config_factory, transform
    from cytof_transform import CytofTransformConfig, cytof_transform_global  # type: ignore[reportMissingImports]

    return config_factory or CytofTransformConfig, transform or cytof_transform_global
