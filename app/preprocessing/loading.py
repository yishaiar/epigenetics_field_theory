"""Load annotated raw CSV files and summarize their sample provenance."""

from pathlib import Path

import pandas as pd


SUMMARY_COLUMNS = [
    "experiment",
    "condition",
    "sample_name",
    "replicate",
    "source_file",
    "source_path",
    "n_cells",
    "saved_file",
    "first_cell_id",
    "last_cell_id",
]


def load_raw_data(input_dir: Path, experiments: list[str]) -> pd.DataFrame:
    """Load sorted annotated raw CSVs for the requested experiments."""
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Raw data folder not found: {input_dir}")
    all_experiment_dfs = []
    for experiment in experiments:
        experiment_dir = input_dir / experiment
        if not experiment_dir.exists():
            continue
        csv_files = sorted(experiment_dir.rglob("*_raw_data.csv"))
        for csv_file in csv_files:
            df_file = pd.read_csv(csv_file, low_memory=False)
            all_experiment_dfs.append(df_file)
    if not all_experiment_dfs:
        raise ValueError(f"No '_raw_data.csv' files found inside {input_dir}")
    return pd.concat(all_experiment_dfs, ignore_index=True)


def summarize_raw_data(data: pd.DataFrame) -> pd.DataFrame:
    """Build the source notebook's ordered per-file sample summary."""
    summary = data.groupby(SUMMARY_COLUMNS[:6], as_index=False).agg(
        n_cells=("cell_id", "count"),
        saved_file=("sample_name", lambda values: ""),
        first_cell_id=("cell_id", "first"),
        last_cell_id=("cell_id", "last"),
    )
    return summary[SUMMARY_COLUMNS]


def save_loading_summary(data: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    """Write and return the loading summary without a CSV index."""
    summary = summarize_raw_data(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "raw_data_loading_summary.csv", index=False)
    return summary
