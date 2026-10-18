"""GFP-high balancing workflow copied from main1.ipynb cell 31."""

from pathlib import Path
from typing import TypedDict

import pandas as pd


RANDOM_STATE = 42
BATCH2_SKIP_SAMPLE = "1484"


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


def _load_experiment_samples(
    normalized_dir: Path, experiment: str
) -> tuple[list[SampleData], list[dict[str, object]]]:
    """Load an experiment's GFP-high samples and record skipped files.

    Args:
        normalized_dir: Root containing experiment-specific normalized files.
        experiment: Experiment whose GFP-high files should be loaded.

    Returns:
        The non-skipped sample records and one count/skip record per input file.
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
        skipped = experiment == "batch2" and (
            BATCH2_SKIP_SAMPLE in sample_name or BATCH2_SKIP_SAMPLE in file.name
        )
        reason = "batch2 sample 1484 skipped: very small GFP+ sample size" if skipped else ""
        rows.append(
            {
                "experiment": experiment,
                "sample_name": sample_name,
                "condition": condition,
                "file": str(file),
                "n_GFP_high_cells": len(data),
                "skipped": skipped,
                "skip_reason": reason,
            }
        )
        if not skipped:
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
        samples: Non-skipped sample records to balance.

    Returns:
        The concatenated balanced table and one before/after record per sample.
    """
    n_min = min(len(item["df"]) for item in samples)
    balanced_parts = []
    summary_rows = []
    for index, item in enumerate(samples):
        data = item["df"]
        balanced = data.sample(n=n_min, replace=False, random_state=RANDOM_STATE + index).copy()
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
