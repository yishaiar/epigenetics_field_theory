"""Tests for balanced-reference scaling used by Notebook 2."""

import unittest
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from app.preprocessing.scaling import zscore_markers_from_balanced_reference


class BalancedReferenceScalingTests(unittest.TestCase):
    """Check reference allocation, deterministic fitting, and output preservation."""

    def setUp(self) -> None:
        rows = []
        for condition in ("untreated", "treated"):
            for subtype in ("basal", "classical"):
                for mouse, count in (("mouse1", 5), ("mouse2", 1)):
                    for cell_number in range(count):
                        rows.append(
                            {
                                "cell_uid": (f"{condition}-{subtype}-{mouse}-{cell_number}"),
                                "condition": condition,
                                "labels": subtype,
                                "experiment": "batch2",
                                "sample_name": mouse,
                                "marker": float(len(rows) + 1),
                                "leiden_cluster": cell_number % 2,
                            }
                        )
        self.data = pd.DataFrame(rows)
        self.skip_columns = [
            "cell_uid",
            "condition",
            "labels",
            "experiment",
            "sample_name",
        ]

    def test_balanced_reference_is_seeded_and_preserves_all_rows_and_metadata(self) -> None:
        with patch("app.preprocessing.scaling.dotenv_values", return_value={"RANDOM_STATE": "42"}):
            scaled, allocation, reference_ids = zscore_markers_from_balanced_reference(
                self.data, skip_columns=self.skip_columns
            )
            repeated, _, repeated_ids = zscore_markers_from_balanced_reference(
                self.data, skip_columns=self.skip_columns
            )

        self.assertEqual(reference_ids, repeated_ids)
        self.assertEqual(len(reference_ids), 12)
        self.assertEqual(len(scaled), len(self.data))
        self.assertEqual(scaled.columns.tolist(), self.data.columns.tolist())
        assert_frame_equal(scaled[self.skip_columns], self.data[self.skip_columns])
        assert_frame_equal(scaled, repeated)
        allocation_counts = allocation.groupby(["condition", "labels"])["n_allocated_cells"].sum()
        self.assertEqual(
            allocation_counts.to_dict(),
            {
                ("treated", "basal"): 3,
                ("treated", "classical"): 3,
                ("untreated", "basal"): 3,
                ("untreated", "classical"): 3,
            },
        )
        group_sizes = allocation.groupby(["condition", "labels"])["n"].first()
        self.assertEqual(group_sizes.to_dict(), {group: 6 for group in allocation_counts.index})
        reference_sizes = allocation.groupby(["condition", "labels"])["n_reference_cells"].first()
        self.assertEqual(reference_sizes.to_dict(), {group: 3 for group in allocation_counts.index})

    def test_reference_scaling_rejects_missing_biological_groups(self) -> None:
        incomplete = self.data.loc[
            ~(self.data["condition"].eq("treated") & self.data["labels"].eq("classical"))
        ]

        with self.assertRaisesRegex(ValueError, "Missing required condition-subtype groups"):
            zscore_markers_from_balanced_reference(
                incomplete, skip_columns=self.skip_columns, random_state=42
            )

    def test_reference_size_uses_group_sizes_and_requested_cap(self) -> None:
        rows = []
        for condition in ("untreated", "treated"):
            for subtype in ("basal", "classical"):
                for mouse in ("mouse1", "mouse2"):
                    if condition == "treated" and subtype == "basal" and mouse == "mouse2":
                        continue
                    for cell_number in range(5):
                        rows.append(
                            {
                                "cell_uid": f"{condition}-{subtype}-{mouse}-{cell_number}",
                                "condition": condition,
                                "labels": subtype,
                                "experiment": "batch2",
                                "sample_name": mouse,
                                "marker": float(len(rows) + 1),
                            }
                        )
        data = pd.DataFrame(rows)

        _, allocation, reference_ids = zscore_markers_from_balanced_reference(
            data,
            skip_columns=self.skip_columns,
            n_reference_cells_per_group=100,
            random_state=42,
        )

        self.assertEqual(len(reference_ids), 4)
        group_totals = allocation.groupby(["condition", "labels"])["n"].first().to_dict()
        self.assertEqual(
            group_totals,
            {
                ("treated", "basal"): 5,
                ("treated", "classical"): 10,
                ("untreated", "basal"): 10,
                ("untreated", "classical"): 10,
            },
        )
        allocation_counts = allocation.groupby(["condition", "labels"])["n_allocated_cells"].sum()
        self.assertEqual(allocation_counts.to_dict(), {group: 1 for group in group_totals})
        reference_sizes = allocation.groupby(["condition", "labels"])["n_reference_cells"].first()
        self.assertEqual(reference_sizes.to_dict(), {group: 1 for group in group_totals})

        _, capped_allocation, capped_reference_ids = zscore_markers_from_balanced_reference(
            self.data,
            skip_columns=self.skip_columns,
            n_reference_cells_per_group=2,
            random_state=42,
        )
        self.assertEqual(len(capped_reference_ids), 8)
        capped_sizes = capped_allocation.groupby(["condition", "labels"])[
            "n_reference_cells"
        ].first()
        self.assertEqual(capped_sizes.to_dict(), {group: 2 for group in capped_sizes.index})


if __name__ == "__main__":
    unittest.main()
