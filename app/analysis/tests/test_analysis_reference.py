"""Reference checks for the saved analysis tables and density curves."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib.pyplot as plt
import pandas as pd

from app.analysis.kde_curves import plot_kde_curves
from app.analysis.kde import (
    plot_kde_comparison,
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

    def test_kde_curves_matches_saved_all_cell_density_curve(self) -> None:
        fig, ax = plt.subplots()
        try:
            treated = self.data.loc[self.data["condition"] == "treated", "TSPAN8"]
            untreated = self.data.loc[self.data["condition"] == "untreated", "TSPAN8"]
            actual = plot_kde_curves(
                ax,
                [untreated, treated],
                [(0, "untreated", "blue"), (1, "treated", "red")],
                "TSPAN8",
            )
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
                plot_kde_comparison(
                    [untreated, treated],
                    [(0, "untreated", "blue"), (1, "treated", "red")],
                    ["TSPAN8"],
                    "All cells",
                    output,
                )
            actual = pd.read_csv(output.with_suffix(".csv"))
        expected = pd.read_csv(ANALYSIS_REFERENCE / "all.csv")
        expected = expected.loc[expected["marker"] == "TSPAN8"].reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-5, atol=1e-8)


if __name__ == "__main__":
    unittest.main()
