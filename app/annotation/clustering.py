"""Leiden clustering and diagnostics copied from active source notebook cells."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, cast

import igraph as ig
import leidenalg
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.sparse import triu
from sklearn.neighbors import kneighbors_graph


def calc_leiden(
    data: pd.DataFrame, n_neighbors: int = 30, resolution: float = 1.0, random_state: int = 42
) -> np.ndarray:
    """Run the source notebook's symmetric kNN RBConfiguration Leiden clustering."""
    coordinates = data[["UMAP1", "UMAP2"]].to_numpy(dtype=float)
    if n_neighbors < 1 or n_neighbors >= len(coordinates):
        raise ValueError("n_neighbors must be between 1 and the number of cells minus 1")
    started = perf_counter()
    adjacency = kneighbors_graph(
        coordinates, n_neighbors=n_neighbors, mode="connectivity", include_self=False, n_jobs=-1
    )
    adjacency = triu(adjacency.maximum(adjacency.T), k=1).tocoo()
    graph = ig.Graph(
        n=len(coordinates),
        edges=list(zip(adjacency.row.tolist(), adjacency.col.tolist())),
        directed=False,
    )
    partition = leidenalg.find_partition(
        graph,
        leidenalg.RBConfigurationVertexPartition,
        resolution_parameter=resolution,
        n_iterations=2,
        seed=random_state,
    )
    labels = np.asarray(partition.membership, dtype=int)
    print(f"Leiden computation: {perf_counter() - started:.2f} seconds")
    print(f"Leiden clusters: {len(np.unique(labels))}")
    return labels


def plot_clusters(
    data: pd.DataFrame,
    labels: np.ndarray,
    title: str,
    out_file: Path,
    point_size: int = 4,
    figsize: tuple[int, int] = (9, 7),
) -> None:
    """Save the source notebook's labeled UMAP scatter."""
    values = np.asarray(labels)
    if len(values) != len(data):
        raise ValueError("Cluster label count must match the coordinate rows")
    clusters = np.unique(values[values != -1])
    cmap = plt.get_cmap("tab20", max(len(clusters), 1))
    fig, ax = plt.subplots(figsize=figsize)
    _draw_cluster_points(ax, data, values, clusters, cmap, point_size)
    ax.set(title=title, xlabel="UMAP1", ylabel="UMAP2", aspect="equal")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", frameon=False, markerscale=3)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def _draw_cluster_points(
    ax: Axes,
    data: pd.DataFrame,
    values: np.ndarray,
    clusters: np.ndarray,
    cmap: Any,
    point_size: int,
) -> None:
    """Draw cluster and noise points using source notebook colors."""
    for index, cluster in enumerate(clusters):
        mask = values == cluster
        ax.scatter(
            data.loc[mask, "UMAP1"],
            data.loc[mask, "UMAP2"],
            s=point_size,
            color=cmap(index),
            alpha=0.8,
            linewidths=0,
            rasterized=True,
            label=f"Cluster {cluster} ({mask.sum():,})",
        )
    noise = values == -1
    if noise.any():
        ax.scatter(
            data.loc[noise, "UMAP1"],
            data.loc[noise, "UMAP2"],
            s=point_size,
            c="black",
            alpha=0.5,
            linewidths=0,
            rasterized=True,
            label=f"Noise ({noise.sum():,})",
        )


def plot_clusters_by_condition(
    data: pd.DataFrame,
    labels: np.ndarray,
    conditions: list[str],
    out_file: Path,
    figsize: tuple[int, int] = (9, 14),
    point_size: int = 4,
    alpha: float = 0.8,
) -> None:
    """Save source-style Leiden panels separated by condition."""
    values = np.asarray(labels)
    if len(values) != len(data):
        raise ValueError("Cluster label count must match the coordinate rows")
    clusters = np.sort(np.unique(values))
    cmap = plt.get_cmap("tab20", max(len(clusters), 1))
    colors = {cluster: cmap(i) for i, cluster in enumerate(clusters) if cluster != -1}
    colors[-1] = (0.0, 0.0, 0.0, 1.0)
    x, y = data["UMAP1"], data["UMAP2"]
    xpad, ypad = (x.max() - x.min()) * 0.08, (y.max() - y.min()) * 0.08
    xlim, ylim = (x.min() - xpad, x.max() + xpad), (y.min() - ypad, y.max() + ypad)
    fig, axes = plt.subplots(
        len(conditions), 1, figsize=figsize, sharex=True, sharey=True, squeeze=False
    )
    for ax, condition in zip(axes.flatten(), conditions):
        _draw_condition_panel(
            ax, data, values, clusters, colors, condition, xlim, ylim, point_size, alpha
        )
    fig.suptitle("Clusters by condition", fontsize=15)
    fig.tight_layout()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def _draw_condition_panel(
    ax: Axes,
    data: pd.DataFrame,
    values: np.ndarray,
    clusters: np.ndarray,
    colors: dict[int, Any],
    condition: str,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    point_size: int,
    alpha: float,
) -> None:
    """Draw one source-style condition panel."""
    condition_mask = data["condition"].to_numpy() == condition
    _draw_condition_points(ax, data, values, clusters, colors, condition_mask, point_size, alpha)
    ax.set(
        title=f"{condition} | {condition_mask.sum():,} cells",
        xlabel="UMAP1",
        ylabel="UMAP2",
        xlim=xlim,
        ylim=ylim,
        aspect="equal",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", frameon=False, markerscale=3, fontsize=9)


def _draw_condition_points(
    ax: Axes,
    data: pd.DataFrame,
    values: np.ndarray,
    clusters: np.ndarray,
    colors: dict[int, Any],
    condition_mask: np.ndarray,
    point_size: int,
    alpha: float,
) -> None:
    """Draw all nonempty cluster scatters for a single condition."""
    for cluster in clusters:
        mask = condition_mask & (values == cluster)
        if mask.any():
            ax.scatter(
                data.loc[mask, "UMAP1"],
                data.loc[mask, "UMAP2"],
                s=point_size,
                color=colors[cluster],
                alpha=alpha,
                linewidths=0,
                rasterized=True,
                label=f"Cluster {cluster} ({mask.sum():,})",
            )


def plot_cluster_heatmap(
    data: pd.DataFrame,
    labels: np.ndarray,
    features: list[str],
    out_file: Path,
    title: str = "Cluster marker expression",
    figsize: tuple[int, int] = (23, 10),
    amin: float | None = None,
    amax: float | None = None,
    rot_dendrogram: bool = False,
    fmt: str = ".2f",
) -> tuple[sns.matrix.ClusterGrid, pd.DataFrame]:
    """Create the source notebook's clustered mean-expression heatmap."""
    means = _calculate_cluster_means(data, labels, features)
    heatmap = means.T
    amin = cast(float, heatmap.min().min() if amin is None else amin)
    amax = cast(float, heatmap.max().max() if amax is None else amax)
    row_cluster, col_cluster = (False, True) if rot_dendrogram else (True, False)
    grid = _make_heatmap(heatmap, row_cluster, col_cluster, figsize, amin, amax, fmt, title)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    grid.figure.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(grid.figure)
    return grid, cast(pd.DataFrame, means)


def _calculate_cluster_means(
    data: pd.DataFrame, labels: np.ndarray, features: list[str]
) -> pd.DataFrame:
    """Calculate source cluster means while retaining positional label alignment."""
    if len(labels) != len(data):
        raise ValueError(f"Labels length ({len(labels)}) != DataFrame length ({len(data)})")
    available = [feature for feature in features if feature in data.columns]
    if not available:
        raise ValueError("No requested features found in DataFrame")
    expression = data[available].apply(pd.to_numeric, errors="coerce").copy()
    expression["_cluster"] = np.asarray(labels)
    means = cast(pd.DataFrame, expression.groupby("_cluster", sort=True).mean())
    if means.empty:
        raise ValueError("No valid cluster data available")
    means.index = ["Noise (-1)" if label == -1 else f"Cluster {label}" for label in means.index]
    means = means.drop(columns=means.columns[means.isna().all()].tolist())
    if means.shape[1] == 0 or cast(Any, means.isna().any()).any():
        raise ValueError("Cluster means contain no usable numeric features")
    return means


def _make_heatmap(
    heatmap: pd.DataFrame,
    row_cluster: bool,
    col_cluster: bool,
    figsize: tuple[int, int],
    amin: float,
    amax: float,
    fmt: str,
    title: str,
) -> sns.matrix.ClusterGrid:
    """Render the source-style annotated and hierarchically clustered heatmap."""
    grid = sns.clustermap(
        heatmap,
        cmap=plt.cm.seismic,
        vmin=amin,
        vmax=amax,
        center=0,
        row_cluster=row_cluster and heatmap.shape[0] > 1,
        col_cluster=col_cluster and heatmap.shape[1] > 1,
        figsize=figsize,
        annot=True,
        fmt=fmt,
        annot_kws={"size": 8},
        linewidths=1,
        linecolor="black",
        cbar_kws={"label": "Mean feature expression"},
    )
    grid.ax_heatmap.set_xlabel("Clusters")
    grid.ax_heatmap.set_ylabel("Features")
    grid.ax_heatmap.set_xticklabels(grid.ax_heatmap.get_xticklabels(), rotation=90)
    grid.ax_heatmap.set_yticklabels(grid.ax_heatmap.get_yticklabels(), rotation=0)
    grid.figure.suptitle(title, fontsize=15, y=1.02)
    return grid
