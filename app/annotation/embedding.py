"""Embedding and coordinate export copied from the active main1.ipynb cells."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import umap.umap_ as umap

from app.config.config import METADATA_COLUMNS


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
        if marker not in data.columns or marker in METADATA_COLUMNS:
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


def plot_full_umap(data: pd.DataFrame, out_file: Path) -> None:
    """Save and display a scatter plot of all supplied UMAP coordinates.

    Args:
        data: Table containing ``UMAP1`` and ``UMAP2`` columns.
        out_file: Destination image path.
    """
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.scatter(data["UMAP1"], data["UMAP2"], s=4, c="black", alpha=0.75, linewidths=0)
    ax.set(
        title="UMAP embedding",
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
    out_file: Path,
) -> None:
    """Save and display one UMAP panel for each condition in the data.

    Args:
        data: Table containing coordinates and a ``condition`` column.
        out_file: Destination image path.
    """
    xlim, ylim = get_axis_limits(data["UMAP1"].to_numpy(), data["UMAP2"].to_numpy())
    present = data["condition"].dropna().unique().tolist()
    if not present:
        raise ValueError("No conditions found for UMAP plot")
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
    fig.suptitle("UMAP by condition", fontsize=15, y=1.01)
    plt.tight_layout()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def calculate_umap(
    data: pd.DataFrame,
    markers: list[str],
    cache_file: Path,
    n_neighbors: int = 15,
    min_dist: float = 0.001,
    random_state: int = 42,
) -> pd.DataFrame:
    """Load cached UMAP coordinates or calculate and cache them as Parquet.

    Args:
        data: Cells-by-metadata-and-marker table.
        markers: Candidate feature columns used to fit the embedding.
        cache_file: Parquet path reused when it already exists.
        n_neighbors: UMAP neighborhood size.
        min_dist: Minimum spacing between embedded points.
        random_state: Seed for reproducible fitting.

    Returns:
        A copy of the input table with UMAP coordinate columns.

    Raises:
        ValueError: If the cache is misaligned or no usable markers remain.
    """
    if cache_file.is_file():
        cached = pd.read_parquet(cache_file)
        if len(cached) != len(data):
            raise ValueError("Cached UMAP row count does not match the input data")
        if (
            "cell_id" in data
            and "cell_id" in cached
            and not data["cell_id"]
            .reset_index(drop=True)
            .equals(cached["cell_id"].reset_index(drop=True))
        ):
            raise ValueError("Cached UMAP cell_id values/order do not match the input data")
        return cached

    marker_cols = [
        marker
        for marker in markers
        if marker in data.columns
        and marker not in METADATA_COLUMNS
        and pd.Series(pd.to_numeric(pd.Series(data[marker]), errors="coerce"), dtype=float)
        .notna()
        .any()
    ]
    if not marker_cols:
        raise ValueError("No usable UMAP markers found in the input data")
    matrix = data[marker_cols].apply(pd.to_numeric, errors="coerce")
    if matrix.isna().to_numpy().any():
        bad_columns = matrix.columns[matrix.isna().any(axis=0)].tolist()
        raise ValueError(f"NaN values found in UMAP markers: {bad_columns}")
    model = umap.UMAP(
        n_neighbors=n_neighbors, min_dist=min_dist, metric="euclidean", random_state=random_state
    )
    embedding = np.asarray(model.fit_transform(matrix.to_numpy(dtype=float)), dtype=float)
    embedded = data.assign(UMAP1=embedding[:, 0], UMAP2=embedding[:, 1])
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    embedded.to_parquet(cache_file, index=False)
    return embedded


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
