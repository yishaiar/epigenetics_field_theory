"""Embedding and coordinate export copied from the active main1.ipynb cells."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import umap.umap_ as umap


def safe_name(value: object) -> str:
    """Return the source notebook's filesystem-safe sample name."""
    name = re.sub(r'[<>:"/\\|?*]', "_", str(value))
    return re.sub(r"\s+", "_", name)


def get_umap_markers(data: pd.DataFrame, marker_list: list[str]) -> tuple[list[str], list[str]]:
    """Select source-notebook markers that exist and contain numeric values."""
    available, missing = [], []
    for marker in marker_list:
        if marker not in data.columns:
            missing.append(marker)
            continue
        values = cast(Any, pd.to_numeric(data[marker], errors="coerce"))
        (available if values.notna().sum() else missing).append(marker)
    return available, missing


def get_axis_limits(
    x: np.ndarray, y: np.ndarray, pad_frac: float = 0.08
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Calculate the padded coordinate limits used by source UMAP plots."""
    x_min, x_max, y_min, y_max = np.nanmin(x), np.nanmax(x), np.nanmin(y), np.nanmax(y)
    x_range, y_range = x_max - x_min, y_max - y_min
    x_range = 1 if x_range == 0 else x_range
    y_range = 1 if y_range == 0 else y_range
    return (
        (x_min - x_range * pad_frac, x_max + x_range * pad_frac),
        (y_min - y_range * pad_frac, y_max + y_range * pad_frac),
    )


def plot_full_umap(data: pd.DataFrame, experiment: str, group: str, out_file: Path) -> None:
    """Save the active source notebook's full-population UMAP scatter."""
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
    """Save source notebook condition panels using shared coordinate limits."""
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
    """Fit source-parameter UMAP, then export pooled and per-sample coordinates."""
    if not marker_cols:
        raise ValueError(f"No usable {group} markers found for {experiment}")
    matrix = data[marker_cols].apply(pd.to_numeric, errors="coerce")
    missing_matrix = cast(Any, matrix.isna())
    if missing_matrix.any().any():
        bad_columns = matrix.columns[missing_matrix.any()].tolist()
        raise ValueError(f"NaN values found in UMAP matrix for {experiment}: {bad_columns}")
    model = umap.UMAP(
        n_neighbors=n_neighbors, min_dist=min_dist, metric="euclidean", random_state=random_state
    )
    embedding = cast(np.ndarray, model.fit_transform(cast(Any, matrix.values)))
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
    """Save pooled and per-sample coordinates using the original folder layout."""
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
    """Save full and condition-split plots with source notebook styling."""
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
    """Assemble the source notebook's embedding summary fields."""
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
    """Load the coordinate CSV using the original notebook's directory layout."""
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
