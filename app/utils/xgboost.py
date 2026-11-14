"""Reusable XGBoost model fitting and probability prediction."""

from __future__ import annotations

import numpy as np
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


def fit_xgboost_probabilities(
    training_features: np.ndarray,
    training_labels: np.ndarray,
    prediction_features: np.ndarray,
    *,
    n_estimators: int = 100,
    max_depth: int = 3,
    learning_rate: float = 0.1,
    random_state: int = 42,
    n_jobs: int = 1,
) -> tuple[np.ndarray, np.ndarray, XGBClassifier]:
    """Fit an XGBoost classifier and return probabilities in encoded class order.

    Args:
        training_features: Two-dimensional feature matrix used to fit the model.
        training_labels: One-dimensional labels corresponding to training rows.
        prediction_features: Feature rows for which probabilities are returned.
        n_estimators: Number of boosting rounds.
        max_depth: Maximum tree depth.
        learning_rate: Boosting learning rate.
        random_state: Seed for classifier training.
        n_jobs: Number of parallel workers.

    Returns:
        A tuple of class probabilities, original class labels in probability
        column order, and the fitted classifier.

    Raises:
        ValueError: If feature matrices or labels are not row and column aligned,
            or fewer than two training classes are provided.
    """
    training_features = np.asarray(training_features, dtype=np.float32)
    prediction_features = np.asarray(prediction_features, dtype=np.float32)
    training_labels = np.asarray(training_labels)
    if training_features.ndim != 2 or prediction_features.ndim != 2:
        raise ValueError("Training and prediction features must be two-dimensional")
    if training_labels.ndim != 1:
        raise ValueError("Training labels must be one-dimensional")
    if len(training_features) != len(training_labels):
        raise ValueError("Training feature row count must match label count")
    if training_features.shape[1] != prediction_features.shape[1]:
        raise ValueError("Training and prediction features must have matching columns")

    encoder = LabelEncoder()
    encoded_labels = encoder.fit_transform(training_labels)
    class_labels = np.unique(training_labels)
    class_count = len(class_labels)
    if class_count < 2:
        raise ValueError("At least two training classes are required for XGBoost")

    model = XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        objective="binary:logistic" if class_count == 2 else "multi:softprob",
        eval_metric="logloss" if class_count == 2 else "mlogloss",
        subsample=0.8,
        colsample_bytree=1.0,
        tree_method="hist",
        random_state=random_state,
        n_jobs=n_jobs,
        verbosity=0,
    )
    model.fit(training_features, encoded_labels)
    if prediction_features.shape[0]:
        probabilities = np.asarray(model.predict_proba(prediction_features), dtype=np.float32)
    else:
        probabilities = np.empty((0, class_count), dtype=np.float32)
    return probabilities, class_labels, model
