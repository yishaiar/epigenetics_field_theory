"""Reference checks against the preserved CyTOF workflow artifacts."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from app.harmonization.balancing import process_balancing_files
from app.harmonization.batch_correction import MARKER_COLS, batch_correct
from app.harmonization.scaling import (
    combine_scaled_experiments,
    process_scaling_files,
    zscore_markers,
)


ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "_processed_cytof_pipeline_yishai"
EXPERIMENTS = ["batch2", "batch3", "batch4_extra_treatment"]
BALANCED = (
    REFERENCE / "5. GFP_high_balanced_per_experiment, & Z_scored/GFP_high_balanced_per_experiment"
)
ZSCORED = (
    REFERENCE
    / "5. GFP_high_balanced_per_experiment, & Z_scored/7. GFP_high_balanced_per_experiment_ZSCORED"
)


def assert_frames_match(
    test: unittest.TestCase, actual: pd.DataFrame, expected: pd.DataFrame
) -> None:
    test.assertEqual(actual.columns.tolist(), expected.columns.tolist())
    test.assertEqual(actual.shape, expected.shape)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-10, atol=1e-12)


class HarmonizationReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (REFERENCE / "4. data processing after GFP split/NORMALIZED_d").is_dir():
            raise unittest.SkipTest("Local harmonization reference files are unavailable")

    def test_balance_normalized_reference_samples_matches_saved_balanced_tables(self) -> None:
        normalized = REFERENCE / "4. data processing after GFP split/NORMALIZED_d"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "balanced"
            actual, _, _ = process_balancing_files(normalized, output, EXPERIMENTS)
            for experiment in EXPERIMENTS:
                expected = pd.read_csv(BALANCED / f"{experiment}_GFP_high_BALANCED.csv")
                assert_frames_match(self, actual[experiment], expected)

    def test_zscore_reference_balanced_table_matches_saved_values(self) -> None:
        source = pd.read_csv(BALANCED / "batch2_GFP_high_BALANCED.csv")
        actual, valid, skipped, zero_variance = zscore_markers(source)
        expected = pd.read_csv(ZSCORED / "batch2_GFP_high_BALANCED_ZSCORED.csv")
        self.assertTrue(valid)
        self.assertEqual(skipped, ["H2A"])
        assert_frames_match(self, actual, expected)
        self.assertEqual(zero_variance, [])

    def test_scaling_and_pooling_file_workflows_match_reference_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "zscored"
            shutil.copytree(BALANCED, Path(temp) / "balanced")
            process_scaling_files(Path(temp) / "balanced", output, EXPERIMENTS)
            for experiment in EXPERIMENTS:
                expected = pd.read_csv(ZSCORED / f"{experiment}_GFP_high_BALANCED_ZSCORED.csv")
                actual = pd.read_csv(output / f"{experiment}_GFP_high_BALANCED_ZSCORED.csv")
                assert_frames_match(self, actual, expected)
            pooled = combine_scaled_experiments(output, EXPERIMENTS)
            expected_pooled = pd.read_csv(ZSCORED / "all_GFP_high_BALANCED_ZSCORED.csv")
            assert_frames_match(self, pooled, expected_pooled)

    def test_identity_correction_matches_historical_corrected_file(self) -> None:
        class IdentityModel:
            def transform(
                self, values: NDArray[np.float64], batch_labels: np.ndarray
            ) -> NDArray[np.float64]:
                return values

        arcsinh = (
            REFERENCE
            / "4. data processing after GFP split/ARCSINH_b/batch2/GFP_high/treated"
            / "batch2_1473_gem_GFP_high_ARCSINH_5.csv"
        )
        corrected = (
            REFERENCE
            / "4. data processing after GFP split/BATCH_CORRECTED_c/batch2/GFP_high/treated"
            / "batch2_1473_gem_GFP_high_ARCSINH_5.csv"
        )
        source = pd.read_csv(arcsinh).iloc[:8].copy()
        expected = pd.read_csv(corrected).iloc[:8].copy()
        markers = [column for column in MARKER_COLS if column in source and column in expected]
        invalid = [column for column in source if column not in expected]
        actual = batch_correct(source, markers, "batch2", IdentityModel(), invalid)
        self.assertEqual(actual.columns.tolist(), expected.columns.tolist())
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-7, atol=1e-7)


if __name__ == "__main__":
    unittest.main()
