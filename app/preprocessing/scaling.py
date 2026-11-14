"""Balanced-reference pooled z-scoring and legacy per-experiment scaling."""

from itertools import product
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from dotenv import dotenv_values
from sklearn.preprocessing import StandardScaler

from app.config import env_dir
from app.config.config import METADATA_COLUMNS


def _equal_allocation_capacity(available: list[int]) -> int:
    smallest = min(available)
    return len(available) * smallest + sum(count > smallest for count in available)


def _allocate_equally(total: int, available: list[int], rng: np.random.Generator) -> np.ndarray:
    base, remainder = divmod(total, len(available))
    allocations = np.full(len(available), base, dtype=int)
    eligible = np.flatnonzero(np.asarray(available) > base)
    if remainder:
        allocations[rng.choice(eligible, size=remainder, replace=False)] += 1
    return allocations


def hierarchical_zscore(
    data: pd.DataFrame,
    *,
    group_columns: tuple[str, str] = ("condition", "labels"),
    group_1_values: Sequence[object] = ("untreated", "treated"),
    group_2_values: Sequence[object] = ("basal", "classical"),
    hierarchy_columns: tuple[str, str] = ("experiment", "sample_name"),
    use_labels: bool = False,
    skip_columns: list[str] = METADATA_COLUMNS,
    reference_size_per_group: int = 10_000,
) -> tuple[pd.DataFrame, StandardScaler, pd.Index, list[object], pd.DataFrame]:
    """Z-score selected features using one hierarchically balanced reference.

    1. Optionally split by every supplied group column and drop rows missing
       the final group column when ``use_labels`` is true.
    2. Allocate each group equally across the two hierarchy columns, reducing
       the shared reference size to fit available cells.
    3. Fit one scaler on the combined reference and transform remaining rows.
    4. Return scaled data, selected and dropped indices, and group counts.

    Group columns, their values, and hierarchy columns have defaults for the
    current workflow. The seed is read from ``RANDOM_STATE`` in the project .env.
    """
    selected_group_columns = list(group_columns if use_labels else group_columns[:1])
    group_values = [group_1_values, group_2_values] if use_labels else [group_1_values]
    group_combinations = list(product(*group_values))
    parent_columns = selected_group_columns[:-1] if use_labels else selected_group_columns
    parent_values_list = group_values[:-1] if use_labels else group_values
    first_level_column, second_level_column = hierarchy_columns
    dropped_indices = (
        data.index[data[selected_group_columns[-1]].isna()].tolist() if use_labels else []
    )
    if use_labels:
        data = data.loc[data[selected_group_columns[-1]].notna()].copy()

    reference_data = data.dropna(subset=[*selected_group_columns, *hierarchy_columns])
    feature_columns = [column for column in data.columns if column not in set(skip_columns)]
    rng = np.random.default_rng(int(dotenv_values(env_dir).get("RANDOM_STATE") or "0"))
    group_indices = reference_data.groupby(
        [*selected_group_columns, *hierarchy_columns], sort=False
    ).groups
    first_level_values = list(pd.unique(reference_data[first_level_column]))
    parent_combinations = list(product(*parent_values_list))

    values_by_group_and_level = {}
    for parent_values in parent_combinations:
        parent_mask = pd.Series(True, index=reference_data.index)
        for column, value in zip(parent_columns, parent_values):
            parent_mask &= reference_data[column].eq(value)
        for first_level_value in first_level_values:
            group_rows = reference_data.loc[
                parent_mask & reference_data[first_level_column].eq(first_level_value)
            ]
            values_by_group_and_level[parent_values, first_level_value] = [
                value
                for value in pd.unique(group_rows[second_level_column])
                if all(
                    (*combination, first_level_value, value) in group_indices
                    for combination in group_combinations
                    if combination[: len(parent_values)] == parent_values
                )
            ]

    capacities_by_group = {}
    for combination in group_combinations:
        parent_values = combination[: len(parent_columns)]
        capacities_by_group[combination] = [
            _equal_allocation_capacity(
                [
                    len(group_indices[(*combination, level_value, value)])
                    for value in values_by_group_and_level[parent_values, level_value]
                ]
            )
            for level_value in first_level_values
        ]

    reference_size = min(
        reference_size_per_group,
        *(_equal_allocation_capacity(capacities) for capacities in capacities_by_group.values()),
    )
    minimum_size = len(first_level_values) * max(
        len(values) for values in values_by_group_and_level.values()
    )
    if reference_size < minimum_size:
        raise ValueError("Available cells cannot support the balanced reference allocation.")

    reference_indices = []
    for combination in group_combinations:
        parent_values = combination[: len(parent_columns)]
        level_counts = _allocate_equally(reference_size, capacities_by_group[combination], rng)
        for level_value, level_count in zip(first_level_values, level_counts):
            values = values_by_group_and_level[parent_values, level_value]
            candidate_indices = [
                group_indices[(*combination, level_value, value)] for value in values
            ]
            value_counts = _allocate_equally(
                int(level_count), [len(indices) for indices in candidate_indices], rng
            )
            for indices, count in zip(candidate_indices, value_counts):
                reference_indices.extend(rng.choice(indices, size=count, replace=False).tolist())

    reference_indices = pd.Index(reference_indices)
    scaler = StandardScaler().fit(data.loc[reference_indices, feature_columns])
    scaled_data = data.copy()
    scaled_data[feature_columns] = scaler.transform(data[feature_columns])

    summary_columns = [
        first_level_column,
        *selected_group_columns[::-1],
        second_level_column,
    ]
    summary = data.groupby(summary_columns, dropna=False, sort=True).size().to_frame()
    summary.columns = ["n"]
    summary = summary.reset_index()
    reference_summary = (
        data.loc[reference_indices]
        .groupby(summary_columns, dropna=False, sort=True)
        .size()
        .to_frame()
    )
    reference_summary.columns = ["n_subsample"]
    reference_summary = reference_summary.reset_index()
    summary = summary.merge(reference_summary, on=summary_columns, how="left")
    summary["n_subsample"] = summary["n_subsample"].fillna(0).astype(int)
    aggregates = (
        summary.groupby(summary_columns[:-1], dropna=False, sort=True)[["n", "n_subsample"]]
        .sum()
        .reset_index()
    )
    aggregates[second_level_column] = pd.NA
    summary = pd.concat([aggregates, summary], ignore_index=True)
    summary["_sample_sort"] = summary[second_level_column].notna()
    summary = (
        summary.set_index([*summary_columns[:-1], "_sample_sort", second_level_column])
        .sort_index()
        .reset_index()
        .drop(columns="_sample_sort")
    )
    summary = summary.loc[
        :,
        [
            "n",
            "n_subsample",
            first_level_column,
            *selected_group_columns,
            second_level_column,
        ],
    ]
    return scaled_data, scaler, reference_indices, dropped_indices, summary


def zscore_markers(
    data: pd.DataFrame,
    skip_columns: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Z-score every numeric, non-skipped column across the supplied rows.

    Args:
        data: The dataframe to scale, whether pooled or from one GFP group.
        skip_columns: Column names to preserve without scaling.

    Returns:
        A copy of the complete input table and the numeric marker columns scaled
        using their mean and population standard deviation across all rows.

    Constant numeric columns are set to zero. Nonnumeric and all-missing
    columns are left unchanged.
    """
    df_z = data.copy()
    scaled_columns = []
    excluded = set(METADATA_COLUMNS).union(skip_columns)
    for column in data.select_dtypes(include=[np.number]).columns:
        if column in excluded:
            continue
        values = data[column]
        if values.notna().sum() == 0:
            continue
        scaled_columns.append(column)
        standard_deviation = float(values.std(ddof=0))
        if standard_deviation == 0:
            df_z[column] = 0
        else:
            df_z[column] = (values - values.mean()) / standard_deviation
    return df_z, scaled_columns


def zscore_markers_from_balanced_reference(
    data: pd.DataFrame,
    skip_columns: list[str],
    *,
    condition_column: str = "condition",
    subtype_column: str = "labels",
    experiment_column: str = "experiment",
    mouse_column: str = "sample_name",
    cell_index_column: str = "cell_uid",
    n_reference_cells_per_group: int | None = None,
    random_state: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[object]]:
    """Scale all cells using one batch- and mouse-balanced reference subset.

    Each condition-subtype group receives the same target size, capped by the
    smallest group. Each target is allocated across batches and then across
    treatment-matched mice. The target is reduced if any allocation is
    unavailable. One scaler is fitted on the combined reference and applied to
    the complete input table.

    Args:
        data: Complete preprocessed and batch-corrected cell table.
        skip_columns: Metadata and other columns excluded from scaling.
        condition_column: Treatment column with treated and untreated values.
        subtype_column: Biological subtype column with basal and classical values.
        experiment_column: Batch identifier used to allocate reference cells.
        mouse_column: Mouse identifier used to allocate reference cells.
        cell_index_column: Unique per-cell identifier retained in the output.
        n_reference_cells_per_group: Optional maximum target per
            condition-subtype group. ``None`` uses the smallest full group size.
        random_state: Optional seed override; defaults to ``RANDOM_STATE`` from
            ``app/config/.env``.

    Returns:
        Complete scaled data, per-batch and per-mouse reference allocations,
        and selected reference cell IDs. ``n_reference_cells`` is the shared
        final target, and ``n_allocated_cells`` is that row's mouse allocation.

    Raises:
        ValueError: If required columns or biological groups are absent, IDs are
            invalid, or no balanced reference can be sampled.
    """
    required = [
        condition_column,
        subtype_column,
        experiment_column,
        mouse_column,
        cell_index_column,
    ]
    missing = set(required).difference(data.columns)
    if missing:
        raise ValueError(f"Balanced-reference scaling is missing columns: {sorted(missing)}")
    if data.empty:
        raise ValueError("Balanced-reference scaling requires at least one cell")
    if bool(data[cell_index_column].isna().to_numpy().any()):
        raise ValueError(f"{cell_index_column} values must be non-null and unique")
    if not data[cell_index_column].is_unique:
        raise ValueError(f"{cell_index_column} values must be non-null and unique")
    if random_state is None:
        seed_value = dotenv_values(env_dir).get("RANDOM_STATE")
        if seed_value is None:
            raise ValueError(f"RANDOM_STATE is missing from {env_dir}")
        random_state = int(seed_value)

    groups: list[tuple[str, str]] = [
        (condition, subtype)
        for condition in ("untreated", "treated")
        for subtype in ("basal", "classical")
    ]
    observed = set(data[[condition_column, subtype_column]].itertuples(index=False, name=None))
    missing_groups = [group for group in groups if group not in observed]
    if missing_groups:
        raise ValueError(f"Missing required condition-subtype groups: {missing_groups}")
    group_sizes = {
        group: int((data[condition_column].eq(group[0]) & data[subtype_column].eq(group[1])).sum())
        for group in groups
    }
    reference_rows = data[[experiment_column, mouse_column]].notna().all(axis=1)
    group_masks = {
        group: reference_rows
        & data[condition_column].eq(group[0])
        & data[subtype_column].eq(group[1])
        for group in groups
    }
    if n_reference_cells_per_group is not None and n_reference_cells_per_group < 1:
        raise ValueError("n_reference_cells_per_group must be a positive integer")

    requested_size = min(group_sizes.values())
    if n_reference_cells_per_group is not None:
        requested_size = min(requested_size, n_reference_cells_per_group)
    experiments = sorted(data[experiment_column].dropna().unique().tolist(), key=str)

    def allocate_reference(target: int) -> list[tuple[object, str, str, object, int]] | None:
        allocations: list[tuple[object, str, str, object, int]] = []
        batch_counts = {
            experiment: target // len(experiments) + int(position < target % len(experiments))
            for position, experiment in enumerate(experiments)
        }
        for condition, subtype in groups:
            group_mask = group_masks[(condition, subtype)]
            for experiment, batch_count in batch_counts.items():
                if batch_count == 0:
                    continue
                batch_data = data.loc[
                    data[condition_column].eq(condition)
                    & data[experiment_column].eq(experiment)
                    & data[mouse_column].notna()
                ]
                mice = sorted(batch_data[mouse_column].unique().tolist(), key=str)
                if not mice:
                    return None
                for position, mouse in enumerate(mice):
                    mouse_count = batch_count // len(mice) + int(position < batch_count % len(mice))
                    available = int(
                        (
                            group_mask
                            & data[experiment_column].eq(experiment)
                            & data[mouse_column].eq(mouse)
                        ).sum()
                    )
                    if mouse_count > available:
                        return None
                    if mouse_count:
                        allocations.append((experiment, condition, subtype, mouse, mouse_count))
        return allocations

    reference_size = 0
    allocations = None
    for candidate_size in range(requested_size, 0, -1):
        candidate_allocations = allocate_reference(candidate_size)
        if candidate_allocations is not None:
            reference_size = candidate_size
            allocations = candidate_allocations
            break
    if reference_size == 0 or allocations is None:
        raise ValueError("No non-empty balanced reference is available across batches and mice")

    rng = np.random.default_rng(random_state)
    selected_positions: list[int] = []
    summary_rows: list[dict[str, object]] = []
    for experiment, condition, subtype, mouse, count in allocations:
        candidates = np.flatnonzero(
            group_masks[(condition, subtype)].to_numpy()
            & data[experiment_column].eq(experiment).to_numpy()
            & data[mouse_column].eq(mouse).to_numpy()
        )
        selected_positions.extend(rng.choice(candidates, size=count, replace=False).tolist())
        summary_rows.append(
            {
                experiment_column: experiment,
                condition_column: condition,
                subtype_column: subtype,
                mouse_column: mouse,
                "n": group_sizes[(condition, subtype)],
                "n_reference_cells": reference_size,
                "n_allocated_cells": count,
            }
        )

    reference = data.iloc[selected_positions]
    excluded_columns = set(METADATA_COLUMNS).union(skip_columns)
    feature_columns = [
        column
        for column in data.select_dtypes(include=[np.number]).columns
        if column not in excluded_columns
    ]
    if not feature_columns:
        raise ValueError("No numeric feature columns remain after excluding metadata")
    scaler = StandardScaler()
    scaler.fit(reference[feature_columns])
    scaled = data.copy()
    scaled.loc[:, feature_columns] = scaler.transform(data[feature_columns])
    reference_cell_ids = data.iloc[selected_positions][cell_index_column].tolist()
    allocation_columns = [
        experiment_column,
        condition_column,
        subtype_column,
        mouse_column,
        "n",
        "n_reference_cells",
        "n_allocated_cells",
    ]
    reference_allocation = (
        pd.DataFrame(summary_rows)
        .reindex(columns=allocation_columns)
        .sort_values(allocation_columns[:4], kind="stable")
        .reset_index(drop=True)
    )
    return scaled, reference_allocation, reference_cell_ids


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
    scale_columns = [
        column
        for column in data.select_dtypes(include=[np.number]).columns
        if column not in METADATA_COLUMNS
    ]
    skip_columns = [column for column in data.columns if column not in scale_columns]
    zscored, _ = zscore_markers(data, skip_columns=skip_columns)
    valid = [column for column in scale_columns if _numeric_series(data, column).notna().any()]
    skipped = [column for column in scale_columns if column not in valid]
    zero_variance = [column for column in valid if _numeric_series(data, column).std(ddof=0) == 0]
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
