"""Public namespace tests for plotting."""

import unittest

import scbatch


class TestPlottingNamespace(unittest.TestCase):
    def test_package_exposes_plotting_namespace(self) -> None:
        self.assertIsNotNone(scbatch.pl)

    def test_package_exports_plotting_functions(self) -> None:
        self.assertTrue(callable(scbatch.pl.qqplot))
        self.assertTrue(callable(scbatch.pl.histplot_comparison))
        self.assertIs(scbatch.pl.qqplot, scbatch.pl.qqplot)
