"""Tests for source-notebook-compatible biological comparisons."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.analysis.comparisons import run_biological_comparisons
from app.analysis.kde import plot_kde_comparison, plot_kde_pair


class BiologicalComparisonsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = pd.DataFrame(
            {
                "experiment": ["batch2"] * 4,
                "sample_name": ["t1", "t1", "u1", "u1"],
                "condition": ["treated", "treated", "untreated", "untreated"],
                "labels": ["basal", "classical", "basal", "classical"],
                "M": [1.0, 2.0, 3.0, 4.0],
            }
        )

    def test_runs_pooled_experiment_and_sample_pair_products(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("app.analysis.comparisons.plot_kde_comparison") as plot_kde,
                patch("app.analysis.comparisons._plot_proportions") as plot_proportions,
            ):
                run_biological_comparisons(self.data, ["M", "M"], temp_dir)

        self.assertEqual(plot_kde.call_count, 15)
        self.assertEqual(plot_proportions.call_count, 3)
        self.assertEqual(plot_kde.call_args.args[2], ["M", "M"])
        output_paths = [call.args[4] for call in plot_kde.call_args_list]
        self.assertIn(
            Path(temp_dir) / "mouse_pairs" / "batch2" / "t1_vs_u1" / "all.png", output_paths
        )

    def test_missing_required_columns_raise_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing comparison columns"):
            run_biological_comparisons(self.data.drop(columns="M"), ["M"], "unused")

    def test_empty_marker_list_raises_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one marker"):
            run_biological_comparisons(self.data, [], "unused")

    def test_writes_subtype_proportions_for_pooled_and_pairwise_comparisons(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("app.analysis.comparisons.plot_kde_comparison"),
                patch("matplotlib.pyplot.show"),
            ):
                run_biological_comparisons(self.data, ["M"], temp_dir)

            pooled = pd.read_csv(Path(temp_dir) / "all_experiments" / "subtype_proportions.csv")
            pairwise = pd.read_csv(
                Path(temp_dir) / "mouse_pairs" / "batch2" / "t1_vs_u1" / "subtype_proportions.csv"
            )
        self.assertEqual(pooled["proportion"].tolist(), [0.5, 0.5, 0.5, 0.5])
        self.assertEqual(pairwise["proportion"].tolist(), [0.5, 0.5, 0.5, 0.5])


class KdeTests(unittest.TestCase):
    def test_pair_extracts_two_independently_normalized_kde_curves(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        try:
            values = pd.Series([1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
            result = plot_kde_pair(ax, values + 1.0, values, "M")
            self.assertEqual(
                result["condition"].drop_duplicates().tolist(), ["untreated", "treated"]
            )
            self.assertEqual(result["marker"].unique().tolist(), ["M"])
            self.assertEqual(len(ax.lines), 2)
        finally:
            plt.close(fig)

    def test_pair_skips_groups_with_fewer_than_two_values(self) -> None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        try:
            result = plot_kde_pair(ax, pd.Series([1.0]), pd.Series([2.0, 3.0]), "M")
            self.assertTrue(result.empty)
            self.assertEqual(len(ax.lines), 0)
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
                patch("app.analysis.kde.plot_kde_pair", return_value=density) as pair_plot,
                patch("app.analysis.kde.plt.show"),
            ):
                plot_kde_comparison(data, data, ["M", "M"], "title", output)

            self.assertEqual(pair_plot.call_count, 2)
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_suffix(".csv").is_file())
        plt.close("all")


if __name__ == "__main__":
    unittest.main()
