"""Build a deterministic, small raw-data fixture for workflow smoke runs."""

import argparse
from pathlib import Path

import pandas as pd

EXPERIMENTS = ["batch2", "batch3", "batch4_extra_treatment"]

REQUIRED_DEMO_COLUMNS = {
    "cell_id",
    "experiment",
    "sample_name",
    "condition",
    "replicate",
    "source_file",
    "source_path",
    "raw_row_id",
}


def generate_demo_dataset(
    source_dir: Path,
    output_dir: Path,
    experiments: list[str],
    cells_per_sample: int = 100,
    random_state: int = 42,
) -> pd.DataFrame:
    """Write a reproducible row sample from every raw CSV in each experiment.

    Args:
        source_dir: Root containing experiment directories and raw CSV files.
        output_dir: Separate root where sampled files and their manifest are written.
        experiments: Experiment directory names to include, in desired order.
        cells_per_sample: Exact number of rows selected from each source file.
        random_state: Seed used independently for each source file.

    Returns:
        A manifest with one row per source file and its source and demo row counts.

    Raises:
        FileNotFoundError: If the source directory or a requested experiment is absent.
        ValueError: If arguments, source schemas, sample sizes, or output location are invalid.
    """
    source_root = source_dir.resolve()
    output_root = output_dir.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Raw data folder not found: {source_dir}")
    if output_root == source_root or source_root in output_root.parents:
        raise ValueError("Demo output directory must be separate from and outside raw data")
    if cells_per_sample < 1:
        raise ValueError("cells_per_sample must be a positive integer")
    if random_state < 0:
        raise ValueError("random_state must be non-negative")
    if not experiments:
        raise ValueError("At least one experiment must be requested")

    source_files: list[tuple[str, Path]] = []
    for experiment in experiments:
        experiment_dir = source_root / experiment
        if not experiment_dir.is_dir():
            raise FileNotFoundError(f"Experiment folder not found: {experiment_dir}")
        experiment_files = sorted(experiment_dir.rglob("*_raw_data.csv"))
        if not experiment_files:
            raise ValueError(f"No '_raw_data.csv' files found inside {experiment_dir}")
        source_files.extend((experiment, source_file) for source_file in experiment_files)

    expected_outputs = {
        output_root / source_file.relative_to(source_root) for _, source_file in source_files
    }
    existing_outputs = set(output_root.rglob("*_raw_data.csv")) if output_root.exists() else set()
    unexpected_outputs = existing_outputs.difference(expected_outputs)
    if unexpected_outputs:
        unexpected_names = sorted(str(path.relative_to(output_root)) for path in unexpected_outputs)
        raise ValueError(f"Unexpected stale demo CSV files exist: {unexpected_names}")

    manifest_rows: list[dict[str, object]] = []
    for sample_index, (experiment, source_file) in enumerate(source_files):
        source_frame = pd.read_csv(source_file, low_memory=False)
        missing = REQUIRED_DEMO_COLUMNS.difference(source_frame.columns)
        if missing:
            raise ValueError(
                f"Raw file {source_file} is missing required columns: {sorted(missing)}"
            )
        if len(source_frame) < cells_per_sample:
            raise ValueError(
                f"Raw file {source_file} has {len(source_frame)} rows, fewer than "
                f"the requested {cells_per_sample}"
            )

        sample_seed = random_state + sample_index
        sampled = source_frame.sample(n=cells_per_sample, random_state=sample_seed).sort_index()
        relative_path = source_file.relative_to(source_root)
        demo_file = output_root / relative_path
        demo_file.parent.mkdir(parents=True, exist_ok=True)
        sampled.to_csv(demo_file, index=False)
        manifest_rows.append(
            {
                "experiment": experiment,
                "source_file": str(relative_path),
                "demo_file": str(relative_path),
                "source_cells": len(source_frame),
                "demo_cells": len(sampled),
                "random_state": sample_seed,
            }
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = output_root.parent / "demo_dataset_manifest.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_path, index=False)
    return manifest


def main() -> None:
    """Generate the local demo fixture using the standard project locations."""
    from app.dotenv import data_dir, project_dir

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=data_dir)
    parser.add_argument("--output-dir", type=Path, default=project_dir / "demo_data" / "raw_data")
    parser.add_argument("--cells-per-sample", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    arguments = parser.parse_args()
    manifest = generate_demo_dataset(
        arguments.source_dir,
        arguments.output_dir,
        EXPERIMENTS,
        arguments.cells_per_sample,
        arguments.random_state,
    )
    print(f"Generated {len(manifest)} sample files with {int(manifest['demo_cells'].sum())} cells")


if __name__ == "__main__":
    main()
