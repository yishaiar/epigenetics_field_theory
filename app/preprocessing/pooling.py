"""Pool CSV files and report columns containing only missing values."""

from pathlib import Path

import pandas as pd


def pool_csv_files(
    input_files: list[Path],
    output_file: Path | None = None,
    source_column: str | None = None,
    drop_columns: list[str] | None = None,
    metadata_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Concatenate CSV files and map each all-missing marker to its samples."""
    if not input_files:
        raise ValueError("At least one input CSV file is required")

    missing_files = [path for path in input_files if not path.is_file()]
    if missing_files:
        raise FileNotFoundError(", ".join(str(path) for path in missing_files))

    frames: list[pd.DataFrame] = []
    missing_by_column: dict[str, set[str]] = {}
    metadata = set(metadata_columns or [])

    for path in input_files:
        frame = pd.read_csv(path, low_memory=False)
        if drop_columns is not None:
            frame = frame.drop(columns=drop_columns, errors="ignore")

        missing_values = (
            frame.replace(r"(?i)^\s*(?:none|null|nan|na|n/a)?\s*$", pd.NA, regex=True)
            .isna()
            .to_numpy()
            .all(axis=0)
        )
        missing_columns = [
            str(column) for column, missing in zip(frame.columns, missing_values) if missing
        ]
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

        for column in missing_columns:
            if column not in metadata:
                missing_by_column.setdefault(column, set()).update(
                    str(sample_name) for sample_name in sample_names
                )

        if source_column is not None:
            frame[source_column] = path.resolve().as_posix()
        frames.append(frame)

    pooled = pd.concat(frames, ignore_index=True)
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        pooled.to_csv(output_file, index=False)

    report = {column: sorted(samples) for column, samples in sorted(missing_by_column.items())}
    return pooled, report
