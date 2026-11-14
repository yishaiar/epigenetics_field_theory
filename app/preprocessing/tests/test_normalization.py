"""Tests for the source notebook's per-file CyTOF normalization calls."""

import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from app.preprocessing.normalization import (
    normalize_pooled_dataframe,
    normalize_sample,
    process_normalization_files,
)


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
                "cell_uid": ["a", "b"],
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
            self.frame, config_factory=NormalizationConfig, transform=transform
        )

        self.assertEqual(markers, ["ACSS2"])
        self.assertEqual(received["config"].values["control_markers"], ["H3.3", "H4"])
        self.assertEqual(received["config"].values["use_compartments"], False)
        self.assertEqual(received["config"].values["n_pcs_for_T"], 1)
        self.assertEqual(received["config"].values["anchor_to_median"], True)
        self.assertEqual(received["config"].values["zscore"], False)
        self.assertEqual(normalized["ACSS2"].tolist(), [10.0, 12.0])
        self.assertEqual(self.frame["ACSS2"].tolist(), [5.0, 6.0])

    def test_normalization_excludes_metadata_and_preserves_all_columns(self) -> None:
        data = self.frame.assign(
            new_marker=[7.0, 8.0],
            labels=["basal", "classical"],
            leiden_cluster=pd.array([0, 1], dtype="Int64"),
            annotation_present=[True, False],
        )

        normalized, markers = normalize_sample(
            data,
            config_factory=NormalizationConfig,
            transform=lambda frame, config: NormalizationResult(frame.assign(ACSS2=[10.0, 12.0])),
            skip_columns=["annotation_present"],
        )

        self.assertEqual(markers, ["ACSS2", "new_marker"])
        self.assertEqual(normalized.columns.tolist(), data.columns.tolist())
        self.assertEqual(normalized["labels"].tolist(), data["labels"].tolist())
        self.assertEqual(normalized["leiden_cluster"].tolist(), data["leiden_cluster"].tolist())
        self.assertEqual(
            normalized["annotation_present"].tolist(), data["annotation_present"].tolist()
        )

    def test_normalize_sample_rejects_missing_controls(self) -> None:
        frame = self.frame.drop(columns="H4")

        with self.assertRaisesRegex(ValueError, "Missing control markers"):
            normalize_sample(frame, NormalizationConfig, lambda data, config: data)

    def test_pooled_normalization_runs_separately_for_each_source_file(self) -> None:
        calls = []
        Config = NormalizationConfig

        def transform(data: pd.DataFrame, config: object) -> NormalizationResult:
            calls.append((data["source_file"].iloc[0], len(data)))
            return NormalizationResult(data.assign(ACSS2=data["ACSS2"] + 100))

        helper = types.ModuleType("cytof_helper.cytof_transform")
        setattr(helper, "CytofTransformConfig", Config)
        setattr(helper, "cytof_transform_global", transform)
        package = types.ModuleType("cytof_helper")
        package.__path__ = []
        sample_one = self.frame.assign(source_file="sample-one.csv")
        sample_two = self.frame.assign(
            cell_uid=["c", "d"],
            source_file="sample-two.csv",
            ACSS2=[7.0, 8.0],
        )
        pooled = pd.concat([sample_one, sample_two], ignore_index=True)
        with patch.dict(
            sys.modules,
            {"cytof_helper": package, "cytof_helper.cytof_transform": helper},
        ):
            normalized, normalized_columns = normalize_pooled_dataframe(
                pooled,
                skip_columns=["cell_uid", "experiment", "sample_name", "condition", "source_file"],
            )

        self.assertEqual(
            calls,
            [
                ("sample-one.csv", 2),
                ("sample-two.csv", 2),
            ],
        )
        self.assertEqual(normalized_columns, ["ACSS2"])
        self.assertEqual(normalized["ACSS2"].tolist(), [105.0, 106.0, 107.0, 108.0])
        self.assertEqual(normalized["cell_uid"].tolist(), ["a", "b", "c", "d"])

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
