"""Marker-staining plots copied from active main1.ipynb cell 50."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from typing import Any, cast


def plot_umap_staining(
    data: pd.DataFrame,
    markers: list[str],
    experiment: str,
    marker_group: str,
    stain_out: Path,
) -> list[dict[str, str]]:
    """Save per-marker seismic maps split by condition as in the source cell."""
    output, present, conditions = _staining_setup(
        data, markers, experiment, marker_group, stain_out
    )
    return [
        _plot_one_marker(data, marker, conditions, experiment, marker_group, output)
        for marker in present
    ]


def _staining_setup(
    data: pd.DataFrame,
    markers: list[str],
    experiment: str,
    marker_group: str,
    stain_out: Path,
) -> tuple[Path, list[str], list[str]]:
    """Validate plotting inputs and resolve active source notebook selections."""
    missing = [column for column in ("UMAP1", "UMAP2", "condition") if column not in data]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if data.empty:
        raise ValueError("UMAP DataFrame is empty")
    output = stain_out / f"staining_on_{marker_group}_UMAP" / "individual_marker_seismic"
    output.mkdir(parents=True, exist_ok=True)
    present = [m for m in markers if m in data and _numeric(data, m).notna().any()]
    conditions = data["condition"].dropna().unique().tolist()
    preferred = {"all": ["untreated", "treated", "parental"]}.get(experiment, [])
    conditions = [c for c in preferred if c in conditions] + [
        c for c in conditions if c not in preferred
    ]
    if not conditions:
        raise ValueError(f"No conditions found for {experiment}")
    return output, present, conditions


def _plot_one_marker(
    data: pd.DataFrame,
    marker: str,
    conditions: list[str],
    experiment: str,
    marker_group: str,
    output: Path,
) -> dict[str, str]:
    """Create and save one marker's condition-split seismic plot."""
    values = _numeric(data, marker)
    low, high = values.quantile(0.01), values.quantile(0.99)
    fig, axes = plt.subplots(
        len(conditions),
        1,
        figsize=(7, 5.5 * len(conditions)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    _draw_marker_conditions(fig, axes.flatten(), data, marker, conditions, low, high)
    fig.suptitle(f"{experiment} | {marker_group} UMAP | {marker}", fontsize=15, y=1.01)
    fig.tight_layout()
    safe_marker = re.sub(r"\s+", "_", re.sub(r'[<>:"/\\|?*]', "_", marker))
    out_file = output / f"{experiment}_{marker_group}_{safe_marker}_seismic_by_condition.png"
    fig.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)
    return {
        "umap_marker_group": marker_group,
        "experiment": experiment,
        "plot_type": "individual_marker_seismic",
        "marker": marker,
        "plot_file": str(out_file),
    }


def _draw_marker_conditions(
    fig: Any,
    axes: Any,
    data: pd.DataFrame,
    marker: str,
    conditions: list[str],
    low: float,
    high: float,
) -> None:
    """Draw the source notebook's color-scaled panel and colorbar per condition."""
    for ax, condition in zip(axes, conditions):
        subset = cast(pd.DataFrame, data[data["condition"] == condition])
        points = ax.scatter(
            subset["UMAP1"],
            subset["UMAP2"],
            c=_numeric(subset, marker),
            s=4,
            cmap="seismic",
            vmin=low,
            vmax=high,
            alpha=0.85,
            linewidths=0,
            rasterized=True,
        )
        ax.set_title(f"{condition} — {marker}", fontsize=13)
        fig.colorbar(points, ax=ax, fraction=0.046, pad=0.04).set_label(
            f"{marker} z-score\n1st–99th percentile clipped"
        )


def _numeric(data: pd.DataFrame, marker: str) -> Any:
    """Return the runtime Series while accommodating Pandas' broad column type."""
    return cast(Any, pd.to_numeric(data[marker], errors="coerce"))
