"""Tests for the source notebook's per-file CyTOF normalization calls."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from app.harmonization.normalization import normalize_sample, process_normalization_files


class NormalizationConfig:
    """Capture normalization parameters supplied by the extracted workflow."""

    def __init__(self, **values: object) -> None:
        self.values = values


class NormalizationResult:
    """Match the helper result object's `.corrected` surface."""

    def __init__(self, corrected: pd.DataFrame) -> None:
        self.corrected = corrected


class NormalizationTests(unittest.TestCase):
    """Check source marker selection, call settings, and file output layout."""

    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {
                "cell_id": ["a", "b"],
                "experiment": ["batch2", "batch2"],
                "sample_name": ["sample1", "sample1"],
                "condition": ["treated", "treated"],
                "H3.3": [1.0, 2.0],
                "H4": [3.0, 4.0],
                "ACSS2": [5.0, 6.0],
                "EZH2": ["bad", "data"],
            }
        )

    def test_normalize_sample_uses_source_config_and_returns_corrected_copy(self) -> None:
        received = {}

        def transform(data: pd.DataFrame, config: object) -> NormalizationResult:
            received["input"] = data
            received["config"] = config
            return NormalizationResult(data.assign(ACSS2=[10.0, 12.0]))

        normalized, markers = normalize_sample(
            self.frame, NormalizationConfig, transform, ["H3.3", "H4"], ["ACSS2", "EZH2"]
        )

        self.assertEqual(markers, ["ACSS2"])
        self.assertEqual(received["config"].values["control_markers"], ["H3.3", "H4"])
        self.assertEqual(received["config"].values["use_compartments"], False)
        self.assertEqual(received["config"].values["n_pcs_for_T"], 1)
        self.assertEqual(received["config"].values["anchor_to_median"], True)
        self.assertEqual(received["config"].values["zscore"], False)
        self.assertEqual(normalized["ACSS2"].tolist(), [10.0, 12.0])
        self.assertEqual(self.frame["ACSS2"].tolist(), [5.0, 6.0])

    def test_normalization_excludes_and_preserves_annotation_metadata(self) -> None:
        data = self.frame.assign(
            labels=["basal", "classical"],
            leiden_cluster=pd.array([0, 1], dtype="Int64"),
            annotation_present=[True, False],
        )

        normalized, markers = normalize_sample(
            data,
            NormalizationConfig,
            lambda frame, config: NormalizationResult(frame.assign(labels=["changed", "changed"])),
            ["H3.3", "H4"],
            ["ACSS2", "labels", "leiden_cluster", "annotation_present"],
        )

        self.assertEqual(markers, ["ACSS2"])
        self.assertEqual(normalized["labels"].tolist(), data["labels"].tolist())
        self.assertEqual(normalized["leiden_cluster"].tolist(), data["leiden_cluster"].tolist())
        self.assertEqual(
            normalized["annotation_present"].tolist(), data["annotation_present"].tolist()
        )

    def test_normalize_sample_rejects_missing_controls(self) -> None:
        frame = self.frame.drop(columns="H4")

        with self.assertRaisesRegex(ValueError, "Missing control markers"):
            normalize_sample(frame, NormalizationConfig, lambda data, config: data)

    def test_normalization_file_workflow_writes_source_names_and_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "corrected" / "batch2" / "GFP_high" / "sample_ARCSINH_5.csv"
            source.parent.mkdir(parents=True)
            self.frame.to_csv(source, index=False)

            summary, inputs = process_normalization_files(
                root / "corrected",
                root / "normalized",
                NormalizationConfig,
                lambda data, config: NormalizationResult(data.copy()),
            )

            output = root / "normalized" / "batch2" / "GFP_high" / "sample_NORMALIZED.csv"
            self.assertTrue(output.is_file())
            self.assertEqual(summary["n_cells"].tolist(), [2])
            self.assertEqual(inputs["gfp_group"].tolist(), ["GFP_high"])
            self.assertFalse(any(column.startswith("Unnamed:") for column in pd.read_csv(output)))


if __name__ == "__main__":
    unittest.main()
