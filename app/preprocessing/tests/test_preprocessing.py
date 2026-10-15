"""Tests for notebook-extracted preprocessing functions."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from app.preprocessing.filtering import (
    find_cd45_column,
    find_marker_column,
    plot_cd45_histograms,
    plot_gfp_histograms,
    save_gfp_split,
    split_cells_by_gfp,
)
from app.preprocessing.gating import gate_histones, process_gated_files
from app.preprocessing.loading import load_raw_data, save_loading_summary, summarize_raw_data
from app.preprocessing.transformation import arcsinh_transform, process_arcsinh_files


class PreprocessingTests(unittest.TestCase):
    """Exercise source thresholds, ordering, and metadata preservation."""

    def setUp(self) -> None:
        self.cd45_boundary = 5 * np.sinh(2.0)
        self.gfp_boundary = np.nextafter(5 * np.sinh(2.0), np.inf)
        self.frame = pd.DataFrame(
            {
                "cell_id": ["a-high", "a-low", "excluded", "no-high"],
                "experiment": ["batch2"] * 4,
                "sample_name": ["a", "a", "a", "b"],
                "condition": ["treated"] * 4,
                "replicate": [1] * 4,
                "source_file": ["source.csv"] * 4,
                "source_path": ["source/path"] * 4,
                "raw_row_id": [0, 1, 2, 3],
                "Line": ["L"] * 4,
                "batch": ["B"] * 4,
                "CD45": [self.cd45_boundary, self.cd45_boundary, self.cd45_boundary + 1, 0],
                "GFP": [self.gfp_boundary, 0, self.gfp_boundary, 0],
                "H3.3": [6, 6, 6, 6],
                "H4": [6, 6, 6, 6],
                "marker": [5.0, 10.0, 15.0, 20.0],
            }
        )

    def test_split_preserves_threshold_boundaries_and_omits_zero_high_sample(self) -> None:
        splits, summary = split_cells_by_gfp(self.frame, ["batch2"], {"batch2": 2.0})

        self.assertEqual(list(splits), [("batch2", "a", "GFP_low"), ("batch2", "a", "GFP_high")])
        self.assertEqual(splits[("batch2", "a", "GFP_high")]["cell_id"].tolist(), ["a-high"])
        self.assertEqual(splits[("batch2", "a", "GFP_low")]["cell_id"].tolist(), ["a-low"])
        self.assertEqual(summary[["n_GFP_high", "n_GFP_low"]].values.tolist(), [[1, 1]])

    def test_split_refreshes_files_without_csv_index(self) -> None:
        splits, _ = split_cells_by_gfp(self.frame, ["batch2"], {"batch2": 2.0})
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            target = output / "batch2" / "GFP_high" / "a_GFP_high.csv"
            target.parent.mkdir(parents=True)
            target.write_text("stale output", encoding="utf-8")

            paths = save_gfp_split(splits, output)

            self.assertEqual(len(paths), 2)
            saved = pd.read_csv(target)
            self.assertEqual(saved["cell_id"].tolist(), ["a-high"])
            self.assertFalse(any(column.startswith("Unnamed:") for column in saved.columns))

    def test_histone_gate_uses_strict_raw_thresholds(self) -> None:
        data = self.frame.copy()
        data.loc[1, "H3.3"] = 5
        data.loc[2, "H4"] = 5

        gated = gate_histones(data)

        self.assertEqual(gated["cell_id"].tolist(), ["a-high", "no-high"])

    def test_arcsinh_transforms_markers_but_preserves_metadata(self) -> None:
        legacy_frame = self.frame.assign(**{"Unnamed: 0": range(len(self.frame))})

        transformed, columns = arcsinh_transform(legacy_frame)

        self.assertEqual(columns, ["CD45", "GFP", "H3.3", "H4", "marker"])
        self.assertNotIn("Unnamed: 0", transformed.columns)
        self.assertEqual(transformed["cell_id"].tolist(), self.frame["cell_id"].tolist())
        self.assertEqual(transformed["source_path"].tolist(), self.frame["source_path"].tolist())
        np.testing.assert_allclose(transformed["marker"], np.arcsinh(self.frame["marker"] / 5))

    def test_load_and_summary_preserve_sorted_file_order_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            experiment = root / "batch2"
            experiment.mkdir()
            self.frame.iloc[[1]].to_csv(experiment / "b_raw_data.csv", index=False)
            self.frame.iloc[[0]].to_csv(experiment / "a_raw_data.csv", index=False)

            loaded = load_raw_data(root, ["batch2"])
            summary = summarize_raw_data(loaded)

            self.assertEqual(loaded["cell_id"].tolist(), ["a-high", "a-low"])
            self.assertEqual(summary["n_cells"].tolist(), [2])
            self.assertEqual(summary["first_cell_id"].tolist(), ["a-high"])
            self.assertEqual(summary["last_cell_id"].tolist(), ["a-low"])

    def test_marker_lookup_prefers_exact_case_insensitive_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample_raw_data.csv"
            pd.DataFrame({"CD45-A": [1], "cd45": [2], "my_GFP_marker": [3]}).to_csv(
                path, index=False
            )
            self.assertEqual(find_cd45_column(path), "cd45")
            self.assertEqual(find_marker_column(pd.read_csv(path), "GFP"), "my_GFP_marker")

    def test_marker_lookup_raises_when_marker_is_absent(self) -> None:
        with self.assertRaisesRegex(ValueError, "Could not find marker column"):
            find_marker_column(pd.DataFrame({"CD45": [1]}), "GFP")

    def test_cd45_lookup_falls_back_to_contains_match_and_errors_if_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample_raw_data.csv"
            pd.DataFrame({"fluor_CD45_channel": [1]}).to_csv(path, index=False)
            self.assertEqual(find_cd45_column(path), "fluor_CD45_channel")
            pd.DataFrame({"GFP": [1]}).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "No CD45 column found"):
                find_cd45_column(path)

    def test_histogram_workflows_write_files_and_report_filter_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw" / "batch2"
            raw.mkdir(parents=True)
            pd.DataFrame({"CD45-A": [0.0, 5.0]}).to_csv(raw / "sample_raw_data.csv", index=False)
            cd45_outputs = plot_cd45_histograms(
                root / "raw", ["batch2"], root / "plots", {"batch2": 2.0}
            )
            summary = plot_gfp_histograms(self.frame, ["batch2"], {"batch2": 2.0}, root / "gfp")
            self.assertTrue(cd45_outputs[0].is_file())
            self.assertTrue((root / "gfp" / "batch2_GFP_histogram_CD45neg.png").is_file())
            self.assertEqual(summary[["n_total_valid", "n_cd45neg_kept"]].values.tolist(), [[4, 3]])

    def test_loading_summary_export_has_no_index_column(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            summary = save_loading_summary(self.frame, Path(temporary))
            saved = pd.read_csv(Path(temporary) / "raw_data_loading_summary.csv")
        self.assertEqual(summary["n_cells"].tolist(), [3, 1])
        self.assertFalse(any(column.startswith("Unnamed:") for column in saved.columns))

    def test_gate_and_arcsinh_file_workflows_preserve_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            split_file = root / "split" / "batch2" / "GFP_high" / "sample.csv"
            split_file.parent.mkdir(parents=True)
            self.frame.to_csv(split_file, index=False)
            gated_root = root / "gated"
            summary = process_gated_files(root / "split", gated_root, ["batch2"])
            gated_file = gated_root / "batch2" / "GFP_high" / "treated" / "a_GFP_high_GATED.csv"
            gated = pd.read_csv(gated_file)
            self.assertEqual(summary["n_gated_cells"].tolist(), [4])
            self.assertEqual(gated["cell_id"].tolist(), self.frame["cell_id"].tolist())

            arcsinh_root = root / "arcsinh"
            arcsinh_summary = process_arcsinh_files(gated_root, arcsinh_root)
            arcsinh_file = arcsinh_root / "batch2/GFP_high/treated/a_GFP_high_ARCSINH_5.csv"
            transformed = pd.read_csv(arcsinh_file)
            self.assertEqual(arcsinh_summary["n_cells"].tolist(), [4])
            self.assertAlmostEqual(transformed.loc[0, "marker"], np.arcsinh(5.0 / 5))
            self.assertFalse(any(column.startswith("Unnamed:") for column in transformed.columns))

    def test_file_workflows_raise_for_missing_or_empty_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(FileNotFoundError, "GATED folder not found"):
                process_arcsinh_files(root / "missing", root / "arcsinh")
            empty = root / "empty"
            empty.mkdir()
            with self.assertRaisesRegex(FileNotFoundError, "No gated CSV files"):
                process_arcsinh_files(empty, root / "arcsinh")
            with self.assertRaisesRegex(ValueError, "No cells found"):
                split_cells_by_gfp(self.frame, ["missing"], {"missing": 2.0})


if __name__ == "__main__":
    unittest.main()
