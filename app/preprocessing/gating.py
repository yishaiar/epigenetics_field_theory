"""Raw H3.3/H4 gating extracted from main1.ipynb cell 21."""

import re
from pathlib import Path

import pandas as pd


GATE_COLUMNS = ["H3.3", "H4"]
REQUIRED_COLUMNS = GATE_COLUMNS + ["cell_id", "sample_name", "condition"]


def safe_name(x: object) -> str:
    """Apply the source notebook's filename sanitization."""
    x = str(x)
    x = re.sub(r'[<>:"/\\|?*]', "_", x)
    x = re.sub(r"\s+", "_", x)
    return x


def gate_histones(data: pd.DataFrame, source: Path | None = None) -> pd.DataFrame:
    """Keep rows where numeric H3.3 and H4 are both strictly greater than five."""
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"Missing columns in file {source}: {missing}")
    if data["cell_id"].isna().any():
        raise ValueError(f"Missing cell_id values in file: {source}")
    if not data["cell_id"].is_unique:
        raise ValueError(f"cell_id is not unique in file: {source}")
    if data.empty:
        return data.copy()
    if pd.isna(data["sample_name"].iloc[0]) or pd.isna(data["condition"].iloc[0]):
        raise ValueError(f"Missing sample_name or condition in: {source}")
    gate_values = data[GATE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    gate_mask = (gate_values > 5).all(axis=1)
    return data.loc[gate_mask].copy()


def _gate_file(
    csv_file: Path, experiment: str, group: str, output_dir: Path
) -> dict[str, object] | None:
    """Reload, gate, and save one split file using the source paths and names."""
    data = pd.read_csv(csv_file, low_memory=False)
    if data.empty:
        return None
    gated = gate_histones(data, csv_file)
    sample_name = data["sample_name"].iloc[0]
    condition = data["condition"].iloc[0]
    target_dir = output_dir / experiment / group / safe_name(condition)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{safe_name(sample_name)}_{group}_GATED.csv"
    gated.to_csv(target, index=False)
    n_input = len(data)
    n_gated = len(gated)
    return {
        "experiment": experiment,
        "condition": condition,
        "sample_name": sample_name,
        "gfp_group": group,
        "input_file": str(csv_file),
        "gated_file": str(target),
        "gate_columns": " | ".join(GATE_COLUMNS),
        "gate_rule": "H3.3 > 5 and H4 > 5 on raw values",
        "n_input_cells": n_input,
        "n_gated_cells": n_gated,
        "n_removed_by_gate": n_input - n_gated,
        "pct_kept": 100 * n_gated / n_input if n_input > 0 else 0,
    }


def process_gated_files(
    split_dir: Path,
    output_dir: Path,
    experiments: list[str],
    groups: list[str] | None = None,
) -> pd.DataFrame:
    """Apply the source cell's sorted per-experiment, per-group file workflow."""
    rows = []
    for experiment in experiments:
        for group in groups or ["GFP_high", "GFP_low"]:
            input_dir = split_dir / experiment / group
            if not input_dir.is_dir():
                continue
            files = sorted(input_dir.glob("*.csv"))
            for csv_file in files:
                result = _gate_file(csv_file, experiment, group, output_dir)
                if result is not None:
                    rows.append(result)
    columns = [
        "experiment",
        "condition",
        "sample_name",
        "gfp_group",
        "input_file",
        "gated_file",
        "gate_columns",
        "gate_rule",
        "n_input_cells",
        "n_gated_cells",
        "n_removed_by_gate",
        "pct_kept",
    ]
    summary = pd.DataFrame(rows, columns=columns)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "GATED_summary.csv", index=False)
    return summary
