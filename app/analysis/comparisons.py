"""Biological comparison loops copied from active main1.ipynb cells 61 and 63."""

from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import cast

import pandas as pd

from .kde import plot_kde_comparison


def run_biological_comparisons(
    data: pd.DataFrame, markers: list[str], output_dir: str | Path
) -> None:
    """Create pooled, per-experiment, and every within-experiment sample-pair comparison."""
    _validate_comparison_input(data, markers)
    output = Path(output_dir)
    _run_comparison(data, markers, "All Experiments", output / "all_experiments")
    experiments = cast(pd.Series, data["experiment"]).drop_duplicates().tolist()
    for experiment in experiments:
        experiment_data = cast(pd.DataFrame, data[data["experiment"] == experiment])
        _run_comparison(
            experiment_data, markers, str(experiment), output / "per_experiment" / str(experiment)
        )
        _run_sample_pairs(experiment_data, markers, output, str(experiment))


def _validate_comparison_input(data: pd.DataFrame, markers: list[str]) -> None:
    required = {"condition", "experiment", "sample_name", "labels", *markers}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Missing comparison columns: {missing}")
    if not markers:
        raise ValueError("At least one marker is required")


def _run_comparison(data: pd.DataFrame, markers: list[str], title: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    treated = cast(pd.DataFrame, data[data["condition"] == "treated"])
    untreated = cast(pd.DataFrame, data[data["condition"] == "untreated"])
    groups = {
        "all": (treated, untreated, "All cells"),
        "basal": (
            treated[treated["labels"] == "basal"],
            untreated[untreated["labels"] == "basal"],
            "Basal",
        ),
        "classical": (
            treated[treated["labels"] == "classical"],
            untreated[untreated["labels"] == "classical"],
            "Classical",
        ),
        "classical_to_basal": (
            treated[treated["labels"] == "basal"],
            untreated[untreated["labels"] == "classical"],
            "Untreated classical vs treated basal",
        ),
        "basal_to_classical": (
            treated[treated["labels"] == "classical"],
            untreated[untreated["labels"] == "basal"],
            "Untreated basal vs treated classical",
        ),
    }
    for name, (treated_group, untreated_group, subtitle) in groups.items():
        plot_kde_comparison(
            treated_group, untreated_group, markers, f"{title} | {subtitle}", output / f"{name}.png"
        )
    _save_subtype_proportions(treated, untreated, title, output)


def _save_subtype_proportions(
    treated: pd.DataFrame, untreated: pd.DataFrame, title: str, output: Path
) -> None:
    proportions = (
        pd.concat([treated, untreated])
        .groupby(["experiment", "sample_name", "condition", "labels"])
        .size()
        .to_frame("n_cells")
        .reset_index()
    )
    proportions["proportion"] = proportions["n_cells"] / proportions.groupby(
        ["experiment", "sample_name"]
    )["n_cells"].transform("sum")
    proportions.to_csv(output / "subtype_proportions.csv", index=False)
    _plot_proportions(proportions, title, output)


def _plot_proportions(proportions: pd.DataFrame, title: str, output: Path) -> None:
    import matplotlib.pyplot as plt
    import seaborn as sns

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


def _run_sample_pairs(
    data: pd.DataFrame, markers: list[str], output: Path, experiment: str
) -> None:
    treated = data[data["condition"] == "treated"]
    untreated = data[data["condition"] == "untreated"]
    treated_samples = cast(pd.Series, treated["sample_name"]).drop_duplicates().tolist()
    untreated_samples = cast(pd.Series, untreated["sample_name"]).drop_duplicates().tolist()
    for treated_sample, untreated_sample in product(treated_samples, untreated_samples):
        treated_pair = cast(pd.DataFrame, treated[treated["sample_name"] == treated_sample])
        untreated_pair = cast(pd.DataFrame, untreated[untreated["sample_name"] == untreated_sample])
        pair_title = f"{experiment} | {treated_sample} (treated) vs {untreated_sample} (untreated)"
        pair_path = output / "mouse_pairs" / experiment / f"{treated_sample}_vs_{untreated_sample}"
        _run_comparison(
            cast(pd.DataFrame, pd.concat([treated_pair, untreated_pair])),
            markers,
            pair_title,
            pair_path,
        )
