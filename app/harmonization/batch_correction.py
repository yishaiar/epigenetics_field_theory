"""SOM-OT fitting and application extracted from main1.ipynb cell 25."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from app.harmonization.marker_lists import (
    CELL_IDENTITY_MARKERS,
    EPIGENETIC_MARKERS,
)

MARKER_COLS = [
    "CD109",
    "CD24",
    "CD44",
    "CD45",
    "CXCR4",
    "E-cadherin",
    "EZH2",
    "EpCAM",
    "GAL4",
    "GATA6",
    "GFP",
    "H2AK119ub",
    "H3",
    "H3.3",
    "H3K27ac",
    "H3K27me3",
    "H3K36me2",
    "H3K36me3",
    "H3K4me1",
    "H3K4me2",
    "H3K4me3",
    "H3K9ac",
    "H3K9me2",
    "H3K9me3",
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
    "TSPAN8",
    "Vimentin",
    "pH2A.X",
    "pRb",
]
ALL_MARKER_COLS = list(dict.fromkeys(MARKER_COLS + CELL_IDENTITY_MARKERS + EPIGENETIC_MARKERS))


class BatchCorrectionModel(Protocol):
    """The transform interface used by the notebook's fitted SOM-OT model."""

    def transform(
        self, values: NDArray[np.float64], batch_labels: np.ndarray
    ) -> NDArray[np.float64]: ...


class FittableBatchCorrectionModel(BatchCorrectionModel, Protocol):
    """A source SOM-OT instance before the cell-25 fit call."""

    def fit(self, values: NDArray[np.float64], batch_labels: np.ndarray) -> object: ...


def batch_correct(
    df: pd.DataFrame,
    marker_cols_: list[str],
    batch_label: str,
    model: BatchCorrectionModel,
    invalid_markers: list[str] | None = None,
) -> pd.DataFrame:
    """Apply cell 25's `batch_correct` function, with its model made explicit."""
    df_corrected = df.copy()
    invalid_markers = [] if invalid_markers is None else invalid_markers
    df_corrected.drop(columns=invalid_markers, inplace=True, errors="ignore")
    X = _reverse_arcsinh(df_corrected, marker_cols_)
    if not np.isfinite(X).all():
        raise ValueError(f"Invalid input values for batch {batch_label}")
    X_corrected = model.transform(X, np.full(len(df_corrected), batch_label))
    if not np.isfinite(X_corrected).all():
        raise ValueError(f"Batch correction produced NaN or Inf for {batch_label}")
    df_corrected[marker_cols_] = np.arcsinh(X_corrected / 5)
    return df_corrected


def select_correction_markers(
    files: list[Path], marker_cols: list[str], all_marker_cols: list[str]
) -> tuple[list[str], list[str], list[str]]:
    """Select source-ordered valid markers shared and finite across all files."""
    if not files:
        raise FileNotFoundError("No files found for batch correction")
    shared_markers = set(all_marker_cols)
    for file in files:
        shared_markers &= set(pd.read_csv(file, nrows=0).columns)
    valid_markers = set(shared_markers)
    for file in files:
        if not valid_markers:
            break
        checked = pd.read_csv(file, usecols=cast(Any, sorted(valid_markers)), low_memory=False)
        for marker in list(valid_markers):
            numeric: Any = pd.to_numeric(checked[marker], errors="coerce")
            values = numeric.to_numpy(dtype=float)
            if not np.isfinite(values).all():
                valid_markers.remove(marker)
    invalid_markers = sorted(set(all_marker_cols) - valid_markers)
    selected_markers = [marker for marker in marker_cols if marker in valid_markers]
    if not selected_markers:
        raise ValueError("No valid markers remain for batch correction")
    return selected_markers, invalid_markers, sorted(valid_markers)


def fit_batch_correction(
    arcsinh_dir: Path,
    experiments: list[str],
    marker_cols: list[str] = MARKER_COLS,
    all_marker_cols: list[str] = ALL_MARKER_COLS,
    model_factory: Callable[..., FittableBatchCorrectionModel] | None = None,
) -> tuple[FittableBatchCorrectionModel, list[str], list[str], list[str], pd.DataFrame]:
    """Fit the source SOM-OT model from both GFP groups and source sample order."""
    files = _collect_arcsinh_files(arcsinh_dir, experiments)
    markers, invalid, valid = select_correction_markers(files, marker_cols, all_marker_cols)
    fit_df = _load_fit_frame(arcsinh_dir, experiments)
    fit_subset = _sample_fit_cells(fit_df, markers)
    factory = _resolve_somot_factory() if model_factory is None else model_factory
    model = factory(
        anchor_label=sorted(fit_df["_batch"].unique())[0],
        n_jobs=-1,
        som_verbose=True,
        pca_components=None,
        transform_kind="arcsinh",
        n_landmarks_total=1200,
        som_grid=(8, 8),
        q_grid=np.array([0, 1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99, 100]),
        alpha_ot=0.7,
        alpha_warp=None,
    )
    values = _reverse_arcsinh(fit_subset, markers)
    if not np.isfinite(values).all():
        raise ValueError("X_fit contains NaN or Inf values")
    model.fit(values, fit_subset["_batch"].to_numpy())
    return model, markers, invalid, valid, fit_subset


def _collect_arcsinh_files(arcsinh_dir: Path, experiments: list[str]) -> list[Path]:
    """Collect the notebook's sorted ARCSINH_5 input files."""
    files = sorted(
        file
        for experiment in experiments
        for file in (arcsinh_dir / experiment).rglob("*_ARCSINH_5.csv")
    )
    if not files:
        raise FileNotFoundError(f"No files found in: {arcsinh_dir}")
    return files


def _load_fit_frame(arcsinh_dir: Path, experiments: list[str]) -> pd.DataFrame:
    """Load fit inputs in cell 25's experiment-then-file order."""
    frames = []
    for experiment in experiments:
        for file in sorted((arcsinh_dir / experiment).rglob("*_ARCSINH_5.csv")):
            frame = pd.read_csv(file, low_memory=False)
            frame["_batch"] = experiment
            frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _sample_fit_cells(data: pd.DataFrame, markers: list[str]) -> pd.DataFrame:
    """Reverse-transform and source-sample up to ten thousand rows per batch/condition."""
    subset = (
        data.groupby(["_batch", "condition"], group_keys=False)
        .sample(frac=1, random_state=42)
        .groupby(["_batch", "condition"], group_keys=False)
        .head(10000)
    )
    return cast(pd.DataFrame, subset)


def _reverse_arcsinh(data: pd.DataFrame, markers: list[str]) -> NDArray[np.float64]:
    """Convert source `arcsinh(raw / 5)` values back to raw scale and validate."""
    return np.asarray(5 * np.sinh(data[markers].to_numpy(dtype=float)), dtype=np.float64)


def _resolve_somot_factory() -> Callable[..., FittableBatchCorrectionModel]:
    """Import the same SOM-OT class used by source cell 25, without installing it."""
    from somot_warp.multi_batch import MultiBatchSOMOTWarp  # type: ignore[reportMissingImports]

    return MultiBatchSOMOTWarp


def process_batch_correction_files(
    arcsinh_dir: Path,
    output_dir: Path,
    experiments: list[str],
    model: BatchCorrectionModel,
    marker_cols: list[str],
    invalid_markers: list[str],
    all_marker_cols: list[str] = ALL_MARKER_COLS,
) -> pd.DataFrame:
    """Correct source files, preserve their relative layout, and verify markers."""
    _collect_arcsinh_files(arcsinh_dir, experiments)
    saved_files = _correct_files(
        arcsinh_dir, output_dir, experiments, model, marker_cols, invalid_markers
    )
    _verify_output_markers(saved_files, all_marker_cols)
    return _correction_summary(saved_files, marker_cols)


def _correct_files(
    arcsinh_dir: Path,
    output_dir: Path,
    experiments: list[str],
    model: BatchCorrectionModel,
    marker_cols: list[str],
    invalid_markers: list[str],
) -> list[tuple[Path, Path, int]]:
    """Apply the source function to every input in experiment/file order."""
    saved = []
    for experiment in experiments:
        for source in sorted((arcsinh_dir / experiment).rglob("*_ARCSINH_5.csv")):
            data = pd.read_csv(source, low_memory=False)
            relative = source.relative_to(arcsinh_dir)
            target = output_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            batch_correct(data, marker_cols, experiment, model, invalid_markers).to_csv(
                target, index=False
            )
            saved.append((source, target, len(data)))
    return saved


def _verify_output_markers(
    saved_files: list[tuple[Path, Path, int]], all_marker_cols: list[str]
) -> None:
    """Keep cell 25's shared biological-marker consistency check."""
    output_marker_sets = [
        set(pd.read_csv(target, nrows=0).columns).intersection(all_marker_cols)
        for _, target, _ in saved_files
    ]
    if output_marker_sets and not all(
        markers == output_marker_sets[0] for markers in output_marker_sets
    ):
        raise ValueError("Output files do not share the same biological markers")


def _correction_summary(
    saved_files: list[tuple[Path, Path, int]], marker_cols: list[str]
) -> pd.DataFrame:
    """Summarize the files written by the source cell's application loop."""
    rows = []
    for source, target, n_cells in saved_files:
        rows.append(
            {
                "input_file": str(source),
                "output_file": str(target),
                "n_cells": n_cells,
                "n_markers_corrected": len(marker_cols),
            }
        )
    return pd.DataFrame(rows)
