"""Tests for notebook-extracted balancing and scaling operations."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from app.harmonization.balancing import balance_samples
from app.harmonization.scaling import (
    combine_scaled_experiments,
    process_scaling_files,
    zscore_markers,
)


class HarmonizationTests(unittest.TestCase):
    """Verify the source notebook's sample ordering and numerical rules."""

    def test_balance_uses_sorted_samples_seed_offsets_and_batch2_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            high_dir = root / "normalized" / "batch3" / "GFP_high"
            high_dir.mkdir(parents=True)
            pd.DataFrame(
                {
                    "cell_id": ["a0", "a1", "a2"],
                    "sample_name": ["a"] * 3,
                    "condition": ["treated"] * 3,
                }
            ).to_csv(high_dir / "a_NORMALIZED.csv", index=False)
            pd.DataFrame(
                {"cell_id": ["b0", "b1"], "sample_name": ["b"] * 2, "condition": ["untreated"] * 2}
            ).to_csv(high_dir / "b_NORMALIZED.csv", index=False)
            skip_dir = root / "normalized" / "batch2" / "GFP_high"
            skip_dir.mkdir(parents=True)
            pd.DataFrame(
                {"cell_id": ["skip"], "sample_name": ["1484"], "condition": ["treated"]}
            ).to_csv(skip_dir / "1484_NORMALIZED.csv", index=False)

            balanced, counts, summary = balance_samples(
                root / "normalized", root / "balanced", ["batch2", "batch3"]
            )

            self.assertEqual(balanced["batch3"]["cell_id"].value_counts().sum(), 4)
            self.assertEqual(balanced["batch3"]["cell_id"].tolist()[2:], ["b1", "b0"])
            self.assertTrue(counts.loc[counts["experiment"] == "batch2", "skipped"].iloc[0])
            self.assertEqual(summary["n_after_balancing"].tolist(), [2, 2])

    def test_zscore_matches_population_standard_deviation_and_keeps_metadata(self) -> None:
        frame = pd.DataFrame(
            {
                "cell_id": ["a", "b", "c"],
                "CD109": [1.0, 2.0, 3.0],
                "H4": [7.0, 7.0, 7.0],
                "DNA": ["x", "x", "x"],
                "not_a_marker": [2.0, 4.0, 6.0],
            }
        )

        scaled, valid, skipped, constant = zscore_markers(frame)

        np.testing.assert_allclose(scaled["CD109"], [-np.sqrt(1.5), 0, np.sqrt(1.5)])
        self.assertEqual(scaled["H4"].tolist(), [0, 0, 0])
        self.assertEqual(scaled["cell_id"].tolist(), ["a", "b", "c"])
        self.assertEqual(valid, ["CD109", "H4"])
        self.assertEqual(skipped, ["DNA"])
        self.assertEqual(constant, ["H4"])

    def test_combine_preserves_experiment_order_and_saves_index_free_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for experiment, cell_id in (("batch3", "b"), ("batch2", "a")):
                pd.DataFrame({"cell_id": [cell_id]}).to_csv(
                    root / f"{experiment}_GFP_high_BALANCED_ZSCORED.csv", index=False
                )

            combined = combine_scaled_experiments(root, ["batch2", "batch3"])
            saved = pd.read_csv(root / "all_GFP_high_BALANCED_ZSCORED.csv")

            self.assertEqual(combined["cell_id"].tolist(), ["a", "b"])
            self.assertEqual(saved.columns.tolist(), ["cell_id"])

    def test_combine_fails_when_an_experiment_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                combine_scaled_experiments(Path(temporary), ["batch2"])

    def test_scaling_file_workflow_writes_zscores_and_proof_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            balanced = root / "balanced"
            balanced.mkdir()
            pd.DataFrame(
                {
                    "cell_id": ["a", "b", "c"],
                    "experiment": ["batch2"] * 3,
                    "CD109": [1.0, 2.0, 3.0],
                    "H4": [7.0, 7.0, 7.0],
                }
            ).to_csv(balanced / "batch2_GFP_high_BALANCED.csv", index=False)

            summary, proof = process_scaling_files(balanced, root / "zscored", ["batch2"])

            output = pd.read_csv(root / "zscored" / "batch2_GFP_high_BALANCED_ZSCORED.csv")
            self.assertEqual(summary["ready_for_umap"].tolist(), [True])
            self.assertEqual(proof["marker"].tolist(), ["CD109", "H4"])
            np.testing.assert_allclose(output["CD109"], [-np.sqrt(1.5), 0, np.sqrt(1.5)])
            self.assertEqual(output["H4"].tolist(), [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
