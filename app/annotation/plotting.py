"""Marker-staining plots copied from active main1.ipynb cell 50."""

from __future__ import annotations

from collections.abc import Sequence
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from app.config.config import METADATA_COLUMNS


def plot_umap_staining(
    data: pd.DataFrame,
    output_root: Path,
    marker_group: str,
    markers: Sequence[str] | None = None,
    *,
    point_size: int = 4,
    alpha: float = 0.85,
    quantiles: tuple[float, float] = (0.01, 0.99),
    cmap: str = "seismic",
    condition_order: Sequence[str] = ("untreated", "treated", "parental"),
) -> list[dict[str, str]]:
    """Save one condition-split UMAP staining plot per available marker.

    Args:
        data: Table containing UMAP coordinates, conditions, and marker values.
        output_root: Root directory for staining plot files.
        marker_group: Name of the marker group used to create the embedding.
        markers: Optional explicit marker panel; by default, all numeric columns
            except metadata and UMAP coordinates are plotted.
        point_size: Scatter point size.
        alpha: Scatter point opacity.
        quantiles: Lower and upper intensity limits used for color scaling.
        cmap: Matplotlib color map used for marker staining.
        condition_order: Preferred condition order before any remaining conditions.

    Returns:
        A record for each marker plot saved.

    Raises:
        ValueError: If required coordinates, rows, or non-null conditions are absent.
    """
    required = ("UMAP1", "UMAP2", "condition")
    missing = [column for column in required if column not in data]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if data.empty:
        raise ValueError("UMAP DataFrame is empty")

    candidate_markers = (
        list(markers)
        if markers is not None
        else [
            column
            for column in data.select_dtypes(include=[np.number]).columns
            if column not in METADATA_COLUMNS and column not in required[:2]
        ]
    )
    marker_values = {
        marker: pd.Series(pd.to_numeric(pd.Series(data[marker]), errors="coerce"), dtype=float)
        for marker in candidate_markers
        if marker in data.columns
    }
    present = [marker for marker, values in marker_values.items() if values.notna().any()]
    conditions = data["condition"].dropna().unique().tolist()
    if not conditions:
        raise ValueError("No conditions found for UMAP staining")
    conditions = [condition for condition in condition_order if condition in conditions] + [
        condition for condition in conditions if condition not in condition_order
    ]

    output = output_root / f"staining_on_{marker_group}_UMAP" / f"individual_marker_{cmap}"
    output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, str]] = []
    for marker in present:
        values = marker_values[marker]
        low, high = values.quantile(quantiles).tolist()
        fig, axes = plt.subplots(
            len(conditions),
            1,
            figsize=(7, 5.5 * len(conditions)),
            sharex=True,
            sharey=True,
            squeeze=False,
        )
        for ax, condition in zip(axes.flatten(), conditions, strict=True):
            condition_mask = data["condition"] == condition
            points = ax.scatter(
                data.loc[condition_mask, "UMAP1"],
                data.loc[condition_mask, "UMAP2"],
                c=values.loc[condition_mask],
                s=point_size,
                cmap=cmap,
                vmin=low,
                vmax=high,
                alpha=alpha,
                linewidths=0,
                rasterized=True,
            )
            ax.set_title(f"{condition} — {marker}", fontsize=13)
            fig.colorbar(points, ax=ax, fraction=0.046, pad=0.04).set_label(
                f"{marker} z-score\n{quantiles[0]:.0%}–{quantiles[1]:.0%} quantiles clipped"
            )
        fig.suptitle(f"{marker_group} UMAP | {marker}", fontsize=15, y=1.01)
        fig.tight_layout()
        safe_marker = re.sub(r"\s+", "_", re.sub(r'[<>:"/\\|?*]', "_", marker))
        out_file = output / f"{marker_group}_{safe_marker}_{cmap}_by_condition.png"
        fig.savefig(out_file, dpi=300, bbox_inches="tight")
        plt.show()
        plt.close(fig)
        records.append(
            {
                "umap_marker_group": marker_group,
                "plot_type": f"individual_marker_{cmap}",
                "marker": marker,
                "plot_file": str(out_file),
            }
        )
    return records


def plot_umap_class_probabilities(
    data: pd.DataFrame,
    probabilities: np.ndarray,
    class_labels: np.ndarray,
    out_file: Path,
    *,
    point_size: int = 4,
    alpha: float = 0.85,
    cmap: str = "seismic",
    condition_order: Sequence[str] = ("untreated", "treated", "parental"),
) -> None:
    """Save condition-split UMAP panels for probabilities across all cells.

    Args:
        data: Table containing UMAP coordinates and condition values.
        probabilities: Probability matrix, one row per data row and one column
            per class label.
        class_labels: Class labels in the same order as the probability columns.
        out_file: Destination PNG path.
        point_size: Scatter point size.
        alpha: Scatter point opacity.
        cmap: Matplotlib color map used for class probabilities.
        condition_order: Preferred condition order before any remaining conditions.

    Raises:
        ValueError: If coordinates, conditions, or probability dimensions do not align.
    """
    required = {"UMAP1", "UMAP2", "condition"}
    if missing := required.difference(data.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    values = np.asarray(probabilities, dtype=float)
    labels = np.asarray(class_labels)
    if values.ndim != 2 or values.shape[0] != len(data):
        raise ValueError("Probability rows must match all UMAP rows")
    if values.shape[1] != len(labels):
        raise ValueError("Probability columns must match the class labels")

    selected = data.loc[:, ["UMAP1", "UMAP2", "condition"]].reset_index(drop=True)
    conditions = selected["condition"].dropna().unique().tolist()
    if not conditions:
        raise ValueError("No conditions found for probability plots")
    preferred = [condition for condition in condition_order if condition in conditions]
    conditions = preferred + [condition for condition in conditions if condition not in preferred]
    fig, axes = plt.subplots(
        len(labels),
        len(conditions),
        figsize=(6 * len(conditions), 5 * len(labels)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    class_names = {0: "classical", 1: "basal"}
    for class_index, class_label in enumerate(labels):
        class_name = class_names.get(int(class_label), str(class_label))
        for condition_index, condition in enumerate(conditions):
            condition_mask = selected["condition"].to_numpy() == condition
            points = axes[class_index, condition_index].scatter(
                selected.loc[condition_mask, "UMAP1"],
                selected.loc[condition_mask, "UMAP2"],
                c=values[condition_mask, class_index],
                s=point_size,
                cmap=cmap,
                vmin=0,
                vmax=1,
                alpha=alpha,
                linewidths=0,
                rasterized=True,
            )
            axes[class_index, condition_index].set(
                title=f"{condition} | P({class_name})",
                xlabel="UMAP1",
                ylabel="UMAP2",
                aspect="equal",
            )
            fig.colorbar(points, ax=axes[class_index, condition_index], label=f"P({class_name})")
    fig.suptitle("XGBoost class probabilities for all cells", fontsize=15)
    fig.tight_layout()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)
