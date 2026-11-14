"""Compare pooled gate and ArcSinh operations with historical reference rows."""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from app.preprocessing import arcsinh_transform, gate_histones


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REFERENCE_ROOT = PROJECT_ROOT / "_processed_cytof_pipeline_yishai"
SAMPLE_NAME = "batch2_1473_gem"
EXPERIMENT = "batch2"


def _read_reference_csv(relative_path: str) -> pd.DataFrame:
    """Read one optional historical reference CSV for focused comparisons."""
    path = REFERENCE_ROOT / relative_path
    if not path.is_file():
        raise unittest.SkipTest(f"Reference CSV is unavailable: {path}")
    return pd.read_csv(path, low_memory=False)


def _assert_matches_reference(actual: pd.DataFrame, reference: pd.DataFrame) -> None:
    """Compare shared source columns, ignoring the saved CSV index artifact."""
    actual = actual.drop(columns="Unnamed: 0", errors="ignore").reset_index(drop=True)
    reference = reference.drop(columns="Unnamed: 0", errors="ignore")
    reference = reference.loc[:, actual.columns].reset_index(drop=True)
    assert_frame_equal(
        actual,
        reference,
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=0,
    )


class HarmonizationReferenceUnitTests(unittest.TestCase):
    """Check gate and ArcSinh outputs against small historical slices."""

    def test_gate_matches_reference_rows_for_a_small_split_slice(self) -> None:
        relative = (
            f"4. data processing after GFP split/GATED_a/{EXPERIMENT}/GFP_high/treated/"
            f"{SAMPLE_NAME}_GFP_high_GATED.csv"
        )
        gated_reference = _read_reference_csv(relative)
        split_reference = _read_reference_csv(
            f"3. GFP split after CD45 exclusion/{EXPERIMENT}/GFP_high/{SAMPLE_NAME}_GFP_high.csv"
        )
        input_slice = split_reference.head(5)
        expected = gated_reference.loc[gated_reference["cell_id"].isin(input_slice["cell_id"])]

        actual, _ = gate_histones(input_slice)

        _assert_matches_reference(actual, expected)
        self.assertEqual(actual["cell_id"].tolist(), expected["cell_id"].tolist())

    def test_arcsinh_matches_reference_for_three_gated_cells(self) -> None:
        base = "4. data processing after GFP split"
        gated_reference = _read_reference_csv(
            f"{base}/GATED_a/{EXPERIMENT}/GFP_high/treated/{SAMPLE_NAME}_GFP_high_GATED.csv"
        ).head(3)
        arcsinh_reference = _read_reference_csv(
            f"{base}/ARCSINH_b/{EXPERIMENT}/GFP_high/treated/{SAMPLE_NAME}_GFP_high_ARCSINH_5.csv"
        )
        expected = arcsinh_reference.loc[
            arcsinh_reference["cell_id"].isin(gated_reference["cell_id"])
        ]

        actual, transformed_columns = arcsinh_transform(gated_reference)

        _assert_matches_reference(actual, expected)
        self.assertIn("H3.3", transformed_columns)
        self.assertIn("H4", transformed_columns)
        np.testing.assert_allclose(
            actual[["H3.3", "H4"]].to_numpy(),
            expected[["H3.3", "H4"]].to_numpy(),
            rtol=1e-12,
            atol=0,
        )


if __name__ == "__main__":
    unittest.main()
