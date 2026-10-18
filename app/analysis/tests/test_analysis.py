"""Tests for the analysis KDE plotting functions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.analysis.kde import plot_kde_comparison
from app.analysis.kde_curves import plot_kde_curves


class KdeTests(unittest.TestCase):
    def test_curves_extract_two_independently_normalized_kde_curves(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        try:
            values = pd.Series([1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
            result = plot_kde_curves(
                ax, [values, values + 1.0], [(0, "untreated", "blue"), (1, "treated", "red")], "M"
            )
            self.assertEqual(
                result["condition"].drop_duplicates().tolist(), ["untreated", "treated"]
            )
            self.assertEqual(result["marker"].unique().tolist(), ["M"])
            self.assertEqual(len(ax.lines), 2)
        finally:
            plt.close(fig)

    def test_curves_skip_groups_with_fewer_than_two_values(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        try:
            result = plot_kde_curves(
                ax, [pd.Series([1.0]), pd.Series([2.0, 3.0])], [(0, "small"), (1, "valid")], "M"
            )
            self.assertEqual(result["condition"].unique().tolist(), ["valid"])
            self.assertEqual(len(ax.lines), 1)
        finally:
            plt.close(fig)

    def test_comparison_preserves_duplicate_markers_and_writes_density_csv(self) -> None:
        import matplotlib.pyplot as plt

        data = pd.DataFrame({"M": [1.0, 2.0, 3.0]})
        density = pd.DataFrame(
            {"marker": ["M"], "condition": ["treated"], "expression": [1.0], "density": [0.5]}
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "plot.png"
            with (
                patch("app.analysis.kde.plot_kde_curves", return_value=density) as curves_plot,
                patch("app.analysis.kde.plt.show"),
            ):
                plot_kde_comparison(
                    [data], [(0, "treated"), (0, "untreated")], ["M", "M"], "title", output
                )

            self.assertEqual(curves_plot.call_count, 2)
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_suffix(".csv").is_file())
        plt.close("all")


if __name__ == "__main__":
    unittest.main()
