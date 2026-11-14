"""Tests for reusable XGBoost fitting and probability prediction."""

import unittest

import numpy as np
from xgboost import XGBClassifier

from app.utils.xgboost import fit_xgboost_probabilities


class XGBoostProbabilityTests(unittest.TestCase):
    def test_returns_probabilities_with_original_class_order(self) -> None:
        training_features = np.array([[0.0], [0.1], [0.9], [1.0]])
        training_labels = np.array([2, 2, 7, 7])
        prediction_features = np.array([[0.05], [0.95]])

        probabilities, classes, model = fit_xgboost_probabilities(
            training_features,
            training_labels,
            prediction_features,
            n_estimators=10,
            max_depth=2,
        )

        self.assertEqual(probabilities.shape, (2, 2))
        np.testing.assert_array_equal(classes, [2, 7])
        np.testing.assert_array_equal(model.classes_, [0, 1])
        np.testing.assert_allclose(probabilities.sum(axis=1), np.ones(2))
        self.assertIsInstance(model, XGBClassifier)

    def test_returns_empty_probabilities_for_empty_prediction_rows(self) -> None:
        training_features = np.array([[0.0], [0.1], [0.9], [1.0]])
        training_labels = np.array([0, 0, 1, 1])

        probabilities, classes, model = fit_xgboost_probabilities(
            training_features,
            training_labels,
            np.empty((0, 1)),
            n_estimators=5,
        )

        self.assertEqual(probabilities.shape, (0, 2))
        np.testing.assert_array_equal(classes, [0, 1])
        self.assertIsInstance(model, XGBClassifier)

    def test_rejects_training_feature_and_label_row_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "row count must match"):
            fit_xgboost_probabilities(
                np.array([[0.0], [1.0]]),
                np.array([0]),
                np.array([[0.5]]),
            )

    def test_rejects_mismatched_feature_counts(self) -> None:
        with self.assertRaisesRegex(ValueError, "matching columns"):
            fit_xgboost_probabilities(
                np.array([[0.0, 0.1], [1.0, 0.9]]),
                np.array([0, 1]),
                np.array([[0.5]]),
            )

    def test_rejects_training_data_with_one_class(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least two training classes"):
            fit_xgboost_probabilities(
                np.array([[0.0], [1.0]]),
                np.array([1, 1]),
                np.array([[0.5]]),
            )
