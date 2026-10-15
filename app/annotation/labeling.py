"""Manual and XGBoost labeling copied from active source notebook cells."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


def assign_manual_labels(data: pd.DataFrame) -> np.ndarray:
    """Apply the exact classical/basal UMAP regions in source cell 56."""
    labels = np.full(len(data), -1, dtype=int)
    labels[(data["UMAP1"].to_numpy() > 5) & (data["UMAP2"].to_numpy() > 12)] = 0
    labels[(data["UMAP1"].to_numpy() < 0) & (data["UMAP2"].to_numpy() > 10)] = 1
    labels[data["UMAP1"].to_numpy() < -5] = 1
    return labels


def predict_noise_xgboost(
    data: pd.DataFrame,
    labels: np.ndarray,
    n_estimators: int = 100,
    max_depth: int = 3,
    learning_rate: float = 0.1,
    random_state: int = 42,
    n_jobs: int = 1,
    features: list[str] | None = None,
) -> tuple[np.ndarray, XGBClassifier | None]:
    """Fill manually-unassigned cells using the original three-marker XGBoost."""
    features = ["GAL4", "GATA6", "TSPAN8"] if features is None else features
    matrix = data[features].to_numpy(dtype=np.float32)
    values = np.asarray(labels, dtype=int)
    if len(matrix) != len(values):
        raise ValueError("Label count must match expression row count")
    noise_mask, train_mask = values == -1, values != -1
    clusters = np.unique(values[train_mask])
    if len(clusters) == 0:
        raise ValueError("No manually labeled cells remain for XGBoost training")
    final_labels, model = values.copy(), None
    if noise_mask.any():
        if len(clusters) == 1:
            final_labels[noise_mask] = clusters[0]
        else:
            final_labels[noise_mask], model = _fit_xgboost(
                matrix,
                values,
                train_mask,
                noise_mask,
                n_estimators,
                max_depth,
                learning_rate,
                random_state,
                n_jobs,
                len(clusters),
            )
    return final_labels, model


def _fit_xgboost(
    matrix: np.ndarray,
    labels: np.ndarray,
    train_mask: np.ndarray,
    noise_mask: np.ndarray,
    n_estimators: int,
    max_depth: int,
    learning_rate: float,
    random_state: int,
    n_jobs: int,
    class_count: int,
) -> tuple[np.ndarray, XGBClassifier]:
    """Fit the source XGBoost classifier and predict only the unassigned rows."""
    encoder = LabelEncoder()
    y_train = encoder.fit_transform(labels[train_mask])
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
    model.fit(matrix[train_mask], y_train)
    probabilities = model.predict_proba(matrix[noise_mask])
    predicted = encoder.inverse_transform(probabilities.argmax(axis=1))
    return predicted, model


def assign_biological_labels(labels: np.ndarray) -> list[str | int]:
    """Map source numeric manual/XGBoost labels to the original biological names."""
    names: dict[int, str | int] = {0: "classical", 1: "basal", -1: -1}
    return [names[int(label)] for label in labels]


def save_labeled_data(
    expression: pd.DataFrame, coordinates: pd.DataFrame, labels: np.ndarray, output_file: Path
) -> pd.DataFrame:
    """Check cell identity/order before attaching labels and saving scaled rows."""
    if len(expression) != len(coordinates):
        raise ValueError("Expression and coordinate tables have different row counts")
    if "cell_id" not in expression or "cell_id" not in coordinates:
        raise ValueError("Both tables must contain cell_id")
    if (
        not expression["cell_id"]
        .reset_index(drop=True)
        .equals(coordinates["cell_id"].reset_index(drop=True))
    ):
        raise ValueError("Expression and UMAP cell_id values/order do not match")
    if len(labels) != len(expression):
        raise ValueError("Label count must match expression row count")
    result = expression.copy()
    result["labels"] = assign_biological_labels(labels)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_file, index=False)
    return result
