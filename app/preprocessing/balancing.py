"""GFP-high balancing workflow copied from main1.ipynb cell 31."""

from pathlib import Path
from typing import TypedDict

import pandas as pd
from dotenv import dotenv_values

from app.config import env_dir


class SampleData(TypedDict):
    """One normalized sample and its source metadata from cell 31."""

    sample_name: str
    condition: str
    file: Path
    df: pd.DataFrame


def balance_samples(
    normalized_dir: Path,
    output_dir: Path,
    experiments: list[str],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """Balance each experiment's normalized GFP-high samples to equal size.

    Args:
        normalized_dir: Root containing experiment-specific GFP-high CSV files.
        output_dir: Directory for balanced tables and summary CSVs.
        experiments: Experiment directories to process, in output order.

    Returns:
        Balanced tables by experiment, input sample counts, and a balancing
        summary table.
    """
    all_rows = []
    all_dfs = {}
    for experiment in experiments:
        samples, rows = _load_experiment_samples(normalized_dir, experiment)
        if samples:
            all_dfs[experiment] = samples
        all_rows.extend(rows)
    counts_df = pd.DataFrame(all_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    counts_df.to_csv(output_dir / "GFP_high_cell_counts_before_balancing.csv", index=False)
    balanced_by_experiment = {}
    summary_rows = []
    for experiment, samples in all_dfs.items():
        balanced, rows = _balance_experiment(experiment, samples)
        balanced_by_experiment[experiment] = balanced
        balanced.to_csv(output_dir / f"{experiment}_GFP_high_BALANCED.csv", index=False)
        summary_rows.extend(rows)
    balance_summary = pd.DataFrame(summary_rows)
    balance_summary.to_csv(output_dir / "GFP_high_balancing_summary.csv", index=False)
    return balanced_by_experiment, counts_df, balance_summary


def subsample_gfp_high(
    data: pd.DataFrame,
    subsample: bool,
    use_labels: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Optionally subsample GFP-high cells and summarize before/after counts.

    1. Group samples by experiment, condition, and optionally subtype.
    2. If enabled, sample each group to the smallest group size per experiment.
    3. Return selected rows and a summary with sample and aggregate counts.

    Args:
        data: Z-scored dataframe that already contains only GFP-high cells.
        subsample: Whether to balance sample sizes within each experiment.
        use_labels: Whether subtype labels are included in balancing groups.

    Returns:
        Selected dataframe and a count summary. Aggregate rows have no
        ``sample_name`` and sum over samples in each group.
    """
    group_columns = ["experiment", "condition", *(["labels"] if use_labels else []), "sample_name"]
    if subsample:
        selected_groups = []
        for _, experiment_data in data.groupby("experiment", sort=True):
            sample_groups = experiment_data.groupby(group_columns[1:], sort=True, dropna=False)
            target_size = int(sample_groups.size().min())
            selected_groups.extend(
                group.sample(n=target_size, replace=False, random_state=42 + index)
                for index, (_, group) in enumerate(sample_groups)
            )
        selected_data = pd.concat(selected_groups, ignore_index=True)
    else:
        selected_data = data

    summary: pd.DataFrame = data.groupby(group_columns, dropna=False, sort=True).size().to_frame()
    summary.columns = ["n_before"]
    selected_summary = (
        selected_data.groupby(group_columns, dropna=False, sort=True).size().to_frame()
    )
    selected_summary.columns = ["n_selected"]
    summary = summary.join(selected_summary).fillna({"n_selected": 0}).reset_index()
    summary["n_selected"] = summary["n_selected"].astype(int)
    aggregate_summary = (
        summary.groupby(group_columns[:-1], dropna=False, sort=True)[["n_before", "n_selected"]]
        .sum()
        .reset_index()
    )
    aggregate_summary["sample_name"] = pd.NA
    summary = pd.concat([aggregate_summary, summary], ignore_index=True)
    sort_columns = ["experiment", *(["labels"] if use_labels else []), "condition", "sample_name"]
    summary["_sample_sort"] = summary["sample_name"].notna()
    summary = (
        summary.set_index([*sort_columns[:-1], "_sample_sort", "sample_name"])
        .sort_index()
        .reset_index()
        .drop(columns="_sample_sort")
    )
    summary = summary.loc[:, ["n_before", "n_selected", *group_columns]]
    return selected_data, summary


def _load_experiment_samples(
    normalized_dir: Path, experiment: str
) -> tuple[list[SampleData], list[dict[str, object]]]:
    """Load all GFP-high samples for an experiment and record their counts.

    Args:
        normalized_dir: Root containing experiment-specific normalized files.
        experiment: Experiment whose GFP-high files should be loaded.

    Returns:
        The sample records and one count record per input file.
    """
    files = sorted((normalized_dir / experiment / "GFP_high").rglob("*_NORMALIZED.csv"))
    samples = []
    rows = []
    for file in files:
        data = pd.read_csv(file, low_memory=False)
        sample_name = (
            str(data["sample_name"].iloc[0]) if "sample_name" in data and len(data) else file.stem
        )
        condition = (
            str(data["condition"].iloc[0]) if "condition" in data and len(data) else "unknown"
        )
        rows.append(
            {
                "experiment": experiment,
                "sample_name": sample_name,
                "condition": condition,
                "file": str(file),
                "n_GFP_high_cells": len(data),
            }
        )
        samples.append(
            {"sample_name": sample_name, "condition": condition, "file": file, "df": data}
        )
    return samples, rows


def _balance_experiment(
    experiment: str, samples: list[SampleData]
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Downsample each sample to the smallest sample's cell count.

    Args:
        experiment: Experiment identifier included in summary records.
        samples: Sample records to balance.

    Returns:
        The concatenated balanced table and one before/after record per sample.
    """
    n_min = min(len(item["df"]) for item in samples)
    # Read the sampling seed from .env; no code-level default is used.
    seed_value = dotenv_values(env_dir).get("RANDOM_STATE")
    if seed_value is None:
        raise ValueError(f"RANDOM_STATE is missing from {env_dir}")
    random_state = int(seed_value)
    balanced_parts = []
    summary_rows = []
    for index, item in enumerate(samples):
        data = item["df"]
        balanced = data.sample(n=n_min, replace=False, random_state=random_state + index).copy()
        balanced_parts.append(balanced)
        summary_rows.append(
            {
                "experiment": experiment,
                "sample_name": item["sample_name"],
                "condition": item["condition"],
                "n_before": len(data),
                "n_after_balancing": len(balanced),
                "limiting_n_for_experiment": n_min,
                "is_limiting_sample": len(data) == n_min,
            }
        )
    return pd.concat(balanced_parts, ignore_index=True), summary_rows


def process_balancing_files(
    normalized_dir: Path, output_dir: Path, experiments: list[str]
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """Run the GFP-high balancing workflow for the requested experiments.

    Args:
        normalized_dir: Root containing experiment-specific normalized files.
        output_dir: Directory for balanced tables and summaries.
        experiments: Experiment directories to process, in output order.

    Returns:
        Balanced tables by experiment, input sample counts, and a balancing
        summary table.
    """
    return balance_samples(normalized_dir, output_dir, experiments)
