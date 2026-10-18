"""Biological comparisons and expression-distribution analysis."""

from .kde_curves import plot_kde_curves
from .kde import (
    plot_kde_comparison,
    plot_treatment_comparisons,
)

__all__ = [
    "plot_kde_comparison",
    "plot_kde_curves",
    "plot_treatment_comparisons",
]
