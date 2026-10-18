"""Embedding and coordinate export copied from the active main1.ipynb cells."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import umap.umap_ as umap

from app.metadata import METADATA_EXCLUSION_COLUMNS


def safe_name(value: object) -> str:
    """Convert a value to a filename-safe string.

    Args:
        value: Value to stringify and sanitize.

    Returns:
        A string with unsafe filename characters and whitespace replaced.
    """
    name = re.sub(r'[<>:"/\\|?*]', "_", str(value))
    return re.sub(r"\s+", "_", name)


def get_umap_markers(data: pd.DataFrame, marker_list: list[str]) -> tuple[list[str], list[str]]:
    """Separate requested markers into usable and missing or empty columns.

    Args:
        data: Table searched for marker columns.
        marker_list: Marker names to check, in desired order.

    Returns:
        Two lists: usable marker names, then absent, metadata, or nonnumeric names.
    """
    available, missing = [], []
    for marker in marker_list:
        if marker not in data.columns or marker in METADATA_EXCLUSION_COLUMNS:
            missing.append(marker)
            continue
        values = pd.Series(pd.to_numeric(pd.Series(data[marker]), errors="coerce"), dtype=float)
        (available if values.notna().any() else missing).append(marker)
    return available, missing


def get_axis_limits(
    x: np.ndarray, y: np.ndarray, pad_frac: float = 0.08
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Calculate coordinate bounds with proportional padding.

    Args:
        x: Horizontal coordinates.
        y: Vertical coordinates.
        pad_frac: Fraction of each coordinate range added at both ends.

    Returns:
        The padded x limits and padded y limits.
    """
    x_min, x_max, y_min, y_max = np.nanmin(x), np.nanmax(x), np.nanmin(y), np.nanmax(y)
    x_range, y_range = x_max - x_min, y_max - y_min
    x_range = 1 if x_range == 0 else x_range
    y_range = 1 if y_range == 0 else y_range
    return (
        (x_min - x_range * pad_frac, x_max + x_range * pad_frac),
        (y_min - y_range * pad_frac, y_max + y_range * pad_frac),
    )


def plot_full_umap(data: pd.DataFrame, experiment: str, group: str, out_file: Path) -> None:
    """Save and display a scatter plot of all supplied UMAP coordinates.

    Args:
        data: Table containing ``UMAP1`` and ``UMAP2`` columns.
        experiment: Experiment label used in the plot title.
        group: Marker group used in the plot title.
        out_file: Destination image path.
    """
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.scatter(data["UMAP1"], data["UMAP2"], s=4, c="black", alpha=0.75, linewidths=0)
    ax.set(
        title=f"{experiment} — {group}",
        xlabel="UMAP1",
        ylabel="UMAP2",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def plot_condition_umap(
    data: pd.DataFrame,
    experiment: str,
    group: str,
    condition_order: dict[str, list[str]],
    out_file: Path,
) -> None:
    """Save and display UMAP panels for conditions in the configured order.

    Args:
        data: Table containing coordinates and a ``condition`` column.
        experiment: Experiment whose configured condition order is selected.
        group: Marker group used in the plot title.
        condition_order: Mapping from experiment names to ordered conditions.
        out_file: Destination image path.
    """
    xlim, ylim = get_axis_limits(data["UMAP1"].to_numpy(), data["UMAP2"].to_numpy())
    order = (
        list(dict.fromkeys(c for values in condition_order.values() for c in values))
        if experiment == "all"
        else condition_order[experiment]
    )
    present = [condition for condition in order if condition in data["condition"].unique()]
    fig, axes = plt.subplots(
        len(present), 1, figsize=(8, 6 * len(present)), sharex=True, sharey=True
    )
    axes = [axes] if len(present) == 1 else axes
    for ax, condition in zip(axes, present):
        subset = data[data["condition"] == condition]
        ax.scatter(subset["UMAP1"], subset["UMAP2"], s=4, c="black", alpha=0.75, linewidths=0)
        ax.set(title=condition, xlabel="UMAP1", ylabel="UMAP2", xlim=xlim, ylim=ylim)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.suptitle(f"{experiment} — {group} by condition", fontsize=15, y=1.01)
    plt.tight_layout()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def calculate_umap(
    data: pd.DataFrame,
    marker_cols: list[str],
    group: str,
    experiment: str,
    condition_order: dict[str, list[str]],
    output_root: Path,
    n_neighbors: int = 15,
    min_dist: float = 0.001,
    random_state: int = 42,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Fit UMAP and export coordinates, plots, and a run summary.

    Args:
        data: Cells-by-metadata-and-marker table.
        marker_cols: Numeric columns used to fit the embedding.
        group: Marker group name recorded in outputs.
        experiment: Experiment name recorded in outputs.
        condition_order: Mapping from experiment names to ordered conditions.
        output_root: Root directory for coordinate and plot artifacts.
        n_neighbors: UMAP neighborhood size.
        min_dist: Minimum spacing between embedded points.
        random_state: Random seed for reproducible fitting.

    Returns:
        A copy of the input table with UMAP columns and an artifact summary.

    Raises:
        ValueError: If no marker columns are supplied or their values are missing.
    """
    if not marker_cols:
        raise ValueError(f"No usable {group} markers found for {experiment}")
    matrix = data[marker_cols].apply(pd.to_numeric, errors="coerce")
    missing_matrix = matrix.isna().to_numpy()
    if missing_matrix.any().any():
        bad_columns = matrix.columns[missing_matrix.any(axis=0)].tolist()
        raise ValueError(f"NaN values found in UMAP matrix for {experiment}: {bad_columns}")
    model = umap.UMAP(
        n_neighbors=n_neighbors, min_dist=min_dist, metric="euclidean", random_state=random_state
    )
    embedding = np.asarray(model.fit_transform(matrix.to_numpy(dtype=float)), dtype=float)
    embedded = data.assign(UMAP1=embedding[:, 0], UMAP2=embedding[:, 1], UMAP_marker_group=group)
    all_coords, per_sample = _save_coordinates(embedded, output_root, group, experiment)
    full_plot, condition_plot = _save_embedding_plots(
        embedded, output_root, group, experiment, condition_order
    )
    summary = _embedding_summary(
        len(embedded),
        group,
        experiment,
        marker_cols,
        full_plot,
        condition_plot,
        all_coords,
        per_sample,
    )
    return embedded, summary


def _save_coordinates(
    embedded: pd.DataFrame, output_root: Path, group: str, experiment: str
) -> tuple[Path, Path]:
    """Save pooled coordinates and one coordinate CSV per sample.

    Args:
        embedded: Cell table containing UMAP coordinates and ``sample_name``.
        output_root: Root directory for embedding artifacts.
        group: Marker group used in the output directory and filenames.
        experiment: Experiment used in the output directory and filenames.

    Returns:
        The pooled coordinate file path and per-sample directory path.
    """
    base = (
        output_root
        / "6. plots - GFP+ analyses"
        / "GFP_high_balanced_ZSCORED_UMAP_by_marker_group"
        / f"UMAP_{group}"
    )
    coords_dir = base / "coordinates" / experiment
    coords_dir.mkdir(parents=True, exist_ok=True)
    all_coords = coords_dir / f"{experiment}_{group}_UMAP_coordinates_all_cells.csv"
    embedded.to_csv(all_coords, index=False)
    per_sample = coords_dir / "per_sample"
    per_sample.mkdir(parents=True, exist_ok=True)
    for sample_name, subset in embedded.groupby("sample_name"):
        subset.to_csv(
            per_sample / f"{safe_name(sample_name)}_{group}_UMAP_coordinates.csv", index=False
        )
    return all_coords, per_sample


def _save_embedding_plots(
    embedded: pd.DataFrame,
    output_root: Path,
    group: str,
    experiment: str,
    condition_order: dict[str, list[str]],
) -> tuple[Path, Path]:
    """Save full and condition-split UMAP plots.

    Args:
        embedded: Cell table containing UMAP coordinates and conditions.
        output_root: Root directory for embedding artifacts.
        group: Marker group used in the output directory and filenames.
        experiment: Experiment used in plot titles and filenames.
        condition_order: Ordered conditions for each experiment.

    Returns:
        The full-embedding plot path and condition-split plot path.
    """
    plots_dir = (
        output_root
        / "6. plots - GFP+ analyses"
        / "GFP_high_balanced_ZSCORED_UMAP_by_marker_group"
        / f"UMAP_{group}"
        / "plots"
    )
    full_plot, condition_plot = (
        plots_dir / f"{experiment}_{group}_UMAP_all_cells.png",
        plots_dir / f"{experiment}_{group}_UMAP_by_condition.png",
    )
    plot_full_umap(embedded, experiment, group, full_plot)
    plot_condition_umap(embedded, experiment, group, condition_order, condition_plot)
    return full_plot, condition_plot


def _embedding_summary(
    n_cells: int,
    group: str,
    experiment: str,
    marker_cols: list[str],
    full_plot: Path,
    condition_plot: Path,
    all_coords: Path,
    per_sample: Path,
) -> dict[str, object]:
    """Build the output record describing one embedding run.

    Args:
        n_cells: Number of cells included in the embedding.
        group: Marker group used to fit the embedding.
        experiment: Experiment represented by the embedding.
        marker_cols: Marker columns used to fit the embedding.
        full_plot: Path to the full UMAP plot.
        condition_plot: Path to the condition-split UMAP plot.
        all_coords: Path to the pooled coordinate CSV.
        per_sample: Directory containing per-sample coordinate CSVs.

    Returns:
        A summary record containing run metadata and artifact paths.
    """
    return {
        "marker_group": group,
        "experiment": experiment,
        "n_cells": n_cells,
        "n_markers_used": len(marker_cols),
        "markers_used": ", ".join(marker_cols),
        "full_umap_plot": str(full_plot),
        "condition_umap_plot": str(condition_plot),
        "all_coordinates_file": str(all_coords),
        "per_sample_coordinates_dir": str(per_sample),
    }


def load_umap(umap_root: Path, experiment: str, marker_group: str) -> pd.DataFrame:
    """Load an experiment's pooled UMAP coordinate CSV.

    Args:
        umap_root: Root containing the ``UMAP_<marker_group>`` directories.
        experiment: Experiment name used in the coordinate filename.
        marker_group: Marker group directory and filename component.

    Returns:
        The coordinate table read from CSV.

    Raises:
        FileNotFoundError: If the expected coordinate file does not exist.
    """
    path = (
        umap_root
        / f"UMAP_{marker_group}"
        / "coordinates"
        / experiment
        / f"{experiment}_{marker_group}_UMAP_coordinates_all_cells.csv"
    )
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, low_memory=False)
