"""Plot multiple one-dimensional KDE curves on a shared axis."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.axes import Axes


def _plot_comparison_curve(
    ax: Axes,
    data: Sequence[pd.Series | np.ndarray],
    comparison: tuple[int] | tuple[int, str] | tuple[int, str, str] | tuple[int, str, str, str],
    position: int,
    marker: str,
) -> pd.DataFrame | None:
    """Plot one comparison and return its sampled density coordinates.

    Args:
        ax: Matplotlib axis on which to draw the curve.
        data: One-dimensional marker values indexed by comparison entries.
        comparison: Index and optional display style for this curve.
        position: Zero-based comparison position used for default styling.
        marker: Marker name recorded in the density coordinates.

    Returns:
        Density coordinates for the plotted curve, or ``None`` when fewer than
        two numeric values are available.

    Raises:
        IndexError: If the comparison refers to an invalid data index.
    """
    default_colors = ("red", "blue", "black", "green", "yellow", "purple")
    index = comparison[0]
    if index < 0 or index >= len(data):
        raise IndexError(f"comparison data index {index} is out of range")

    name = comparison[1] if len(comparison) > 1 else f"plot{position + 1}"
    color = comparison[2] if len(comparison) > 2 else default_colors[position]
    linestyle = comparison[3] if len(comparison) > 3 else "-"
    numeric_values = pd.Series(pd.to_numeric(pd.Series(data[index]), errors="coerce"), dtype=float)
    values = numeric_values.dropna()
    if len(values) < 2:
        return None

    sns.kdeplot(
        x=values,
        ax=ax,
        color=color,
        linestyle=linestyle,
        label=name,
        common_norm=False,
    )
    x, y = ax.lines[-1].get_data()
    return pd.DataFrame(
        {
            "marker": marker,
            "condition": name,
            "expression": x,
            "density": y,
        }
    )


def plot_kde_curves(
    ax: Axes,
    data: Sequence[pd.Series | np.ndarray],
    comparisons: Sequence[
        tuple[int] | tuple[int, str] | tuple[int, str, str] | tuple[int, str, str, str]
    ],
    marker: str,
    yscale: Literal["linear", "log"] = "log",
) -> pd.DataFrame:
    """Plot two to six independently normalized KDE curves for one marker.

    Args:
        ax: Matplotlib axis on which to draw the curves.
        data: One-dimensional values for the same marker, one series per curve.
        comparisons: One tuple per curve, formatted as
            ``(data_index[, name[, color[, linestyle]]])``. The required
            ``data_index`` selects an entry in ``data``. Optional ``name``,
            ``color``, and ``linestyle`` set the legend label, line color, and
            line style. Defaults are ``plot1``, ``plot2``, and so on for the
            name, the default color sequence by comparison position for the
            color, and a solid line (``"-"``) for the style. For example,
            ``(0, "Treated", "red", "--")`` plots ``data[0]`` with a red,
            dashed line labeled ``Treated``.
        marker: Marker name included in the returned KDE coordinates.
        yscale: Y-axis scale, either ``"linear"`` or ``"log"``.

    Returns:
        A DataFrame of plotted KDE coordinates labeled by marker and comparison
        name. Curves with fewer than two numeric values are skipped.
    """
    if not 2 <= len(comparisons) <= 6:
        raise ValueError("comparisons must contain between two and six entries")

    density_data = []

    for position, comparison in enumerate(comparisons):
        result = _plot_comparison_curve(ax, data, comparison, position, marker)
        if result is not None:
            density_data.append(result)

    ax.set_yscale(yscale)
    ax.set_title(marker)
    ax.set_xlabel("Expression")
    ax.set_ylabel("Density")
    return pd.concat(density_data, ignore_index=True) if density_data else pd.DataFrame()
