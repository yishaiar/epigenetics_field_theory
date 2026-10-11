"""Plotting entry points."""

from typing import Any

__all__ = ["histplot_comparison", "qqplot"]


def __getattr__(name: str) -> Any:
    """Load plotting functions only when their public attribute is requested."""
    if name == "histplot_comparison":
        from .histplot_comparison import histplot_comparison

        value = histplot_comparison
    elif name == "qqplot":
        from .qqplot import qqplot

        value = qqplot
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value
