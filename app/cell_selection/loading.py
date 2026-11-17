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


CELL_UID_COLUMN = "cell_uid"


def _normalized_source_name(experiment: object, source_file: object) -> str:
    """Remove a source filename extension and ensure it includes its experiment.

    Args:
        experiment: Experiment identifier used as the filename prefix.
        source_file: Source filename, with or without an extension.

    Returns:
        The filename stem prefixed by the experiment exactly once.
    """
    experiment_name = str(experiment)
    source_name = Path(str(source_file)).stem
    if source_name == experiment_name or source_name.startswith(f"{experiment_name}_"):
        return source_name
    return f"{experiment_name}_{source_name}"


def add_cell_uid(data: pd.DataFrame) -> pd.DataFrame:
    """Add or validate stable cell identifiers from source metadata.

    Args:
        data: Table with source fields when ``cell_uid`` is absent, or with
            existing cell UIDs to validate.

    Returns:
        A copy of the table with a unique ``cell_uid`` column.

    Raises:
        ValueError: If required source fields are missing, identifiers contain
            nulls, existing UIDs disagree with source fields, or UIDs are not
            unique.
    """
    if CELL_UID_COLUMN in data:
        if data[CELL_UID_COLUMN].isna().to_numpy().any() or not data[CELL_UID_COLUMN].is_unique:
            raise ValueError("Existing cell_uid values must be non-null and unique")
        required_source_columns = {"experiment", "source_file", "raw_row_id"}
        if not required_source_columns.issubset(data.columns):
            return data.copy()

    required = {"experiment", "source_file", "raw_row_id"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Raw data is missing cell UID source columns: {sorted(missing)}")
    source_values = data.loc[:, ["experiment", "source_file", "raw_row_id"]]
    if source_values.isna().to_numpy().any():
        raise ValueError("Cell UID source columns must not contain missing values")
    result = data.copy()
    uid_values: list[str] = [
        f"{_normalized_source_name(experiment, source_file)}_{raw_row_id}"
        for experiment, source_file, raw_row_id in source_values.itertuples(index=False, name=None)
    ]
    if CELL_UID_COLUMN in data.columns:
        if data[CELL_UID_COLUMN].tolist() != uid_values:
            raise ValueError("Existing cell_uid values do not match their source identifiers")
        return data.copy()
    result[CELL_UID_COLUMN] = uid_values
    if not result[CELL_UID_COLUMN].is_unique:
        raise ValueError("Generated cell_uid values are not unique")
    return result


def load_raw_data(
    input_dir: Path,
    experiments: list[str],
) -> pd.DataFrame:
    """Load raw CSV files for the requested experiments.

    Files are read in sorted path order within each experiment.

    Args:
        input_dir: Root directory containing experiment subdirectories.
        experiments: Experiment names to load, in desired concatenation order.

    Returns:
        A concatenated table with its row index reset.

    Raises:
        FileNotFoundError: If ``input_dir`` is not a directory.
        ValueError: If no matching raw data files are found.
    """
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
            if "experiment" not in df_file:
                df_file["experiment"] = experiment
            else:
                df_file["experiment"] = df_file["experiment"].where(
                    df_file["experiment"].notna(), experiment
                )
            df_file = df_file.drop(columns="batch", errors="ignore")
            all_experiment_dfs.append(df_file)
    if not all_experiment_dfs:
        raise ValueError(f"No '_raw_data.csv' files found inside {input_dir}")
    return pd.concat(all_experiment_dfs, ignore_index=True)


def summarize_raw_data(data: pd.DataFrame) -> pd.DataFrame:
    """Summarize cell counts and cell ID bounds for each source file.

    Args:
        data: Raw cell table containing the summary grouping columns and
            ``cell_id``.

    Returns:
        A table with one row per experiment, condition, sample, replicate, and
        source file.
    """
    summary = data.groupby(SUMMARY_COLUMNS[:6], as_index=False).agg(
        n_cells=("cell_id", "count"),
        saved_file=("sample_name", lambda values: ""),
        first_cell_id=("cell_id", "first"),
        last_cell_id=("cell_id", "last"),
    )
    result: pd.DataFrame = summary.loc[:, SUMMARY_COLUMNS]
    return result


def save_loading_summary(data: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    """Write the raw data loading summary to CSV.

    Args:
        data: Raw cell table passed to :func:`summarize_raw_data`.
        output_dir: Directory where the summary CSV will be written.

    Returns:
        The summary table written to ``raw_data_loading_summary.csv``.
    """
    summary = summarize_raw_data(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "raw_data_loading_summary.csv", index=False)
    return summary
