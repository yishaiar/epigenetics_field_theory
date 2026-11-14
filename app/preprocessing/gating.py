"""Gate histone signal and remove per-mouse marker outliers."""

from collections.abc import Sequence

import pandas as pd

from app.config.config import METADATA_COLUMNS

GATE_COLUMNS = ("H3.3", "H4")


def gate_histones(
    data: pd.DataFrame,
    skip_columns: list[str] | None = None,
    core_gate_value: float = 5,
    lower_outlier_quantile: float = 0.0001,
    upper_outlier_quantile: float = 0.9999,
    gate_columns: Sequence[str] = GATE_COLUMNS,
) -> tuple[pd.DataFrame, list[str]]:
    """Keep cells above the histone gate and within each mouse's marker bounds.

    Args:
        data: Cell table with raw histone and marker columns.
        skip_columns: Additional metadata columns excluded from marker selection.
        core_gate_value: Both gate markers must be strictly greater than this value.
        lower_outlier_quantile: Per-mouse lower marker quantile to retain.
        upper_outlier_quantile: Per-mouse upper marker quantile to retain.
        gate_columns: Histone columns used for the strict core gate.

    Returns:
        The retained rows and all nonmetadata input columns considered for gating.

    Raises:
        ValueError: If gate columns are missing or quantiles are invalid.
    """
    missing = [column for column in gate_columns if column not in data]
    if missing:
        raise ValueError(f"Missing histone gate columns: {missing}")
    if not 0 <= lower_outlier_quantile < upper_outlier_quantile <= 1:
        raise ValueError("Outlier quantiles must satisfy 0 <= lower < upper <= 1")

    excluded = set(METADATA_COLUMNS)
    if skip_columns is not None:
        excluded.update(skip_columns)
    marker_columns = [column for column in data.columns if column not in excluded]
    gate_values = data[list(gate_columns)].apply(pd.to_numeric, errors="coerce")
    gated = data.loc[gate_values.gt(core_gate_value).all(axis=1)].copy()
    if gated.empty:
        return gated, marker_columns

    marker_values = gated[marker_columns].apply(pd.to_numeric, errors="coerce")
    marker_values = marker_values.loc[:, marker_values.notna().any()]
    if marker_values.empty:
        return gated, marker_columns

    sample_columns = [c for c in ("sample_name", "experiment", "condition") if c in gated]
    if "sample_name" not in gated:
        groups = [(None, gated)]
    else:
        groups = gated.groupby(sample_columns, sort=False, dropna=False)

    keep_rows = pd.Series(False, index=gated.index)
    for _, sample in groups:
        values = marker_values.loc[sample.index]
        values = values.loc[:, values.notna().any()]
        if values.empty:
            keep_rows.loc[sample.index] = True
            continue
        bounds = values.quantile([lower_outlier_quantile, upper_outlier_quantile])
        within_lower_bound = values.isna() | values.ge(bounds.loc[lower_outlier_quantile])
        within_upper_bound = values.isna() | values.le(bounds.loc[upper_outlier_quantile])
        keep_rows.loc[sample.index] = within_lower_bound.all(axis=1) & within_upper_bound.all(
            axis=1
        )

    return gated.loc[keep_rows].copy(), marker_columns
