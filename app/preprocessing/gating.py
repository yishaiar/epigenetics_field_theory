"""Gate histone signal and remove per-mouse marker outliers."""

from collections.abc import Sequence

import pandas as pd

from app.config.config import METADATA_COLUMNS

GATE_COLUMNS = ("H3.3", "H4")


def gate_histones(
    data: pd.DataFrame,
    skip_columns: list[str] | None = None,
    core_gate_value: float = 5,
    gate_columns: Sequence[str] = GATE_COLUMNS,
) -> tuple[pd.DataFrame, list[str]]:
    """Keep cells whose raw core histone values pass the gate.

    Args:
        data: Cell table with raw histone and marker columns.
        skip_columns: Additional metadata columns excluded from marker selection.
        core_gate_value: Both gate markers must be strictly greater than this value.
        gate_columns: Histone columns used for the strict core gate.

    Returns:
        The retained rows and the nonmetadata input columns.

    Raises:
        ValueError: If a gate column is missing.
    """
    missing = [column for column in gate_columns if column not in data]
    if missing:
        raise ValueError(f"Missing histone gate columns: {missing}")
    gate_values = data[list(gate_columns)].apply(pd.to_numeric, errors="coerce")
    gated = data.loc[gate_values.gt(core_gate_value).all(axis=1)].copy()
    excluded = set(METADATA_COLUMNS)
    if skip_columns is not None:
        excluded.update(skip_columns)
    marker_columns = [column for column in data.columns if column not in excluded]
    return gated, marker_columns
