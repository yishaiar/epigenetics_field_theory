"""Normalize each sample in a pooled CyTOF dataframe."""

from typing import Any, cast

import pandas as pd

from app.config.config import CONTROL_MARKERS, METADATA_COLUMNS

NORMALIZATION_MARKERS = [
    "ACSS2",
    "EZH2",
    "GAL4",
    "GATA6",
    "H2AK119ub",
    "H2BK5ac",
    "H3K27ac",
    "H3K27me2",
    "H3K27me3",
    "H3K36me2",
    "H3K36me3",
    "H3K4me1",
    "H3K4me2",
    "H3K4me3",
    "H3K9ac",
    "H3K9me2",
    "H3K9me3",
    "H3S28p",
    "H4K16ac",
    "H4K20me3",
    "KI67",
    "KRT17",
    "KRT5",
    "MBD",
    "Pan-KRT",
    "S100A4",
    "Vimentin",
    "pH2A.X",
    "pRb",
]


def normalize_pooled_dataframe_new(
    data: pd.DataFrame,
    skip_columns: list[str] = METADATA_COLUMNS,
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize each experiment/sample group and preserve the pooled rows."""
    grouping = (
        ["path"]
        if "path" in data
        else [column for column in ("experiment", "sample_name") if column in data]
    )
    if not grouping:
        raise ValueError("Pooled normalization requires sample_name")

    normalized = data.copy()
    corrected_markers: list[str] = []
    for key, sample in data.groupby(grouping, sort=False, dropna=False):
        sample_name = "_".join(map(str, key if isinstance(key, tuple) else (key,)))
        result, sample_markers = normalize_sample(sample, sample_name, skip_columns)
        if sample_markers:
            normalized.loc[sample.index, sample_markers] = result[sample_markers].to_numpy()
            corrected_markers.extend(
                marker for marker in sample_markers if marker not in corrected_markers
            )
    return normalized, corrected_markers


def normalize_sample(
    data: pd.DataFrame,
    sample_name: str,
    skip_columns: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Normalize the available configured markers in one sample."""
    from cytof_helper.cytof_transform import (  # type: ignore[reportMissingImports]
        CytofTransformConfig,
        cytof_transform_global,
    )

    excluded = set(skip_columns).union(CONTROL_MARKERS)
    markers = [
        marker
        for marker in NORMALIZATION_MARKERS
        if marker in data
        and marker not in excluded
        and col_has_real_data(cast(pd.Series, data[marker]))
    ]
    if not markers:
        return data.copy(), []

    config = CytofTransformConfig(
        control_markers=CONTROL_MARKERS,
        markers_to_correct=markers,
        use_compartments=False,
        n_pcs_for_T=1,
        anchor_to_median=True,
        zscore=False,
    )
    print(sample_name)
    result = cytof_transform_global(data.copy(), config)
    return get_normalization_result(result), markers


def col_has_real_data(series: pd.Series) -> bool:
    """Return whether a column contains any numeric values."""
    numeric = cast(pd.Series, pd.to_numeric(series, errors="coerce"))
    return bool(numeric.notna().any())


def get_normalization_result(result: object) -> pd.DataFrame:
    """Extract the corrected dataframe returned by the CyTOF transform."""
    if isinstance(result, pd.DataFrame):
        return result.copy()
    corrected: Any = getattr(result, "corrected", None)
    if isinstance(corrected, pd.DataFrame):
        return corrected.copy()
    raise TypeError("Expected a dataframe or a transform result with a corrected dataframe")
