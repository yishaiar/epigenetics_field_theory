"""SOM-OT fitting and application extracted from main1.ipynb cell 25."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd
from dotenv import dotenv_values
from numpy.typing import NDArray

from app.config import env_dir
from app.config.config import METADATA_COLUMNS

_INTERNAL_METADATA_COLUMNS = {"_batch", "_arcsinh_file", "_source_file"}
_BATCH_CORRECTION_EXCLUDED_COLUMNS = set(METADATA_COLUMNS) | _INTERNAL_METADATA_COLUMNS


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
    skip_columns: list[str],
    model_factory: Callable[..., FittableBatchCorrectionModel] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Fit SOM-OT on pooled rows and correct every shared marker once.

    Args:
        df: Pooled ArcSinh table with experiment, condition, and source metadata.
        skip_columns: Metadata columns to preserve without correction.
        model_factory: Optional SOM-OT factory, primarily for controlled runs.

    Returns:
        The corrected pooled dataframe and marker columns corrected by SOM-OT.

    Raises:
        ValueError: If required metadata or shared finite markers are unavailable.
    """
    source_column = next(
        (
            column
            for column in ("path", "_arcsinh_file", "_source_file", "source_file")
            if column in df.columns
        ),
        None,
    )
    source_group_columns = (
        [source_column] if source_column is not None else ["experiment", "sample_name", "gfp_group"]
    )
    if source_column is None and not {"sample_name", "gfp_group"}.issubset(df.columns):
        raise ValueError("Pooled arcsinh data requires per-source file metadata")
    required = {"experiment", "condition", *source_group_columns}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Pooled arcsinh data is missing required columns: {missing}")
    required_metadata = list(dict.fromkeys(["experiment", "condition", *source_group_columns]))
    if df[required_metadata].isna().to_numpy().any():
        raise ValueError("Pooled arcsinh data has missing fit or source metadata")

    experiments = list(dict.fromkeys(df["experiment"].astype(str)))
    model, markers, _, _, _ = fit_batch_correction_data(
        df,
        experiments,
        model_factory=model_factory,
        skip_columns=skip_columns,
    )
    corrected = apply_fitted_batch_correction(
        df,
        markers,
        df["experiment"].to_numpy(),
        model,
    )
    output_columns = [
        column for column in df.columns if column in skip_columns or column in markers
    ]
    corrected_columns = [column for column in output_columns if column not in skip_columns]
    return corrected.loc[:, output_columns], corrected_columns


def apply_fitted_batch_correction(
    df: pd.DataFrame,
    marker_cols_: list[str],
    batch_label: str | np.ndarray,
    model: BatchCorrectionModel,
    invalid_markers: list[str] | None = None,
) -> pd.DataFrame:
    """Apply a fitted SOM-OT model to one table using its batch labels."""
    df_corrected = df.copy()
    invalid_markers = [] if invalid_markers is None else invalid_markers
    invalid_markers = [
        column for column in invalid_markers if column not in _BATCH_CORRECTION_EXCLUDED_COLUMNS
    ]
    df_corrected.drop(columns=invalid_markers, inplace=True, errors="ignore")
    marker_cols_ = [
        column for column in marker_cols_ if column not in _BATCH_CORRECTION_EXCLUDED_COLUMNS
    ]
    if not marker_cols_:
        raise ValueError("No marker columns remain after excluding metadata")
    X = _reverse_arcsinh(df_corrected, marker_cols_)
    if isinstance(batch_label, str):
        batch_labels = np.full(len(df_corrected), batch_label)
        batch_name = batch_label
    else:
        batch_labels = np.asarray(batch_label)
        if batch_labels.shape != (len(df_corrected),):
            raise ValueError("batch_label must contain one label per dataframe row")
        batch_name = "pooled data"
    if not np.isfinite(X).all():
        raise ValueError(f"Invalid input values for {batch_name}")
    X_corrected = model.transform(X, batch_labels)
    if not np.isfinite(X_corrected).all():
        raise ValueError(f"Batch correction produced NaN or Inf for {batch_name}")
    df_corrected[marker_cols_] = np.arcsinh(X_corrected / 5)
    return df_corrected


def select_correction_markers(
    files: list[Path],
    marker_cols: list[str] | None = None,
    all_marker_cols: list[str] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Select markers shared by all files and finite in every file.

    Args:
        files: Input CSV paths to inspect.
        marker_cols: Optional preferred marker order. By default, all shared
            nonmetadata columns are candidates.
        all_marker_cols: Optional candidate restriction for specialized callers.

    Returns:
        Selected markers in ``marker_cols`` order, invalid candidate markers,
        and all valid shared markers in sorted order.

    Raises:
        FileNotFoundError: If ``files`` is empty.
        ValueError: If no requested marker remains valid.
    """
    if not files:
        raise FileNotFoundError("No files found for batch correction")
    file_columns = [pd.read_csv(file, nrows=0).columns.tolist() for file in files]
    shared_markers = set(file_columns[0])
    for file in files:
        shared_markers &= set(pd.read_csv(file, nrows=0).columns)
    candidates = shared_markers.difference(_BATCH_CORRECTION_EXCLUDED_COLUMNS)
    if all_marker_cols is not None:
        candidates.intersection_update(all_marker_cols)
    valid_markers = set(candidates)
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
    all_candidates = set().union(*(set(columns) for columns in file_columns))
    all_candidates.difference_update(_BATCH_CORRECTION_EXCLUDED_COLUMNS)
    if all_marker_cols is not None:
        all_candidates.update(all_marker_cols)
    invalid_markers = sorted(all_candidates - valid_markers)
    preferred_order = marker_cols if marker_cols is not None else file_columns[0]
    selected_markers = [marker for marker in preferred_order if marker in valid_markers]
    if not selected_markers:
        raise ValueError("No valid markers remain for batch correction")
    return selected_markers, invalid_markers, sorted(valid_markers)


def fit_batch_correction(
    arcsinh_dir: Path,
    experiments: list[str],
    marker_cols: list[str] | None = None,
    all_marker_cols: list[str] | None = None,
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
    model_factory: Callable[..., FittableBatchCorrectionModel] | None = None,
    skip_columns: list[str] | None = None,
    marker_cols: list[str] | None = None,
    all_marker_cols: list[str] | None = None,
) -> tuple[FittableBatchCorrectionModel, list[str], list[str], list[str], pd.DataFrame]:
    """Fit SOM-OT using the arcsinh table already loaded by the notebook."""
    source_column = next(
        (
            column
            for column in ("path", "_arcsinh_file", "_source_file", "source_file")
            if column in data.columns
        ),
        None,
    )
    source_group_columns = (
        [source_column] if source_column is not None else ["experiment", "sample_name", "gfp_group"]
    )
    if source_column is None and not {"sample_name", "gfp_group"}.issubset(data.columns):
        raise ValueError("Loaded arcsinh data requires per-source file metadata")
    required = {"experiment", "condition"}
    required.update(source_group_columns)
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Loaded arcsinh data is missing required columns: {missing}")
    selected_data = data.loc[data["experiment"].isin(experiments)].copy()
    if selected_data.empty:
        raise ValueError("No loaded arcsinh rows match the requested experiments")
    selected_data["_batch"] = selected_data["experiment"]
    excluded_columns = set(_BATCH_CORRECTION_EXCLUDED_COLUMNS)
    if skip_columns is not None:
        excluded_columns.update(skip_columns)
    candidates = [column for column in selected_data.columns if column not in excluded_columns]
    if all_marker_cols is not None:
        candidates = [column for column in candidates if column in all_marker_cols]
    valid_markers = set(candidates)
    groupby_columns: str | list[str] = (
        source_group_columns[0] if len(source_group_columns) == 1 else source_group_columns
    )
    for _, file_data in selected_data.groupby(groupby_columns, sort=False):
        for marker in list(valid_markers):
            values = np.asarray(pd.to_numeric(file_data[marker], errors="coerce"), dtype=float)
            if not np.isfinite(values).all():
                valid_markers.remove(marker)
    invalid_markers = [marker for marker in candidates if marker not in valid_markers]
    preferred_order = candidates if marker_cols is None else marker_cols
    correction_markers = [marker for marker in preferred_order if marker in valid_markers]
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


def process_batch_correction(
    arcsinh_dir: Path,
    output_dir: Path,
    experiments: list[str],
    model_factory: Callable[..., FittableBatchCorrectionModel] | None = None,
) -> tuple[
    FittableBatchCorrectionModel,
    list[str],
    list[str],
    list[str],
    pd.DataFrame,
    pd.DataFrame,
]:
    """Load arcsinh files, fit SOM-OT on their combined rows, and export corrections.

    The concatenated dataframe and its per-file provenance columns are internal
    to this workflow. Corrected outputs remain separate and preserve their
    source-relative paths.

    Args:
        arcsinh_dir: Root containing experiment-specific arcsinh CSV files.
        output_dir: Destination root for per-source-file corrected CSVs.
        experiments: Experiment folder names included in the correction.
        model_factory: Optional constructor for a compatible SOM-OT model.

    Returns:
        The fitted model, selected markers, invalid markers, all valid markers,
        fit subset, and per-file correction summary.
    """
    files = _collect_arcsinh_files(arcsinh_dir, experiments)
    frames = []
    for source in files:
        relative = source.relative_to(arcsinh_dir)
        frame = pd.read_csv(source, low_memory=False)
        frame["_batch"] = relative.parts[0]
        frame["_arcsinh_file"] = relative.as_posix()
        frames.append(frame)
    arcsinh_data = pd.concat(frames, ignore_index=True)

    model, markers, invalid, valid, fit_subset = fit_batch_correction_data(
        arcsinh_data,
        experiments,
        model_factory=model_factory,
    )
    summary = process_batch_correction_data(
        arcsinh_data,
        arcsinh_dir,
        output_dir,
        model,
        markers,
        invalid,
    )
    return model, markers, invalid, valid, fit_subset, summary


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
    seed_value = dotenv_values(env_dir).get("RANDOM_STATE")
    if seed_value is None:
        raise ValueError(f"RANDOM_STATE is missing from {env_dir}")
    random_state = int(seed_value)
    subset = (
        data.groupby(["_batch", "condition"], group_keys=False)
        .sample(frac=1, random_state=random_state)
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
    all_marker_cols: list[str] | None = None,
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
    all_marker_cols: list[str] | None = None,
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
        corrected = apply_fitted_batch_correction(
            file_data, marker_cols, experiment, model, invalid_markers
        )
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
            apply_fitted_batch_correction(
                data, marker_cols, experiment, model, invalid_markers
            ).to_csv(target, index=False)
            saved.append((source, target, len(data)))
    return saved


def _verify_output_markers(
    saved_files: list[tuple[Path, Path, int]], all_marker_cols: list[str] | None = None
) -> None:
    """Ensure corrected files contain the same biological marker columns.

    Args:
        saved_files: Input/output paths and row counts for corrected files.
        all_marker_cols: Optional marker restriction for specialized callers.

    Raises:
        ValueError: If corrected files have different biological marker sets.
    """
    output_marker_sets = []
    for _, target, _ in saved_files:
        markers = set(pd.read_csv(target, nrows=0).columns).difference(
            _BATCH_CORRECTION_EXCLUDED_COLUMNS
        )
        if all_marker_cols is not None:
            markers.intersection_update(all_marker_cols)
        output_marker_sets.append(markers)
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
