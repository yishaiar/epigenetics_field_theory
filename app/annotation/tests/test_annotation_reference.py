"""Reference checks for annotation outputs retained from the source workflow."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.annotation.embedding import load_umap
from app.annotation.embedding import calculate_umap
from app.annotation.labeling import (
    assign_biological_labels,
    assign_manual_labels,
    predict_noise_xgboost,
)


ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "_processed_cytof_pipeline_yishai"
UMAP_ROOT = REFERENCE / "6. plots - GFP+ analyses/GFP_high_balanced_ZSCORED_UMAP_by_marker_group"
EXPRESSION_FILE = (
    REFERENCE
    / "5. GFP_high_balanced_per_experiment, & Z_scored/7. GFP_high_balanced_per_experiment_ZSCORED"
    / "all_GFP_high_BALANCED_ZSCORED.csv"
)
LABELED_FILE = REFERENCE / "7. Clustering/Label/all_GFP_high_BALANCED_ZSCORED_labeled.csv"
UMAP_SUMMARY = UMAP_ROOT / "UMAP_summary_cell_identity_and_epigenetic.csv"


class AnnotationReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not UMAP_SUMMARY.is_file() or not LABELED_FILE.is_file():
            raise unittest.SkipTest("Local annotation reference files are unavailable")

    def test_umap_loader_matches_reference_coordinate_export(self) -> None:
        actual = load_umap(UMAP_ROOT, "all", "cell_identity")
        expected = pd.read_csv(
            UMAP_ROOT
            / "UMAP_cell_identity/coordinates/all/all_cell_identity_UMAP_coordinates_all_cells.csv"
        )
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False)

    @pytest.mark.slow
    def test_calculated_umap_coordinates_match_saved_reference(self) -> None:
        summary = pd.read_csv(UMAP_SUMMARY).iloc[0]
        data = pd.read_csv(EXPRESSION_FILE, low_memory=False)
        markers = str(summary["markers_used"]).split(", ")
        with tempfile.TemporaryDirectory() as temp:
            with patch(
                "app.annotation.embedding._save_embedding_plots",
                return_value=(Path("full.png"), Path("condition.png")),
            ):
                actual, _ = calculate_umap(
                    data,
                    markers,
                    "cell_identity",
                    "all",
                    {},
                    Path(temp),
                )
        expected = load_umap(UMAP_ROOT, "all", "cell_identity")
        self.assertEqual(actual["cell_id"].tolist(), expected["cell_id"].tolist())
        np.testing.assert_allclose(
            actual[["UMAP1", "UMAP2"]],
            expected[["UMAP1", "UMAP2"]],
            rtol=1e-5,
            atol=1e-5,
        )

    def test_manual_and_xgboost_labels_match_historical_labeled_export(self) -> None:
        coordinates = load_umap(UMAP_ROOT, "all", "cell_identity")
        expression = pd.read_csv(EXPRESSION_FILE, low_memory=False)
        expected = pd.read_csv(LABELED_FILE, low_memory=False)
        self.assertEqual(expression["cell_id"].tolist(), coordinates["cell_id"].tolist())
        np.testing.assert_array_equal(expected["cell_id"], expression["cell_id"])

        manual = assign_manual_labels(coordinates)
        predicted, _ = predict_noise_xgboost(expression, manual)
        actual_names = assign_biological_labels(predicted)
        self.assertEqual(actual_names, expected["labels"].tolist())


if __name__ == "__main__":
    unittest.main()
