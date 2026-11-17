"""Hierarchically balanced pooled z-scoring."""

from itertools import product
from typing import Sequence

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
