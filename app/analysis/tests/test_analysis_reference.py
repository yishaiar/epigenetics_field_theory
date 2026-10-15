"""Reference checks for the saved analysis tables and density curves."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib.pyplot as plt
import pandas as pd

from app.analysis.comparisons import run_biological_comparisons
from app.analysis.kde import (
    plot_kde_comparison,
    plot_kde_pair,
    plot_treated_subtypes,
    plot_treated_vs_untreated_subtypes,
)


ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "_processed_cytof_pipeline_yishai"
ANALYSIS_REFERENCE = REFERENCE / "8. KDE_analysis/all_experiments"
LABELED = REFERENCE / "7. Clustering/Label/all_GFP_high_BALANCED_ZSCORED_labeled.csv"


class AnalysisReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        if not LABELED.is_file():
            self.skipTest("Local analysis reference files are unavailable")
        self.data = pd.read_csv(LABELED, low_memory=False)

    def test_kde_pair_matches_saved_all_cell_density_curve(self) -> None:
        fig, ax = plt.subplots()
        try:
            treated = self.data.loc[self.data["condition"] == "treated", "TSPAN8"]
            untreated = self.data.loc[self.data["condition"] == "untreated", "TSPAN8"]
            actual = plot_kde_pair(ax, treated, untreated, "TSPAN8")
        finally:
            plt.close(fig)
        expected = pd.read_csv(ANALYSIS_REFERENCE / "all.csv")
        expected = expected.loc[expected["marker"] == "TSPAN8"].reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-5, atol=1e-8)

    def test_kde_comparison_density_export_matches_saved_all_cell_curve(self) -> None:
        treated = self.data.loc[self.data["condition"] == "treated"]
        untreated = self.data.loc[self.data["condition"] == "untreated"]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "all.png"
            with patch("matplotlib.pyplot.show"):
                plot_kde_comparison(treated, untreated, ["TSPAN8"], "All cells", output)
            actual = pd.read_csv(output.with_suffix(".csv"))
        expected = pd.read_csv(ANALYSIS_REFERENCE / "all.csv")
        expected = expected.loc[expected["marker"] == "TSPAN8"].reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-5, atol=1e-8)

    def test_treated_subtype_density_export_matches_saved_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "treated.png"
            with patch("matplotlib.pyplot.show"):
                plot_treated_subtypes(self.data, ["TSPAN8"], output)
            actual = pd.read_csv(output.with_suffix(".csv"))
        expected = pd.read_csv(ANALYSIS_REFERENCE / "treated_subtypes.csv")
        expected = expected.loc[expected["marker"] == "TSPAN8"].reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-5, atol=1e-8)

    def test_treated_untreated_subtype_density_export_matches_saved_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "treated_untreated.png"
            with patch("matplotlib.pyplot.show"):
                plot_treated_vs_untreated_subtypes(self.data, ["TSPAN8"], output)
            actual = pd.read_csv(output.with_suffix(".csv"))
        expected = pd.read_csv(ANALYSIS_REFERENCE / "treated_vs_untreated_subtypes.csv")
        expected = expected.loc[expected["marker"] == "TSPAN8"].reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-5, atol=1e-8)

    def test_comparison_runner_proportions_match_saved_pooled_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with (
                patch("app.analysis.comparisons.plot_kde_comparison"),
                patch("app.analysis.comparisons._plot_proportions"),
            ):
                run_biological_comparisons(self.data, ["TSPAN8"], temp)
            actual = pd.read_csv(Path(temp) / "all_experiments/subtype_proportions.csv")
        expected = pd.read_csv(ANALYSIS_REFERENCE / "subtype_proportions.csv")
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-12, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
