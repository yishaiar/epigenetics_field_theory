"""Tests for the notebook's batch-correction function."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from app.harmonization.batch_correction import (
    batch_correct,
    fit_batch_correction,
    process_batch_correction_files,
    select_correction_markers,
)


class IdentityCorrectionModel:
    """Minimal transform double for testing the copied notebook function."""

    def transform(self, values: np.ndarray, batch_labels: np.ndarray) -> np.ndarray:
        self.batch_labels = batch_labels
        return values.copy()

    def fit(self, values: np.ndarray, batch_labels: np.ndarray) -> None:
        self.fit_values = values
        self.fit_batch_labels = batch_labels


class BatchCorrectionTests(unittest.TestCase):
    """Check source transform order, metadata, and invalid-value handling."""

    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {
                "cell_id": ["a", "b"],
                "marker": np.arcsinh(np.array([5.0, 10.0]) / 5),
                "invalid": [1.0, 2.0],
            }
        )
        self.model = IdentityCorrectionModel()

    def test_identity_model_round_trip_preserves_values_and_metadata(self) -> None:
        corrected = batch_correct(self.frame, ["marker"], "batch2", self.model, ["invalid"])

        np.testing.assert_allclose(corrected["marker"], self.frame["marker"])
        self.assertEqual(corrected["cell_id"].tolist(), ["a", "b"])
        self.assertNotIn("invalid", corrected.columns)
        self.assertEqual(self.model.batch_labels.tolist(), ["batch2", "batch2"])

    def test_nonfinite_input_is_rejected(self) -> None:
        data = self.frame.copy()
        data.loc[0, "marker"] = np.inf

        with self.assertRaisesRegex(ValueError, "Invalid input values for batch batch2"):
            batch_correct(data, ["marker"], "batch2", self.model)

    def test_nonfinite_model_output_is_rejected(self) -> None:
        class InvalidModel:
            def transform(self, values: np.ndarray, batch_labels: np.ndarray) -> np.ndarray:
                return np.full_like(values, np.nan)

        with self.assertRaisesRegex(ValueError, "Batch correction produced NaN or Inf"):
            batch_correct(self.frame, ["marker"], "batch2", InvalidModel())

    def test_marker_selection_drops_nonfinite_markers_but_keeps_source_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.csv"
            second = root / "second.csv"
            pd.DataFrame({"M2": [1.0], "M1": [2.0], "bad": [np.nan]}).to_csv(first, index=False)
            pd.DataFrame({"M2": [3.0], "M1": [np.inf], "bad": [4.0]}).to_csv(second, index=False)

            markers, invalid, valid = select_correction_markers(
                [first, second], ["M2", "M1"], ["M2", "M1", "bad", "missing"]
            )

            self.assertEqual(markers, ["M2"])
            self.assertEqual(invalid, ["M1", "bad", "missing"])
            self.assertEqual(valid, ["M2"])

    def test_fit_uses_source_factory_settings_and_batch_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for experiment in ("batch2", "batch3"):
                folder = root / experiment / "GFP_high"
                folder.mkdir(parents=True)
                pd.DataFrame(
                    {
                        "cell_id": [f"{experiment}-0", f"{experiment}-1"],
                        "condition": ["treated", "treated"],
                        "M": np.arcsinh(np.array([5.0, 10.0]) / 5),
                    }
                ).to_csv(folder / "sample_ARCSINH_5.csv", index=False)
            captured = {}
            model = IdentityCorrectionModel()

            def factory(**arguments: object) -> IdentityCorrectionModel:
                captured.update(arguments)
                return model

            fitted, markers, invalid, valid, fit_subset = fit_batch_correction(
                root, ["batch2", "batch3"], ["M"], ["M"], factory
            )

            self.assertIs(fitted, model)
            self.assertEqual(markers, ["M"])
            self.assertEqual(invalid, [])
            self.assertEqual(valid, ["M"])
            self.assertEqual(captured["anchor_label"], "batch2")
            self.assertEqual(captured["n_jobs"], -1)
            self.assertEqual(captured["transform_kind"], "arcsinh")
            self.assertEqual(
                captured["q_grid"].tolist(),
                [0, 1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99, 100],
            )
            self.assertEqual(
                model.fit_batch_labels.tolist(), ["batch2", "batch2", "batch3", "batch3"]
            )
            self.assertEqual(
                fit_subset["cell_id"].tolist(),
                ["batch2-1", "batch2-0", "batch3-0", "batch3-1"],
            )

    def test_correction_file_workflow_keeps_relative_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "batch2" / "GFP_high" / "condition" / "sample_ARCSINH_5.csv"
            source.parent.mkdir(parents=True)
            self.frame.drop(columns="invalid").to_csv(source, index=False)

            summary = process_batch_correction_files(
                root,
                root / "corrected",
                ["batch2"],
                IdentityCorrectionModel(),
                ["marker"],
                [],
                ["marker"],
            )

            target = (
                root / "corrected" / "batch2" / "GFP_high" / "condition" / "sample_ARCSINH_5.csv"
            )
            self.assertTrue(target.is_file())
            self.assertEqual(summary["n_cells"].tolist(), [2])


if __name__ == "__main__":
    unittest.main()
