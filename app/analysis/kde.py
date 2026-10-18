"""KDE plotting functions copied from active main1.ipynb cells 62, 64, and 65."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .kde_curves import plot_kde_curves


def _validate_comparisons(
    data: Sequence[pd.DataFrame],
    comparisons: Sequence[
        tuple[int] | tuple[int, str] | tuple[int, str, str] | tuple[int, str, str, str]
    ],
) -> None:
    """Validate comparison count and referenced table indexes.

    Args:
        data: Tables available to the comparison definitions.
        comparisons: Group definitions containing table indexes.

    Raises:
        ValueError: If the number of comparison groups is outside two to six.
        IndexError: If a comparison refers to an invalid table index.
    """
    if not 2 <= len(comparisons) <= 6:
        raise ValueError("comparisons must contain between two and six entries")
    for comparison in comparisons:
        data_index = comparison[0]
        if data_index < 0 or data_index >= len(data):
            raise IndexError(f"comparison data index {data_index} is out of range")


def _plot_marker_grid(
    axes: Sequence[Axes],
    data: Sequence[pd.DataFrame],
    comparisons: Sequence[
        tuple[int] | tuple[int, str] | tuple[int, str, str] | tuple[int, str, str, str]
    ],
    cols: list[str],
) -> list[pd.DataFrame]:
    """Draw marker panels and collect their density coordinates.

    Args:
        axes: Matplotlib axes, one per marker panel.
        data: Tables selected by comparison indexes.
        comparisons: Group labels and styles for each plotted line.
        cols: Marker names, in panel order.

    Returns:
        Nonempty density-coordinate tables, one per marker with plotted curves.
    """
    density_data = []
    for ax, marker in zip(axes, cols):
        line_data = [pd.Series(data[comparison[0]][marker]) for comparison in comparisons]
        result = plot_kde_curves(ax, line_data, comparisons, marker)
        if not result.empty:
            density_data.append(result)
    return density_data


def _save_comparison_figure(
    fig: Figure,
    axes: Sequence[Axes],
    title: str,
    fname: Path,
    comparison_count: int,
    marker_count: int,
) -> None:
    """Add the shared legend and save the marker-grid figure.

    Args:
        fig: Figure containing the marker panels.
        axes: Figure axes, including any unused panels to remove.
        title: Figure title.
        fname: Destination image path.
        comparison_count: Number of comparison groups shown in the legend.
        marker_count: Number of populated marker panels.
    """
    for ax in axes[marker_count:]:
        ax.remove()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="upper center", ncol=comparison_count, bbox_to_anchor=(0.5, 0.96)
    )
    fig.suptitle(title, fontsize=16)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fname.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fname, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def plot_kde_comparison(
    data: Sequence[pd.DataFrame],
    comparisons: Sequence[
        tuple[int] | tuple[int, str] | tuple[int, str, str] | tuple[int, str, str, str]
    ],
    cols: list[str],
    title: str,
    fname: str | Path,
    figsize: tuple[float, float] = (16, 12),
) -> pd.DataFrame:
    """Plot and export two to six named groups across a marker grid.

    Each comparison selects a DataFrame by index and may specify a display name,
    line color, and line style.

    Args:
        data: One table per plotted group, each containing the requested markers.
        comparisons: Group specifications as ``(data_index,)`` through
            ``(data_index, name, color, linestyle)`` tuples.
        cols: Marker columns to plot, in panel order.
        title: Figure title.
        fname: Output figure path; the density CSV uses the same stem.
        figsize: Matplotlib figure size in inches.

    Returns:
        A table of plotted density coordinates, including group and marker
        identifiers. It is empty when no KDE curves can be computed.

    Raises:
        ValueError: If the number of comparison groups is outside two to six.
        IndexError: If a comparison refers to an invalid data index.
    """
    _validate_comparisons(data, comparisons)

    ncols = 4
    nrows = int(np.ceil(len(cols) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    axes = list(axes.flatten())
    density_data = _plot_marker_grid(axes, data, comparisons, cols)
    fname = Path(fname)
    _save_comparison_figure(fig, axes, title, fname, len(comparisons), len(cols))

    result = pd.concat(density_data, ignore_index=True) if density_data else pd.DataFrame()
    if not result.empty:
        result.to_csv(fname.with_suffix(".csv"), index=False)
    return result


def _plot_treatment_kdes(
    comparisons: dict[str, tuple[pd.DataFrame, pd.DataFrame, str]],
    cols: list[str],
    title: str,
    output: Path,
    figsize: tuple[float, float],
) -> None:
    """Save the five treated-versus-untreated KDE plots and density tables.

    Args:
        comparisons: Named pairs of treated and untreated tables with titles.
        cols: Marker columns to plot, in panel order.
        title: Experiment or comparison name used in figure titles.
        output: Directory for plot and density files.
        figsize: Matplotlib size for each marker-grid figure, in inches.
    """
    for name, (treated_df, untreated_df, comparison_title) in comparisons.items():
        density = plot_kde_comparison(
            data=[untreated_df, treated_df],
            comparisons=[(0, "Untreated", "blue", "-"), (1, "Treated", "red", "-")],
            cols=cols,
            title=f"{title} | {comparison_title}",
            fname=output / f"{name}.png",
            figsize=figsize,
        )
        if not density.empty:
            density["condition"] = density["condition"].str.lower()
            density.to_csv(output / f"{name}.csv", index=False)


def _save_subtype_proportions(
    treated: pd.DataFrame,
    untreated: pd.DataFrame,
    title: str,
    output: Path,
) -> None:
    """Save per-sample subtype proportions as a CSV and boxplot.

    Args:
        treated: Cells from the treated condition.
        untreated: Cells from the untreated condition.
        title: Figure title prefix.
        output: Directory for the proportion CSV and figure.
    """
    proportions = (
        pd.concat([treated, untreated])
        .groupby(["experiment", "sample_name", "condition", "labels"])
        .size()
        .to_frame(name="n_cells")
        .reset_index()
    )
    proportions["proportion"] = proportions["n_cells"] / proportions.groupby(
        ["experiment", "sample_name"]
    )["n_cells"].transform("sum")
    proportions.to_csv(output / "subtype_proportions.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.boxplot(data=proportions, x="labels", y="proportion", hue="condition", ax=ax)
    sns.stripplot(
        data=proportions,
        x="labels",
        y="proportion",
        hue="condition",
        dodge=True,
        color="black",
        alpha=0.6,
        legend=False,
        ax=ax,
    )
    ax.set_title(f"{title} | Subtype proportions")
    ax.set_ylabel("Proportion")
    ax.set_xlabel("Subtype")
    fig.tight_layout()
    fig.savefig(output / "subtype_proportions.png", dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def plot_treatment_comparisons(
    treated: pd.DataFrame,
    untreated: pd.DataFrame,
    cols: list[str],
    title: str,
    fname: str | Path,
    figsize: tuple[float, float] = (16, 12),
) -> None:
    """Create five treated-versus-untreated KDE comparisons and subtype summaries.

    The five plots compare:
    1. all cells
    2. matching basal cells
    3. matching classical cells
    4. treated basal with untreated classical
    5. treated classical with untreated basal
    Save the plots in ``fname`` as ``all.png``, ``basal.png``,
    ``classical.png``, ``classical_to_basal.png``, and
    ``basal_to_classical.png``. Each plot has a sibling density CSV when KDE
    data is available. Also save ``subtype_proportions.csv`` and
    ``subtype_proportions.png``.

    Args:
        treated: Cells from the treated condition, with a ``labels`` column.
        untreated: Cells from the untreated condition, with a ``labels`` column.
        cols: Marker columns to compare, in panel order.
        title: Experiment or comparison name used in figure titles.
        fname: Directory where figures and CSV outputs are written.
        figsize: Matplotlib size for each marker-grid figure, in inches.
    """
    treated_basal = treated[treated["labels"] == "basal"]
    untreated_basal = untreated[untreated["labels"] == "basal"]
    treated_classical = treated[treated["labels"] == "classical"]
    untreated_classical = untreated[untreated["labels"] == "classical"]

    comparisons = {
        "all": (treated, untreated, "All cells"),
        "basal": (treated_basal, untreated_basal, "Basal"),
        "classical": (treated_classical, untreated_classical, "Classical"),
        "classical_to_basal": (
            treated_basal,
            untreated_classical,
            "Untreated classical vs treated basal",
        ),
        "basal_to_classical": (
            treated_classical,
            untreated_basal,
            "Untreated basal vs treated classical",
        ),
    }

    output = Path(fname)
    output.mkdir(parents=True, exist_ok=True)

    _plot_treatment_kdes(comparisons, cols, title, output, figsize)
    _save_subtype_proportions(treated, untreated, title, output)
