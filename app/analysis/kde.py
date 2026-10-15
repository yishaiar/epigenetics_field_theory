"""KDE plots and subtype proportions copied from active main1.ipynb cells 62, 64, 65."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from typing import cast


def plot_kde_pair(ax: Axes, treated: pd.Series, untreated: pd.Series, marker: str) -> pd.DataFrame:
    """Draw independently normalized treated and untreated KDEs for one marker."""
    treated_values = cast(pd.Series, pd.to_numeric(treated, errors="coerce")).dropna()
    untreated_values = cast(pd.Series, pd.to_numeric(untreated, errors="coerce")).dropna()
    if len(untreated_values) < 2 or len(treated_values) < 2:
        return pd.DataFrame()

    sns.kdeplot(x=untreated_values, ax=ax, color="blue", label="Untreated", common_norm=False)
    sns.kdeplot(x=treated_values, ax=ax, color="red", label="Treated", common_norm=False)
    ax.set(yscale="log", title=marker, xlabel="Expression", ylabel="Density")
    return _line_density_data(ax, marker, ["untreated", "treated"])


def _line_density_data(ax: Axes, marker: str, conditions: list[str]) -> pd.DataFrame:
    """Convert the most recently drawn KDE lines to the source CSV format."""
    return pd.concat(
        [
            pd.DataFrame(
                {
                    "marker": marker,
                    "condition": condition,
                    "expression": line.get_xdata(),
                    "density": line.get_ydata(),
                }
            )
            for line, condition in zip(ax.lines[-len(conditions) :], conditions)
        ],
        ignore_index=True,
    )


def plot_kde_comparison(
    treated: pd.DataFrame,
    untreated: pd.DataFrame,
    cols: list[str],
    title: str,
    fname: str | Path,
    figsize: tuple[float, float] = (16, 12),
) -> None:
    """Save a marker-grid KDE, plus the plotted densities as a sibling CSV."""
    ncols = 4
    nrows = int(np.ceil(len(cols) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    axes = axes.flatten()
    density_data = []
    for ax, marker in zip(axes, cols):
        result = plot_kde_pair(
            ax, cast(pd.Series, treated[marker]), cast(pd.Series, untreated[marker]), marker
        )
        if not result.empty:
            density_data.append(result)
    _remove_unused_axes(axes, len(cols))
    _save_kde_figure(fig, axes[0], title, fname, ncols=2)
    if density_data:
        pd.concat(density_data, ignore_index=True).to_csv(
            Path(fname).with_suffix(".csv"), index=False
        )


def _remove_unused_axes(axes: np.ndarray, count: int) -> None:
    """Remove unused panels, preserving the source grid layout."""
    for ax in axes[count:]:
        ax.remove()


def _save_kde_figure(
    fig: Figure,
    legend_ax: Axes,
    title: str,
    fname: str | Path,
    ncols: int,
) -> None:
    """Save, display, and close a KDE figure using notebook behavior."""
    handles, labels = legend_ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=ncols, bbox_to_anchor=(0.5, 0.96))
    fig.suptitle(title, fontsize=16)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    output = Path(fname)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def plot_treated_subtypes(
    data: pd.DataFrame,
    cols: list[str],
    fname: str | Path,
    figsize: tuple[float, float] = (16, 12),
) -> None:
    """Plot all treated, basal treated, and classical treated KDEs."""
    treated = data[data["condition"] == "treated"]
    groups = {
        "All treated": (treated, "blue"),
        "Treated basal": (treated[treated["labels"] == "basal"], "red"),
        "Treated classical": (treated[treated["labels"] == "classical"], "black"),
    }
    _plot_subtype_groups(
        data, cols, fname, figsize, groups, "All Experiments | Treated Subtype Comparison"
    )


def plot_treated_vs_untreated_subtypes(
    data: pd.DataFrame,
    cols: list[str],
    fname: str | Path,
    figsize: tuple[float, float] = (16, 12),
) -> None:
    """Plot treated and untreated KDEs by subtype with source colors and linestyles."""
    groups = {"All": (None, "blue"), "Basal": ("basal", "red"), "Classical": ("classical", "black")}
    ncols = 4
    nrows = int(np.ceil(len(cols) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    axes = axes.flatten()
    density_data = []
    for ax, marker in zip(axes, cols):
        _plot_condition_subtypes(ax, data, marker, groups, density_data)
    _remove_unused_axes(axes, len(cols))
    _finish_subtype_figure(fig, axes[0], "All Experiments | Treated vs Untreated Subtypes", fname)
    _save_density_data(density_data, fname)


def _plot_subtype_groups(
    data: pd.DataFrame,
    cols: list[str],
    fname: str | Path,
    figsize: tuple[float, float],
    groups: dict[str, tuple[pd.DataFrame, str]],
    title: str,
) -> None:
    ncols = 4
    nrows = int(np.ceil(len(cols) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    axes = axes.flatten()
    density_data = []
    for ax, marker in zip(axes, cols):
        for name, (group, color) in groups.items():
            values = cast(
                pd.Series, pd.to_numeric(cast(pd.Series, group[marker]), errors="coerce")
            ).dropna()
            if len(values) < 2:
                continue
            sns.kdeplot(x=values, ax=ax, color=color, label=name, common_norm=False)
            density_data.append(
                _line_density_data(ax, marker, [name]).rename(columns={"condition": "condition"})
            )
        _format_density_axis(ax, marker)
    _remove_unused_axes(axes, len(cols))
    _finish_subtype_figure(fig, axes[0], title, fname)
    _save_density_data(density_data, fname)


def _plot_condition_subtypes(
    ax: Axes,
    data: pd.DataFrame,
    marker: str,
    groups: dict[str, tuple[str | None, str]],
    density_data: list[pd.DataFrame],
) -> None:
    for subtype, (label, color) in groups.items():
        for condition, linestyle in [("treated", "-"), ("untreated", "--")]:
            group = data[data["condition"] == condition]
            if label is not None:
                group = group[group["labels"] == label]
            values = cast(
                pd.Series, pd.to_numeric(cast(pd.Series, group[marker]), errors="coerce")
            ).dropna()
            if len(values) < 2:
                continue
            sns.kdeplot(
                x=values,
                ax=ax,
                color=color,
                linestyle=linestyle,
                label=f"{condition.capitalize()} {subtype}",
                common_norm=False,
            )
            density = _line_density_data(ax, marker, [condition])
            density["subtype"] = subtype
            density_data.append(
                cast(
                    pd.DataFrame,
                    density.loc[:, ["marker", "condition", "subtype", "expression", "density"]],
                )
            )
    _format_density_axis(ax, marker)


def _format_density_axis(ax: Axes, marker: str) -> None:
    ax.set(yscale="log", title=marker, xlabel="Expression", ylabel="Density")
    ax.set_ylim(bottom=1e-4)


def _finish_subtype_figure(fig: Figure, ax: Axes, title: str, fname: str | Path) -> None:
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.96))
    fig.suptitle(title, fontsize=16)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    output = Path(fname)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def _save_density_data(data: list[pd.DataFrame], fname: str | Path) -> None:
    if data:
        pd.concat(data, ignore_index=True).to_csv(Path(fname).with_suffix(".csv"), index=False)
