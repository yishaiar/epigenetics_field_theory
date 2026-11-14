"""Tests for the pooled loading, gating, and ArcSinh steps in Notebook 2."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from app.preprocessing import arcsinh_transform, gate_histones, pool_csv_files


class PooledPreparationTests(unittest.TestCase):
    """Check row pooling and pooled transformations used by the notebook."""

    def setUp(self) -> None:
        self.metadata = ["cell_id", "sample_name", "condition", "source_file"]

    def test_pooling_stacks_rows_and_records_full_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "batch2" / "GFP_high" / "mouse_a.csv"
            second = root / "batch3" / "GFP_low" / "mouse_b.csv"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            pd.DataFrame({"cell_id": ["a"], "marker": [1.0], "first_missing": [None]}).to_csv(
                first, index=False
            )
            pd.DataFrame({"cell_id": ["b"], "marker": [2.0], "second_missing": [None]}).to_csv(
                second, index=False
            )
            output = root / "pooled.csv"

            pooled, missing_columns_by_sample = pool_csv_files(
                [first, second], output, source_column="source_file"
            )

            self.assertEqual(pooled["cell_id"].tolist(), ["a", "b"])
            self.assertEqual(
                missing_columns_by_sample,
                {
                    "first_missing": ["mouse_a"],
                    "second_missing": ["mouse_b"],
                },
            )
            self.assertEqual(
                pooled["source_file"].tolist(),
                [str(first.resolve()), str(second.resolve())],
            )
            pd.testing.assert_frame_equal(pd.read_csv(output), pooled)

    def test_pooling_rejects_empty_or_missing_input_files(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one input"):
            pool_csv_files([])
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(FileNotFoundError, "do not exist"):
                pool_csv_files([Path(temporary) / "missing.csv"])

    def test_pooled_histone_gate_uses_strict_thresholds_and_preserves_columns(self) -> None:
        data = pd.DataFrame(
            {
                "cell_id": ["pass", "h3-boundary", "h4-boundary"],
                "sample_name": ["mouse"] * 3,
                "condition": ["treated"] * 3,
                "source_file": ["mouse.csv"] * 3,
                "H3.3": [6.0, 5.0, 6.0],
                "H4": [6.0, 6.0, 5.0],
                "marker": [1.0, 2.0, 3.0],
            }
        )

        gated, gate_columns = gate_histones(
            data,
            skip_columns=self.metadata,
            lower_outlier_quantile=0,
            upper_outlier_quantile=1,
        )

        self.assertEqual(gated["cell_id"].tolist(), ["pass"])
        self.assertEqual(gate_columns, ["H3.3", "H4", "marker"])
        self.assertEqual(gated.columns.tolist(), data.columns.tolist())

    def test_pooled_histone_gate_removes_outliers_within_each_mouse(self) -> None:
        cells_per_mouse = 100
        mouse_values = np.arange(cells_per_mouse, dtype=float) + 10
        data = pd.DataFrame(
            {
                "cell_id": [f"mouse1-{i}" for i in range(cells_per_mouse)]
                + [f"mouse2-{i}" for i in range(cells_per_mouse)],
                "sample_name": ["mouse1"] * cells_per_mouse + ["mouse2"] * cells_per_mouse,
                "experiment": ["batch2"] * (2 * cells_per_mouse),
                "condition": ["treated"] * (2 * cells_per_mouse),
                "source_file": ["mouse1.csv"] * cells_per_mouse + ["mouse2.csv"] * cells_per_mouse,
                "H3.3": np.concatenate([mouse_values, mouse_values + 1000]),
                "H4": np.concatenate([mouse_values, mouse_values + 2000]),
                "marker": np.concatenate([mouse_values, mouse_values + 3000]),
            }
        )

        gated, gate_columns = gate_histones(data, skip_columns=self.metadata)

        self.assertEqual(gate_columns, ["H3.3", "H4", "marker"])
        self.assertEqual(
            gated.groupby("sample_name").size().to_dict(), {"mouse1": 98, "mouse2": 98}
        )
        self.assertEqual(
            gated["cell_id"].tolist(),
            [
                *(f"mouse1-{i}" for i in range(1, 99)),
                *(f"mouse2-{i}" for i in range(1, 99)),
            ],
        )

    def test_pooled_arcsinh_transforms_markers_and_preserves_metadata(self) -> None:
        data = pd.DataFrame(
            {
                "cell_id": ["a", "b"],
                "sample_name": ["mouse"] * 2,
                "condition": ["treated"] * 2,
                "source_file": ["mouse.csv"] * 2,
                "marker": [5.0, 10.0],
                "labels": ["basal", "classical"],
                "Unnamed: 0": [0, 1],
            }
        )

        transformed, markers = arcsinh_transform(
            data, skip_columns=self.metadata + ["labels", "Unnamed: 0"]
        )

        self.assertEqual(markers, ["marker"])
        self.assertIn("Unnamed: 0", transformed.columns)
        self.assertEqual(transformed["Unnamed: 0"].tolist(), data["Unnamed: 0"].tolist())
        self.assertEqual(transformed["labels"].tolist(), data["labels"].tolist())
        np.testing.assert_allclose(transformed["marker"], np.arcsinh(data["marker"] / 5))
        pd.testing.assert_frame_equal(transformed[self.metadata], data[self.metadata])


if __name__ == "__main__":
    unittest.main()
