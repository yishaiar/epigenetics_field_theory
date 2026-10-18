"""Tests for local environment and output-date configuration."""

import unittest
from unittest.mock import patch

from app.dotenv import get_run_date


class RunDateTests(unittest.TestCase):
    """Verify the date format used for default experiment output folders."""

    def test_get_run_date_formats_current_date_as_ddmmyy(self) -> None:
        with patch("app.dotenv.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "181026"

            result = get_run_date()

            self.assertEqual(result, "181026")
            mock_datetime.now.return_value.strftime.assert_called_once_with("%d%m%y")


if __name__ == "__main__":
    unittest.main()
