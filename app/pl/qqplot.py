import numbers
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes


def qqplot(
    x: Any,
    y: Any,
    quantiles: Any = None,
    interpolation: Literal["linear", "lower", "higher", "midpoint", "nearest"] = "nearest",
    ax: Axes | None = None,
    rug: bool = False,
    rug_length: float = 0.05,
    rug_kwargs: dict[str, Any] | None = None,
    **kwargs: Any,
) -> None:
    """Draw a quantile-quantile plot for `x` versus `y`.

    Parameters
    ----------
    x, y : array-like
        One-dimensional numeric arrays.

    ax : matplotlib.axes.Axes, optional
        Axes on which to plot. If not provided, the current axes will be used.

    quantiles : int or array-like, optional
        Quantiles to include in the plot. This can be an array of quantiles, in
        which case only the specified quantiles of `x` and `y` will be plotted.
        If this is an int `n`, then the quantiles will be `n` evenly spaced
        points between 0 and 1. If this is None, then `min(len(x), len(y))`
        evenly spaced quantiles between 0 and 1 will be computed.

    method : {‘linear’, ‘lower’, ‘higher’, ‘midpoint’, ‘nearest’}
        Specify the interpolation method used to find quantiles when `quantiles`
        is an int or None. See the documentation for numpy.quantile().

    rug : bool, optional
        If True, draw a rug plot representing both samples on the horizontal and
        vertical axes. If False, no rug plot is drawn.

    rug_length : float in [0, 1], optional
        Specifies the length of the rug plot lines as a fraction of the total
        vertical or horizontal length.

    rug_kwargs : dict of keyword arguments
        Keyword arguments to pass to matplotlib.axes.Axes.axvline() and
        matplotlib.axes.Axes.axhline() when drawing rug plots.

    kwargs : dict of keyword arguments
        Keyword arguments to pass to matplotlib.axes.Axes.scatter() when drawing
        the q-q plot.
    """
    # Get current axes if none are provided
    if ax is None:
        ax = plt.gca()

    if quantiles is None:
        quantiles = min(len(x), len(y))

    # Compute quantiles of the two samples
    if isinstance(quantiles, numbers.Integral):
        quantiles = np.linspace(start=0, stop=1, num=int(quantiles))
    else:
        quantiles = np.atleast_1d(np.sort(quantiles))
    x_quantiles = np.quantile(x, quantiles, method=interpolation)
    y_quantiles = np.quantile(y, quantiles, method=interpolation)

    # Draw the rug plots if requested
    if rug:
        # Default rug plot settings
        rug_x_params: dict[str, Any] = dict(ymin=0, ymax=rug_length, c="gray", alpha=0.5)
        rug_y_params: dict[str, Any] = dict(xmin=0, xmax=rug_length, c="gray", alpha=0.5)

        # Override default setting by any user-specified settings
        if rug_kwargs is not None:
            rug_x_params.update(rug_kwargs)
            rug_y_params.update(rug_kwargs)

        # Draw the rug plots
        for point in x:
            ax.axvline(point, **rug_x_params)
        for point in y:
            ax.axhline(point, **rug_y_params)

    # Draw the q-q plot
    # plt.figure()
    ax.scatter(x_quantiles, y_quantiles, **kwargs)
    # j=7
    # plt.plot([-j,j],[-j,j],c='k',lw=2)#refence plot


def shared_qqplot(
    data1: tuple[Any, Any],
    data2: tuple[Any, Any],
    title1: str | None = None,
    title2: str | None = None,
    fname: str | None = None,
) -> None:
    x1, y1 = data1
    x2, y2 = data2

    qqplot(x1, y1, c="r", alpha=0.25, edgecolor=None, rug=True, label="Original")
    qqplot(
        x2,
        y2,
        c="g",
        alpha=0.25,
        edgecolor=None,
        rug=True,
        label="QQ Transformed",
    )

    plt.xlabel(title1 or "Source quantiles")
    plt.ylabel(title2 or "Reference quantiles")
    plt.title("QQ Plot")
    plt.legend()
    j = 7
    plt.plot([-j, j], [-j, j], c="k", lw=2)  # refence plot

    if fname is not None:
        plt.savefig(f"{fname}.png")
    plt.show()


if __name__ == "__main__":
    from ..datasets import get_sample_data, load_demo

    def get_pairs(batch_index: int, marker_index: int) -> tuple[Any, Any]:
        batch_obs = adata.obs[adata.obs["batch_index"] == batch_index]

        anchor_sample = batch_obs.loc[batch_obs["is_anchor"], "sample_index"].iloc[0]
        other_sample = batch_obs.loc[~batch_obs["is_anchor"], "sample_index"].iloc[0]

        return (
            get_sample_data(adata, batch_index, anchor_sample)[:, marker_index],
            get_sample_data(adata, batch_index, other_sample)[:, marker_index],
        )

    adata = load_demo()
    marker_index = 0
    marker_name = str(adata.var_names[marker_index])

    shared_qqplot(
        data1=get_pairs(batch_index=0, marker_index=marker_index),
        data2=get_pairs(batch_index=1, marker_index=marker_index),
        title1=f"Anchor quantiles ({marker_name})",
        title2=f"Sample quantiles ({marker_name})",
    )
