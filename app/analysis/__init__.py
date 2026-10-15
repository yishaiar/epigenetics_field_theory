"""Biological comparisons and expression-distribution analysis."""

from .comparisons import run_biological_comparisons
from .kde import (
    plot_kde_comparison,
    plot_kde_pair,
    plot_treated_subtypes,
    plot_treated_vs_untreated_subtypes,
)

__all__ = [
    "plot_kde_comparison",
    "plot_kde_pair",
    "plot_treated_subtypes",
    "plot_treated_vs_untreated_subtypes",
    "run_biological_comparisons",
]
