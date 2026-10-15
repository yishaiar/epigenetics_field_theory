"""Filtering and histograms extracted from main1.ipynb cells 16 and 19."""

from collections.abc import Mapping
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def find_cd45_column(csv_file: Path) -> str:
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
    """Save one source-style CD45 histogram."""
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
    """Plot each experiment's CD45 histogram using only the CD45 column."""
    outputs = []
    for experiment in experiments:
        files = sorted((input_dir / experiment).rglob("*_raw_data.csv"))
        if not files:
            raise FileNotFoundError(f"No raw data CSV files found for: {experiment}")
        values = []
        for csv_file in files:
            marker = find_cd45_column(csv_file)
            raw = pd.read_csv(csv_file, usecols=[marker])[marker]
            numeric = pd.to_numeric(raw, errors="coerce").dropna()
            values.append(np.arcsinh(numeric / 5))
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
    """Apply the notebook's valid-value masks and high-sample-driven split."""
    cd45_raw = pd.to_numeric(frame[cd45_col], errors="coerce")
    gfp_raw = pd.to_numeric(frame[gfp_col], errors="coerce")
    valid_mask = cd45_raw.notna() & gfp_raw.notna()
    exp_raw_df = frame.loc[valid_mask]
    cd45_asinh = np.arcsinh(cd45_raw.loc[valid_mask] / 5)
    cd45neg_mask = cd45_asinh <= cd45_cutoff
    exp_cd45neg_df = exp_raw_df.loc[cd45neg_mask]
    gfp_asinh = np.arcsinh(pd.to_numeric(exp_cd45neg_df[gfp_col], errors="coerce") / 5)
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
    """Split valid cells by the executable notebook's CD45 and GFP thresholds."""
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
    summary = pd.DataFrame(rows, columns=["experiment", "sample_name", "n_GFP_high", "n_GFP_low"])
    return all_splits, summary


def save_gfp_split(
    splits: Mapping[tuple[str, str, str], pd.DataFrame], output_dir: Path
) -> list[Path]:
    """Always refresh both CSVs for samples represented in the GFP-high split."""
    outputs = []
    for (experiment, sample_name, group), data in splits.items():
        target = output_dir / experiment / group / f"{sample_name}_{group}.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(target, index=False)
        outputs.append(target)
    return outputs


def _save_gfp_histogram(values: pd.Series, experiment: str, cutoff: float, target: Path) -> None:
    """Save one source-style GFP histogram after CD45 exclusion."""
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(values, bins=300, histtype="step", linewidth=1.5)
    ax.axvline(cutoff, linestyle="--", linewidth=2, label=f"GFP cutoff = {cutoff}")
    ax.set_xlim(np.nanpercentile(values, 0.1), np.nanpercentile(values, 99.9))
    ax.set_title(f"{experiment} | GFP after CD45 exclusion")
    ax.set_xlabel("GFP arcsinh(GFP / 5)")
    ax.set_ylabel("CD45-negative cell count")
    ax.legend()
    fig.tight_layout()
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=300)
    plt.close(fig)


def plot_gfp_histograms(
    data: pd.DataFrame,
    experiments: list[str],
    gfp_cutoffs: Mapping[str, float],
    output_dir: Path,
    cd45_cutoff: float = 2.0,
) -> pd.DataFrame:
    """Plot source-notebook GFP distributions and return its per-experiment summary."""
    cd45_col = find_marker_column(data, "CD45")
    gfp_col = find_marker_column(data, "GFP")
    rows = []
    for experiment in experiments:
        frame = data.loc[data["experiment"] == experiment]
        if frame.empty:
            raise ValueError(f"No cells found for experiment: {experiment}")
        cd45_raw = pd.to_numeric(frame[cd45_col], errors="coerce")
        gfp_raw = pd.to_numeric(frame[gfp_col], errors="coerce")
        valid_mask = cd45_raw.notna() & gfp_raw.notna()
        cd45_asinh = np.arcsinh(cd45_raw.loc[valid_mask] / 5)
        kept = cd45_asinh <= cd45_cutoff
        values = np.arcsinh(gfp_raw.loc[valid_mask].loc[kept] / 5)
        target = output_dir / f"{experiment}_GFP_histogram_CD45neg.png"
        _save_gfp_histogram(values, experiment, gfp_cutoffs[experiment], target)
        rows.append(
            {
                "experiment": experiment,
                "cd45_cutoff_asinh": cd45_cutoff,
                "gfp_cutoff_asinh_shown": gfp_cutoffs[experiment],
                "n_total_valid": len(cd45_asinh),
                "n_cd45neg_kept": len(values),
                "n_cd45pos_excluded": len(cd45_asinh) - len(values),
                "plot_file": str(target),
            }
        )
    return pd.DataFrame(rows)
