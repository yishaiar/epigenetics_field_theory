"""Tests for local environment and output-date configuration."""

import unittest
from unittest.mock import patch

from app.config import get_run_date
from app.config.config import (
    CD45_CUTOFFS_ASINH,
    EXPERIMENTS,
    GFP_CUTOFFS_ASINH,
    BASAL_CLASSICAL_SEPARATING_MARKERS,
)


class RunDateTests(unittest.TestCase):
    """Verify the date format used for default experiment output folders."""

    def test_get_run_date_formats_current_date_as_ddmmyy(self) -> None:
        with patch("app.config.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "181026"

            result = get_run_date()

            self.assertEqual(result, "181026")
            mock_datetime.now.return_value.strftime.assert_called_once_with("%d%m%y")


class SharedAnalysisSettingsTests(unittest.TestCase):
    """Verify shared settings consumed by the staged analysis notebooks."""

    def test_shared_analysis_settings_preserve_notebook_contract(self) -> None:
        self.assertEqual(EXPERIMENTS, ["batch2", "batch3", "batch4_extra_treatment"])
        self.assertEqual(
            CD45_CUTOFFS_ASINH,
            {"batch2": 2.0, "batch3": 2.0, "batch4_extra_treatment": 2.0},
        )
        self.assertEqual(
            GFP_CUTOFFS_ASINH,
            {"batch2": 2.0, "batch3": 4.0, "batch4_extra_treatment": 3.0},
        )
        self.assertEqual(BASAL_CLASSICAL_SEPARATING_MARKERS.count("CD109"), 2)


if __name__ == "__main__":
    unittest.main()
