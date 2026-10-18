"""Reference regression test against the local historical preprocessing outputs."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.preprocessing.filtering import save_gfp_split, split_cells_by_gfp
from app.preprocessing.gating import process_gated_files
from app.preprocessing.loading import load_raw_data
from app.preprocessing.transformation import process_arcsinh_files


@pytest.mark.slow
class PreprocessingReferenceTests(unittest.TestCase):
    """Compare fresh Stage 1 artifacts with the available local reference corpus."""

    experiments = ["batch2", "batch3", "batch4_extra_treatment"]
    cutoffs = {"batch2": 2.0, "batch3": 4.0, "batch4_extra_treatment": 3.0}

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[3]
        cls.raw_root = cls.project_root / "raw_data"
        cls.reference_root = cls.project_root / "_processed_cytof_pipeline_yishai"
        if not cls.raw_root.is_dir() or not cls.reference_root.is_dir():
            raise unittest.SkipTest("Local CyTOF inputs or reference outputs are unavailable")

        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.output_root = Path(cls.temporary_directory.name)
        loaded = load_raw_data(cls.raw_root, cls.experiments)
        splits, _ = split_cells_by_gfp(loaded, cls.experiments, cls.cutoffs)

        cls.split_root = cls.output_root / "split"
        save_gfp_split(splits, cls.split_root)
        cls.gated_root = cls.output_root / "gated"
        process_gated_files(cls.split_root, cls.gated_root, cls.experiments)
        cls.arcsinh_root = cls.output_root / "arcsinh"
        process_arcsinh_files(cls.gated_root, cls.arcsinh_root)

    @classmethod
    def tearDownClass(cls) -> None:
        temporary_directory = getattr(cls, "temporary_directory", None)
        if temporary_directory is not None:
            temporary_directory.cleanup()

    def test_stage_one_outputs_match_reference_files(self) -> None:
        reference_stages = [
            (
                self.split_root,
                self.reference_root / "3. GFP split after CD45 exclusion",
            ),
            (
                self.gated_root,
                self.reference_root / "4. data processing after GFP split" / "GATED_a",
            ),
            (
                self.arcsinh_root,
                self.reference_root / "4. data processing after GFP split" / "ARCSINH_b",
            ),
        ]
        for actual_root, reference_root in reference_stages:
            self._assert_csv_tree_matches(actual_root, reference_root)

    def _assert_csv_tree_matches(self, actual_root: Path, reference_root: Path) -> None:
        actual_files = {
            path.relative_to(actual_root): path
            for path in actual_root.rglob("*.csv")
            if not path.name.endswith("summary.csv")
        }
        reference_files = {
            path.relative_to(reference_root): path
            for path in reference_root.rglob("*.csv")
            if not path.name.endswith("summary.csv")
        }
        self.assertEqual(set(actual_files), set(reference_files))

        for relative_path, actual_path in actual_files.items():
            actual = pd.read_csv(actual_path, low_memory=False)
            reference = pd.read_csv(reference_files[relative_path], low_memory=False)
            self.assertIn("Unnamed: 0", reference.columns)
            self.assertNotIn("Unnamed: 0", actual.columns)
            reference = reference.drop(columns=["Unnamed: 0"])
            assert_frame_equal(
                actual,
                reference,
                check_dtype=False,
                check_exact=False,
                rtol=1e-12,
                atol=0,
            )


if __name__ == "__main__":
    unittest.main()
