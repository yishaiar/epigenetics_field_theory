"""Filtering and histograms extracted from main1.ipynb cells 16 and 19."""

from collections.abc import Mapping
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _numeric_series(data: pd.DataFrame, column: str) -> pd.Series:
    """Return one DataFrame column coerced to a numeric Pandas Series."""
    return pd.Series(pd.to_numeric(pd.Series(data[column]), errors="coerce"), dtype=float)


def find_cd45_column(csv_file: Path) -> str:
    """Find the CD45 column in a CSV header.

    Matching prefers an exact case-insensitive name, then a prefix, then a
    substring.

    Args:
        csv_file: CSV file whose header will be inspected.

    Returns:
        The original column name matching CD45.

    Raises:
        ValueError: If the header contains no CD45 column.
    """
    cols = pd.read_csv(csv_file, nrows=0).columns.tolist()
    exact = [c for c in cols if c.lower() == "cd45"]
    if exact:
        return exact[0]
    starts = [c for c in cols if c.lower().startswith("cd45")]
    if starts:
        return starts[0]
    contains = [c for c in cols if "cd45" in c.lower()]
    if contains:
        return contains[0]
    raise ValueError(f"No CD45 column found in: {csv_file}")


def find_marker_column(df: pd.DataFrame, marker: str) -> str:
    """Find a marker column by exact name, prefix, or substring.

    Matching is case-insensitive and returns the first match at the strongest
    matching level.

    Args:
        df: Table whose columns will be searched.
        marker: Marker name to find.

    Returns:
        The original column name matching the marker.

    Raises:
        ValueError: If no column matches the marker.
    """
    cols = list(df.columns)
    exact = [c for c in cols if c.lower() == marker.lower()]
    if exact:
        return exact[0]
    starts = [c for c in cols if c.lower().startswith(marker.lower())]
    if starts:
        return starts[0]
    contains = [c for c in cols if marker.lower() in c.lower()]
    if contains:
        return contains[0]
    raise ValueError(f"Could not find marker column: {marker}")


def _save_cd45_histogram(
    values: pd.Series, experiment: str, cutoff: float, output_dir: Path
) -> Path:
    """Save a histogram of transformed CD45 values and return its path.

    Args:
        values: Transformed CD45 values to plot.
        experiment: Experiment name used in the plot title and filename.
        cutoff: Transformed CD45 cutoff shown on the plot.
        output_dir: Root directory for the histogram image.

    Returns:
        The path to the saved histogram image.
    """
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(values, bins=300, histtype="step", linewidth=1.5)
    ax.axvline(cutoff, linestyle="--", linewidth=2, label=f"Arbitrary cutoff = {cutoff}")
    ax.set_title(f"{experiment} — CD45 histogram")
    ax.set_xlabel("CD45 arcsinh(CD45 / 5)")
    ax.set_ylabel("Cell count")
    ax.legend()
    fig.tight_layout()
    target = output_dir / f"{experiment}_CD45_histogram_arcsinh5.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=300)
    plt.close(fig)
    return target


def plot_cd45_histograms(
    input_dir: Path, experiments: list[str], output_dir: Path, cutoffs: Mapping[str, float]
) -> list[Path]:
    """Plot and save a CD45 distribution for each experiment.

    Args:
        input_dir: Root containing experiment raw data directories.
        experiments: Experiment names to process.
        output_dir: Destination directory for histogram images.
        cutoffs: CD45 cutoff for each experiment, in transformed units.

    Returns:
        Paths to the saved histogram images.

    Raises:
        FileNotFoundError: If an experiment has no matching raw CSV files.
        KeyError: If a cutoff is not provided for an experiment.
    """
    outputs = []
    for experiment in experiments:
        files = sorted((input_dir / experiment).rglob("*_raw_data.csv"))
        if not files:
            raise FileNotFoundError(f"No raw data CSV files found for: {experiment}")
        values: list[pd.Series] = []
        for csv_file in files:
            marker = find_cd45_column(csv_file)
            raw = pd.read_csv(csv_file, usecols=lambda column: column == marker, low_memory=False)
            numeric = _numeric_series(raw, marker).dropna()
            values.append(pd.Series(np.arcsinh(numeric / 5), index=numeric.index, dtype=float))
        outputs.append(
            _save_cd45_histogram(
                pd.concat(values, ignore_index=True), experiment, cutoffs[experiment], output_dir
            )
        )
    return outputs


def _split_experiment(
    frame: pd.DataFrame,
    experiment: str,
    cd45_col: str,
    gfp_col: str,
    cd45_cutoff: float,
    gfp_cutoff: float,
) -> tuple[dict[tuple[str, str, str], pd.DataFrame], list[dict[str, object]]]:
    """Filter one experiment and split each represented sample by GFP level.

    CD45 and GFP values are coerced to numeric values, and rows missing either
    value are discarded. CD45 is transformed with ``arcsinh(value / 5)``;
    only rows at or below ``cd45_cutoff`` continue. Their GFP values receive
    the same transform and are split at ``gfp_cutoff``. A sample is included
    only when it has at least one GFP-high row; its GFP-low rows are included
    alongside the high rows.

    Args:
        frame: Rows for a single experiment, including ``sample_name`` and the
            selected CD45 and GFP columns.
        experiment: Experiment identifier used in split keys and summary rows.
        cd45_col: Name of the CD45 column in ``frame``.
        gfp_col: Name of the GFP column in ``frame``.
        cd45_cutoff: Maximum transformed CD45 value retained.
        gfp_cutoff: Minimum transformed GFP value classified as high.

    Returns:
        A pair containing split DataFrames keyed by
        ``(experiment, sample_name, group)`` and summary records with high and
        low cell counts for each included sample.
    """
    # Keep rows with numeric values for both markers.
    cd45_raw = _numeric_series(frame, cd45_col)
    gfp_raw = _numeric_series(frame, gfp_col)
    valid_mask = cd45_raw.notna() & gfp_raw.notna()
    exp_raw_df = pd.DataFrame(frame.loc[valid_mask])
    cd45_valid = cd45_raw.loc[valid_mask]
    cd45_asinh = pd.Series(
        np.arcsinh(cd45_valid.to_numpy(dtype=float) / 5), index=cd45_valid.index, dtype=float
    )
    # Apply the CD45-negative gate in transformed units.
    cd45neg_mask = cd45_asinh <= cd45_cutoff
    exp_cd45neg_df = exp_raw_df.loc[cd45neg_mask]
    gfp_cd45neg = _numeric_series(exp_cd45neg_df, gfp_col)
    gfp_asinh = pd.Series(
        np.arcsinh(gfp_cd45neg.to_numpy(dtype=float) / 5),
        index=gfp_cd45neg.index,
        dtype=float,
    )
    # Split retained rows by GFP and assemble per-sample outputs.
    gfppos_mask = gfp_asinh >= gfp_cutoff
    gfp_pos_df = exp_cd45neg_df.loc[gfppos_mask]
    gfp_neg_df = exp_cd45neg_df.loc[~gfppos_mask]
    splits = {}
    rows = []
    for sample_name in gfp_pos_df["sample_name"].unique():
        high = gfp_pos_df.loc[gfp_pos_df["sample_name"] == sample_name]
        low = gfp_neg_df.loc[gfp_neg_df["sample_name"] == sample_name]
        splits[(experiment, str(sample_name), "GFP_low")] = low
        splits[(experiment, str(sample_name), "GFP_high")] = high
        rows.append(
            {
                "experiment": experiment,
                "sample_name": sample_name,
                "n_GFP_high": len(high),
                "n_GFP_low": len(low),
            }
        )
    return splits, rows


def split_cells_by_gfp(
    data: pd.DataFrame,
    experiments: list[str],
    gfp_cutoffs: Mapping[str, float],
    cd45_cutoff: float = 2.0,
) -> tuple[dict[tuple[str, str, str], pd.DataFrame], pd.DataFrame]:
    """Split valid cells by CD45 and experiment-specific GFP cutoffs.

    Args:
        data: Cell table with experiment, sample, CD45, and GFP values.
        experiments: Experiment names to split.
        gfp_cutoffs: GFP cutoff for each experiment, in transformed units.
        cd45_cutoff: CD45 exclusion cutoff, in transformed units.

    Returns:
        A mapping keyed by experiment, sample, and GFP group, and a per-sample
        high/low cell count table.

    Raises:
        ValueError: If an experiment has no cells in ``data``.
        KeyError: If a GFP cutoff is not provided for an experiment.
    """
    cd45_col = find_marker_column(data, "CD45")
    gfp_col = find_marker_column(data, "GFP")
    all_splits = {}
    rows = []
    for experiment in experiments:
        exp_df = data.loc[data["experiment"] == experiment].copy()
        if exp_df.empty:
            raise ValueError(f"No cells found for experiment: {experiment}")
        splits, exp_rows = _split_experiment(
            exp_df, experiment, cd45_col, gfp_col, cd45_cutoff, gfp_cutoffs[experiment]
        )
        all_splits.update(splits)
        rows.extend(exp_rows)
    summary = pd.DataFrame(
        rows,
        columns=pd.Index(["experiment", "sample_name", "n_GFP_high", "n_GFP_low"]),
    )
    return all_splits, summary


def save_gfp_split(
    splits: Mapping[tuple[str, str, str], pd.DataFrame], output_dir: Path
) -> list[Path]:
    """Write each supplied GFP split table to its experiment/group path.

    Args:
        splits: Tables keyed by experiment, sample name, and GFP group.
        output_dir: Root directory for the split CSV files.

    Returns:
        Paths to the CSV files written.
    """
    outputs = []
    for (experiment, sample_name, group), data in splits.items():
        target = output_dir / experiment / group / f"{sample_name}_{group}.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(target, index=False)
        outputs.append(target)
    return outputs


def _save_gfp_histogram(values: pd.Series, experiment: str, cutoff: float, target: Path) -> None:
    """Save a histogram of transformed GFP values after CD45 exclusion.

    Args:
        values: Transformed GFP values to plot.
        experiment: Experiment name used in the plot title.
        cutoff: Transformed GFP cutoff shown on the plot.
        target: Destination path for the histogram image.
    """
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(values, bins=300, histtype="step", linewidth=1.5)
    ax.axvline(cutoff, linestyle="--", linewidth=2, label=f"GFP cutoff = {cutoff}")
    ax.set_xlim(float(np.nanpercentile(values, 0.1)), float(np.nanpercentile(values, 99.9)))
    ax.set_title(f"{experiment} | GFP after CD45 exclusion")
    ax.set_xlabel("GFP arcsinh(GFP / 5)")
    ax.set_ylabel("CD45-negative cell count")
    ax.legend()
    fig.tight_layout()
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=300)
    plt.close(fig)


def _plot_experiment_gfp_histogram(
    frame: pd.DataFrame,
    experiment: str,
    cd45_col: str,
    gfp_col: str,
    cd45_cutoff: float,
    gfp_cutoff: float,
    output_dir: Path,
) -> dict[str, object]:
    """Filter one experiment by CD45, save its GFP histogram, and summarize it.

    Args:
        frame: Rows for one experiment, including the selected marker columns.
        experiment: Experiment identifier used in the output filename and row.
        cd45_col: Selected CD45 column name.
        gfp_col: Selected GFP column name.
        cd45_cutoff: Maximum transformed CD45 value retained.
        gfp_cutoff: GFP cutoff shown on the histogram.
        output_dir: Destination directory for the histogram image.

    Returns:
        Summary fields for valid, retained, and excluded cells and the plot path.
    """
    cd45_raw = _numeric_series(frame, cd45_col)
    gfp_raw = _numeric_series(frame, gfp_col)
    valid_mask = cd45_raw.notna() & gfp_raw.notna()
    cd45_valid = cd45_raw.loc[valid_mask]
    gfp_valid = gfp_raw.loc[valid_mask]
    cd45_asinh = pd.Series(
        np.arcsinh(cd45_valid.to_numpy(dtype=float) / 5),
        index=cd45_valid.index,
        dtype=float,
    )
    gfp_cd45neg = gfp_valid.loc[cd45_asinh <= cd45_cutoff]
    values = pd.Series(
        np.arcsinh(gfp_cd45neg.to_numpy(dtype=float) / 5),
        index=gfp_cd45neg.index,
        dtype=float,
    )
    target = output_dir / f"{experiment}_GFP_histogram_CD45neg.png"
    _save_gfp_histogram(values, experiment, gfp_cutoff, target)
    return {
        "experiment": experiment,
        "cd45_cutoff_asinh": cd45_cutoff,
        "gfp_cutoff_asinh_shown": gfp_cutoff,
        "n_total_valid": len(cd45_asinh),
        "n_cd45neg_kept": len(values),
        "n_cd45pos_excluded": len(cd45_asinh) - len(values),
        "plot_file": str(target),
    }


def plot_gfp_histograms(
    data: pd.DataFrame,
    experiments: list[str],
    gfp_cutoffs: Mapping[str, float],
    output_dir: Path,
    cd45_cutoff: float = 2.0,
) -> pd.DataFrame:
    """Plot GFP distributions after CD45 exclusion for each experiment.

    Args:
        data: Cell table with experiment, CD45, GFP, and sample columns.
        experiments: Experiment names to plot.
        gfp_cutoffs: GFP cutoff for each experiment, in transformed units.
        output_dir: Destination directory for histogram images.
        cd45_cutoff: CD45 exclusion cutoff, in transformed units.

    Returns:
        Per-experiment counts and the paths of saved plot files.

    Raises:
        ValueError: If an experiment has no cells in ``data``.
        KeyError: If a GFP cutoff is not provided for an experiment.
    """
    cd45_col = find_marker_column(data, "CD45")
    gfp_col = find_marker_column(data, "GFP")
    rows = []
    for experiment in experiments:
        frame = data.loc[data["experiment"] == experiment]
        if frame.empty:
            raise ValueError(f"No cells found for experiment: {experiment}")
        rows.append(
            _plot_experiment_gfp_histogram(
                frame,
                experiment,
                cd45_col,
                gfp_col,
                cd45_cutoff,
                gfp_cutoffs[experiment],
                output_dir,
            )
        )
    return pd.DataFrame(rows)
