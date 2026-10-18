"""Load annotated raw CSV files and summarize their sample provenance."""

from pathlib import Path
from typing import Any

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
        data: Table containing ``experiment``, ``source_file``, and
            ``raw_row_id`` columns.

    Returns:
        A copy of the table with a unique ``cell_uid`` column.

    Raises:
        ValueError: If source identifiers are missing, null, inconsistent, or
            do not produce unique cell UIDs.
    """
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


def _read_annotation_rows(annotation_file: Path) -> pd.DataFrame:
    """Read annotation rows and verify their required columns.

    Args:
        annotation_file: CSV containing cell UIDs, labels, and cluster IDs.

    Returns:
        The loaded annotation table.

    Raises:
        ValueError: If a required annotation column is missing.
    """
    annotation = pd.read_csv(annotation_file, low_memory=False)
    required = {CELL_UID_COLUMN, "labels", "leiden_cluster"}
    missing = required.difference(annotation.columns)
    if missing:
        raise ValueError(f"Annotation map is missing required columns: {sorted(missing)}")
    return annotation


def _build_annotation_lookup(annotation: pd.DataFrame) -> dict[str, tuple[object, object]]:
    """Validate annotation values and index them by stable cell UID.

    Args:
        annotation: Table with unique cell UIDs, supported labels, and integer
            cluster IDs.

    Returns:
        A mapping from string cell UID to its label and cluster ID.

    Raises:
        ValueError: If identifiers or annotation values are invalid.
    """
    if (
        annotation[CELL_UID_COLUMN].isna().to_numpy().any()
        or not annotation[CELL_UID_COLUMN].is_unique
    ):
        raise ValueError("Annotation map cell_uid values must be non-null and unique")
    invalid_labels = ~annotation["labels"].isin(["basal", "classical"])
    if bool(invalid_labels.any()):
        raise ValueError("Annotation map labels must be 'basal' or 'classical'")
    cluster_values = pd.Series(pd.to_numeric(annotation["leiden_cluster"], errors="coerce"))
    invalid_clusters = cluster_values.isna() | (cluster_values.mod(1) != 0)
    if invalid_clusters.to_numpy().any():
        raise ValueError("Annotation map leiden_cluster values must be integers")

    annotation_rows = annotation[[CELL_UID_COLUMN, "labels"]].copy()
    annotation_rows["leiden_cluster"] = cluster_values.astype("Int64")
    return {
        str(uid): (label, cluster)
        for uid, label, cluster in annotation_rows.itertuples(index=False, name=None)
    }


def attach_annotation_labels(data: pd.DataFrame, annotation_file: Path) -> pd.DataFrame:
    """Attach labels and cluster IDs by stable cell UID.

    Validate input UIDs, load and validate the annotation map, align annotations
    to input rows by UID, then mark which rows received annotations. Unmatched
    rows retain missing labels and cluster IDs.

    Args:
        data: Raw table with unique, non-null ``cell_uid`` values.
        annotation_file: CSV containing ``cell_uid``, ``labels``, and
            ``leiden_cluster`` columns.

    Returns:
        A copy of ``data`` with annotation columns added.

    Raises:
        ValueError: If the annotation file is absent, cell UIDs are invalid, or
            annotation identifiers or values violate the required contract.
    """
    result = data.copy()

    # Validate input identifiers before loading the annotation map.
    if (
        CELL_UID_COLUMN not in result.columns
        or result[CELL_UID_COLUMN].isna().to_numpy().any()
        or not result[CELL_UID_COLUMN].is_unique
    ):
        raise ValueError("Raw data cell_uid values must exist, be non-null and unique")

    if not annotation_file.is_file():
        raise ValueError("No annotations file found")

    annotation = _read_annotation_rows(annotation_file)

    # Index validated annotations by UID, then align them to input row order.
    annotation_by_uid = _build_annotation_lookup(annotation)
    annotation_rows = pd.DataFrame(
        {
            CELL_UID_COLUMN: list(annotation_by_uid),
            "labels": [values[0] for values in annotation_by_uid.values()],
            "leiden_cluster": [values[1] for values in annotation_by_uid.values()],
        }
    )
    annotation_rows[CELL_UID_COLUMN] = annotation_rows[CELL_UID_COLUMN].astype("string")
    annotation_rows = annotation_rows.set_index(CELL_UID_COLUMN)
    input_uids = result[CELL_UID_COLUMN].astype("string")
    matched_rows = annotation_rows.reindex(input_uids)

    # Replace prior annotation columns and mark which input rows found a match.
    result = result.drop(
        columns=["labels", "leiden_cluster", "annotation_present"], errors="ignore"
    )
    result["labels"] = pd.array(matched_rows["labels"].to_numpy(), dtype="string")
    result["leiden_cluster"] = pd.array(matched_rows["leiden_cluster"].to_numpy(), dtype="Int64")
    result["annotation_present"] = result["labels"].notna()
    print(len(result[result["annotation_present"]]))
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
