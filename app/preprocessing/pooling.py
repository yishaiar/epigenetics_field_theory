"""Pooling helpers for harmonization inputs."""

from pathlib import Path
import pandas as pd


def pool_csv_files(
    input_files: list[Path],
    output_file: Path | None = None,
    source_column: str | None = None,
    drop_columns: list[str] | None = None,
    metadata_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Concatenate CSV files row-wise and optionally save the pooled table.

    Args:
        input_files: CSV files to concatenate, in the desired row order.
        output_file: Optional destination CSV path. When omitted, no file is written.
        source_column: Optional column populated with each row's input CSV path.
        drop_columns: Optional columns to remove from each input before adding source metadata.
        metadata_columns: Columns excluded from the missing-marker report.

    Returns:
        The pooled table with its index reset and a mapping from each
        all-missing non-metadata column to the affected experiment/sample identifiers.

    Raises:
        ValueError: If ``input_files`` is empty.
        FileNotFoundError: If any input file does not exist.
    """
    if not input_files:
        raise ValueError("At least one input CSV file is required")

    missing_files = [path for path in input_files if not path.is_file()]
    if missing_files:
        missing_paths = ", ".join(str(path) for path in missing_files)
        raise FileNotFoundError(f"Input CSV files do not exist: {missing_paths}")

    frames: list[pd.DataFrame] = []
    missing_columns_by_sample: dict[str, set[str]] = {}
    ignored_columns = set(metadata_columns or [])
    for path in input_files:
        frame = pd.read_csv(path, low_memory=False)
        if drop_columns is not None:
            frame = frame.drop(columns=drop_columns, errors="ignore")
        missing_mask = (
            frame.replace(r"(?i)^\s*(?:none|null|nan|na|n/a)?\s*$", pd.NA, regex=True)
            .isna()
            .to_numpy()
            .all(axis=0)
        )
        columns = [str(column) for column, missing in zip(frame.columns, missing_mask) if missing]
        if {"experiment", "sample_name"}.issubset(frame.columns):
            samples = frame[["experiment", "sample_name"]].drop_duplicates()
            sample_names = (
                (
                    samples["experiment"].astype("string")
                    + "_"
                    + samples["sample_name"].astype("string")
                )
                .dropna()
                .unique()
            )
        else:
            sample_names = [path.stem]
        for column in columns:
            if column not in ignored_columns:
                missing_columns_by_sample.setdefault(column, set()).update(
                    str(sample_name) for sample_name in sample_names
                )
        if source_column is not None:
            frame[source_column] = path.resolve().as_posix()
        frames.append(frame)

    result: dict[str, list[str]] = {
        column: sorted(samples) for column, samples in sorted(missing_columns_by_sample.items())
    }
    pooled = pd.concat(frames, ignore_index=True)
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        pooled.to_csv(output_file, index=False)
    return pooled, result
