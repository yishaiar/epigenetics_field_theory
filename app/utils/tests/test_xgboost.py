"""Tests for reusable XGBoost fitting and probability prediction."""

import unittest

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from app.utils.xgboost import fit_xgboost_classifier, predict_xgboost_classifier


class XGBoostClassifierTests(unittest.TestCase):
    def test_fit_and_predict_return_probabilities_and_label_encoder(self) -> None:
        training_features = np.array([[0.0], [0.1], [0.9], [1.0]])
        training_labels = np.array([0, 0, 1, 1])
        prediction_data = pd.DataFrame({"marker": [0.05, 0.95]})

        model, encoder = fit_xgboost_classifier(
            training_features,
            training_labels,
            n_estimators=10,
            max_depth=2,
        )
        predicted, probabilities = predict_xgboost_classifier(
            model, prediction_data, ["marker"], encoder
        )

        self.assertEqual(probabilities.shape, (2, 2))
        np.testing.assert_array_equal(encoder.classes_, [0, 1])
        np.testing.assert_array_equal(model.classes_, [0, 1])
        self.assertEqual(len(predicted), 2)
        np.testing.assert_allclose(probabilities.sum(axis=1), np.ones(2))
        self.assertIsInstance(model, XGBClassifier)

    def test_rejects_training_feature_and_label_row_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "row count must match"):
            fit_xgboost_classifier(
                np.array([[0.0], [1.0]]),
                np.array([0]),
            )

    def test_rejects_training_data_with_one_class(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least two training classes"):
            fit_xgboost_classifier(
                np.array([[0.0], [1.0]]),
                np.array([1, 1]),
            )


if __name__ == "__main__":
    unittest.main()
