"""SOM-OT fitting and application extracted from main1.ipynb cell 25."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from app.harmonization.marker_lists import (
    CELL_IDENTITY_MARKERS,
    EPIGENETIC_MARKERS,
)
from app.metadata import METADATA_EXCLUSION_COLUMNS

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
    ) -> NDArray[np.float64]:
        """Transform raw-scale marker values using fitted batch parameters.

        Args:
            values: Two-dimensional cells-by-markers matrix on the raw scale.
            batch_labels: One batch identifier per row in ``values``.

        Returns:
            Corrected cells-by-markers values on the raw scale.
        """
        ...


class FittableBatchCorrectionModel(BatchCorrectionModel, Protocol):
    """A source SOM-OT instance before the cell-25 fit call."""

    def fit(self, values: NDArray[np.float64], batch_labels: np.ndarray) -> object:
        """Fit model parameters from raw-scale marker values and batch labels.

        Args:
            values: Two-dimensional cells-by-markers matrix on the raw scale.
            batch_labels: One batch identifier per row in ``values``.

        Returns:
            The fitted model or another implementation-specific fit result.
        """
        ...


def batch_correct(
    df: pd.DataFrame,
    marker_cols_: list[str],
    batch_label: str,
    model: BatchCorrectionModel,
    invalid_markers: list[str] | None = None,
) -> pd.DataFrame:
    """Correct selected marker columns for one batch.

    Marker values are converted from arcsinh scale to raw scale before calling
    the model, then converted back afterward.

    Args:
        df: Input table containing the selected marker columns.
        marker_cols_: Marker columns to transform and correct.
        batch_label: Batch identifier passed to the correction model.
        model: Fitted model implementing :class:`BatchCorrectionModel`.
        invalid_markers: Optional nonmetadata columns to remove from the output.

    Returns:
        A corrected copy of ``df``.

    Raises:
        ValueError: If no marker columns remain or input/model output contains
            nonfinite values.
    """
    df_corrected = df.copy()
    invalid_markers = [] if invalid_markers is None else invalid_markers
    invalid_markers = [
        column for column in invalid_markers if column not in METADATA_EXCLUSION_COLUMNS
    ]
    df_corrected.drop(columns=invalid_markers, inplace=True, errors="ignore")
    marker_cols_ = [column for column in marker_cols_ if column not in METADATA_EXCLUSION_COLUMNS]
    if not marker_cols_:
        raise ValueError("No marker columns remain after excluding metadata")
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
    """Select markers shared by all files and finite in every file.

    Args:
        files: Input CSV paths to inspect.
        marker_cols: Preferred marker order for the selected marker list.
        all_marker_cols: Full set of candidate biological markers.

    Returns:
        Selected markers in ``marker_cols`` order, invalid candidate markers,
        and all valid shared markers in sorted order.

    Raises:
        FileNotFoundError: If ``files`` is empty.
        ValueError: If no requested marker remains valid.
    """
    if not files:
        raise FileNotFoundError("No files found for batch correction")
    shared_markers = set(all_marker_cols)
    for file in files:
        shared_markers &= set(pd.read_csv(file, nrows=0).columns)
    valid_markers = set(shared_markers).difference(METADATA_EXCLUSION_COLUMNS)
    for file in files:
        if not valid_markers:
            break
        checked = pd.read_csv(
            file, usecols=lambda column: column in valid_markers, low_memory=False
        )
        for marker in list(valid_markers):
            numeric: Any = pd.to_numeric(checked[marker], errors="coerce")
            values = numeric.to_numpy(dtype=float)
            if not np.isfinite(values).all():
                valid_markers.remove(marker)
    invalid_markers = sorted(set(all_marker_cols) - valid_markers - set(METADATA_EXCLUSION_COLUMNS))
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
    """Fit the SOM-OT model from sampled arcsinh files across experiments.

    Args:
        arcsinh_dir: Root containing experiment ``*_ARCSINH_5.csv`` files.
        experiments: Experiments included in model fitting.
        marker_cols: Preferred order for markers passed to the model.
        all_marker_cols: Full candidate marker list used during validation.
        model_factory: Optional constructor for a compatible fittable model.
            The source SOM-OT class is imported when omitted.

    Returns:
        The fitted model, selected markers, invalid markers, all valid markers,
        and the sampled fit table.

    Raises:
        FileNotFoundError: If no matching input files are found.
        ValueError: If markers or sampled values fail validation.
    """
    # Select shared, valid markers and prepare the fit rows.
    files = _collect_arcsinh_files(arcsinh_dir, experiments)
    markers, invalid, valid = select_correction_markers(files, marker_cols, all_marker_cols)
    fit_df = _load_fit_frame(arcsinh_dir, experiments)
    fit_subset = _sample_fit_cells(fit_df)
    # Construct the configured model, then fit it on raw-scale marker values.
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


def fit_batch_correction_data(
    data: pd.DataFrame,
    experiments: list[str],
    marker_cols: list[str] = MARKER_COLS,
    all_marker_cols: list[str] = ALL_MARKER_COLS,
    model_factory: Callable[..., FittableBatchCorrectionModel] | None = None,
) -> tuple[FittableBatchCorrectionModel, list[str], list[str], list[str], pd.DataFrame]:
    """Fit SOM-OT using the arcsinh table already loaded by the notebook."""
    required = {"experiment", "condition", "_arcsinh_file"}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Loaded arcsinh data is missing required columns: {missing}")
    selected_data = data.loc[data["experiment"].isin(experiments)].copy()
    if selected_data.empty:
        raise ValueError("No loaded arcsinh rows match the requested experiments")
    selected_data["_batch"] = selected_data["experiment"]
    candidates = [
        marker
        for marker in all_marker_cols
        if marker in selected_data.columns and marker not in METADATA_EXCLUSION_COLUMNS
    ]
    valid_markers = set(candidates)
    for _, file_data in selected_data.groupby("_arcsinh_file", sort=False):
        for marker in list(valid_markers):
            values = np.asarray(pd.to_numeric(file_data[marker], errors="coerce"), dtype=float)
            if not np.isfinite(values).all():
                valid_markers.remove(marker)
    invalid_markers = sorted(
        set(all_marker_cols).difference(valid_markers).difference(METADATA_EXCLUSION_COLUMNS)
    )
    correction_markers = [marker for marker in marker_cols if marker in valid_markers]
    if not correction_markers:
        raise ValueError("No valid markers remain for batch correction")
    fit_subset = _sample_fit_cells(selected_data)
    factory = _resolve_somot_factory() if model_factory is None else model_factory
    model = factory(
        anchor_label=sorted(selected_data["_batch"].unique())[0],
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
    values = _reverse_arcsinh(fit_subset, correction_markers)
    if not np.isfinite(values).all():
        raise ValueError("X_fit contains NaN or Inf values")
    model.fit(values, fit_subset["_batch"].to_numpy())
    return model, correction_markers, invalid_markers, sorted(valid_markers), fit_subset


def _collect_arcsinh_files(arcsinh_dir: Path, experiments: list[str]) -> list[Path]:
    """Find sorted arcsinh input files for the requested experiments.

    Args:
        arcsinh_dir: Root directory containing experiment folders.
        experiments: Experiment names whose input files should be collected.

    Returns:
        Matching ``*_ARCSINH_5.csv`` paths in sorted order.

    Raises:
        FileNotFoundError: If no matching files are found.
    """
    files = sorted(
        file
        for experiment in experiments
        for file in (arcsinh_dir / experiment).rglob("*_ARCSINH_5.csv")
    )
    if not files:
        raise FileNotFoundError(f"No files found in: {arcsinh_dir}")
    return files


def _load_fit_frame(arcsinh_dir: Path, experiments: list[str]) -> pd.DataFrame:
    """Load fit rows in experiment and file order, adding batch labels.

    Args:
        arcsinh_dir: Root directory containing experiment folders.
        experiments: Experiment names whose input files should be loaded.

    Returns:
        A concatenated table with each row's experiment in ``_batch``.
    """
    frames = []
    for experiment in experiments:
        for file in sorted((arcsinh_dir / experiment).rglob("*_ARCSINH_5.csv")):
            frame = pd.read_csv(file, low_memory=False)
            frame["_batch"] = experiment
            frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _sample_fit_cells(data: pd.DataFrame) -> pd.DataFrame:
    """Shuffle and sample up to 10,000 rows per batch and condition.

    Args:
        data: Input rows containing ``_batch`` and ``condition`` columns.
    Returns:
        A sampled copy containing at most 10,000 rows from each batch-condition
        group, selected after a reproducible shuffle.
    """
    subset = (
        data.groupby(["_batch", "condition"], group_keys=False)
        .sample(frac=1, random_state=42)
        .groupby(["_batch", "condition"], group_keys=False)
        .head(10000)
    )
    return pd.DataFrame(subset)


def _reverse_arcsinh(data: pd.DataFrame, markers: list[str]) -> NDArray[np.float64]:
    """Convert marker values from ``arcsinh(raw / 5)`` back to raw scale.

    Args:
        data: Table containing transformed marker values.
        markers: Marker columns to convert.

    Returns:
        A cells-by-markers NumPy array on the raw scale.
    """
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
    """Correct each requested experiment's files and write a summary.

    Args:
        arcsinh_dir: Root containing experiment ``*_ARCSINH_5.csv`` files.
        output_dir: Destination root; input-relative paths are preserved.
        experiments: Experiments to process, in requested order.
        model: Fitted model used to transform marker values.
        marker_cols: Marker columns passed to the model.
        invalid_markers: Invalid nonmetadata columns removed during correction.
        all_marker_cols: Candidate markers used to verify output consistency.

    Returns:
        A per-file correction summary table.

    Raises:
        FileNotFoundError: If there are no matching input files.
        ValueError: If output files do not share the same biological markers.
    """
    _collect_arcsinh_files(arcsinh_dir, experiments)
    saved_files = _correct_files(
        arcsinh_dir, output_dir, experiments, model, marker_cols, invalid_markers
    )
    _verify_output_markers(saved_files, all_marker_cols)
    return _correction_summary(saved_files, marker_cols)


def process_batch_correction_data(
    data: pd.DataFrame,
    arcsinh_dir: Path,
    output_dir: Path,
    model: BatchCorrectionModel,
    marker_cols: list[str],
    invalid_markers: list[str],
    all_marker_cols: list[str] = ALL_MARKER_COLS,
) -> pd.DataFrame:
    """Correct and export rows from the notebook's loaded arcsinh dataframe."""
    required = {"experiment", "_batch", "_arcsinh_file"}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Loaded arcsinh data is missing required columns: {missing}")
    saved_files = []
    for relative_file, file_data in data.groupby("_arcsinh_file", sort=False):
        relative = Path(str(relative_file))
        experiment = str(file_data["experiment"].iloc[0])
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        corrected = batch_correct(file_data, marker_cols, experiment, model, invalid_markers)
        corrected.drop(columns=["_arcsinh_file", "_batch"], errors="ignore").to_csv(
            target, index=False
        )
        saved_files.append((arcsinh_dir / relative, target, len(file_data)))
    if not saved_files:
        raise ValueError("Loaded arcsinh dataframe contains no files to correct")
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
    """Correct each input file and preserve its path relative to the input root.

    Args:
        arcsinh_dir: Root containing experiment ``*_ARCSINH_5.csv`` files.
        output_dir: Destination root for corrected files.
        experiments: Experiments to process, in requested order.
        model: Fitted correction model applied to each file.
        marker_cols: Marker columns passed to the correction model.
        invalid_markers: Nonmetadata columns to remove from each output.

    Returns:
        Tuples of input path, output path, and input cell count, in processing
        order.
    """
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
    """Ensure corrected files contain the same biological marker columns.

    Args:
        saved_files: Input/output paths and row counts for corrected files.
        all_marker_cols: Candidate biological marker names.

    Raises:
        ValueError: If corrected files have different biological marker sets.
    """
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
    """Build a per-file summary of the batch-correction outputs.

    Args:
        saved_files: Input/output paths and input row counts.
        marker_cols: Marker columns passed through batch correction.

    Returns:
        A table with file paths, cell counts, and corrected marker counts.
    """
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
