"""Manual and XGBoost labeling copied from active source notebook cells."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from app.config.config import METADATA_COLUMNS
from app.utils.xgboost import fit_xgboost_probabilities


def assign_manual_labels(data: pd.DataFrame) -> np.ndarray:
    """Assign classical, basal, or unassigned labels from UMAP regions."""
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
    features: Sequence[str] | None = None,
) -> tuple[np.ndarray, np.ndarray | None, XGBClassifier | None]:
    """Train from manual labels, then predict labels and probabilities for every row.

    Args:
        data: Table containing the selected classifier feature columns.
        labels: Manual labels aligned with ``data``; -1 marks unassigned rows.
        n_estimators: Number of boosting rounds.
        max_depth: Maximum tree depth.
        learning_rate: Boosting learning rate.
        random_state: Seed for classifier training.
        n_jobs: Number of parallel workers.
        features: Optional feature columns; by default, all numeric, nonmetadata
            columns except UMAP coordinates.

    Returns:
        Predicted labels, probabilities aligned with every input row (or
        ``None`` for single-class training), and the fitted classifier (or
        ``None`` for single-class training).

    Raises:
        ValueError: If labels are misaligned or there are no labeled cells.
    """
    if features is None:
        excluded = {*METADATA_COLUMNS, "UMAP1", "UMAP2"}
        features = [
            column
            for column in data.select_dtypes(include=[np.number]).columns
            if column not in excluded
        ]
    matrix = data[list(features)].to_numpy(dtype=np.float32)
    values = np.asarray(labels, dtype=int)
    if len(matrix) != len(values):
        raise ValueError("Label count must match expression row count")
    train_mask = values != -1
    clusters = np.unique(values[train_mask])
    if len(clusters) == 0:
        raise ValueError("No manually labeled cells remain for XGBoost training")
    if len(clusters) == 1:
        return np.full(len(values), clusters[0], dtype=int), None, None

    probabilities, class_labels, model = fit_xgboost_probabilities(
        matrix[train_mask],
        values[train_mask],
        matrix,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        random_state=random_state,
        n_jobs=n_jobs,
    )
    predicted_labels = class_labels[probabilities.argmax(axis=1)]
    return predicted_labels, probabilities, model


def assign_biological_labels(labels: np.ndarray) -> list[str | int]:
    """Map numeric classifier labels to biological names.

    Args:
        labels: Numeric labels where 0 is classical, 1 is basal, and -1 is
            unassigned.

    Returns:
        Labels mapped to ``classical``, ``basal``, or integer -1.
    """
    names: dict[int, str | int] = {0: "classical", 1: "basal", -1: -1}
    return [names[int(label)] for label in labels]


def save_labeled_data(
    expression: pd.DataFrame, coordinates: pd.DataFrame, labels: np.ndarray, output_file: Path
) -> pd.DataFrame:
    """Attach labels to expression rows after checking cell identity and order.

    Args:
        expression: Expression table containing unique ``cell_uid`` values.
        coordinates: Coordinate table with matching cell identifiers and order.
        labels: Numeric labels aligned with both input tables.
        output_file: Destination CSV path.

    Returns:
        A copy of ``expression`` with biological labels added.

    Raises:
        ValueError: If identifiers, row order, or label count do not align.
    """
    if len(expression) != len(coordinates):
        raise ValueError("Expression and coordinate tables have different row counts")
    if "cell_uid" not in expression or "cell_uid" not in coordinates:
        raise ValueError("Both tables must contain cell_uid")
    if "cell_id" in expression and "cell_id" in coordinates:
        if (
            not expression["cell_id"]
            .reset_index(drop=True)
            .equals(coordinates["cell_id"].reset_index(drop=True))
        ):
            raise ValueError("Expression and UMAP cell_id values/order do not match")
    if (
        bool(expression["cell_uid"].isna().any())
        or bool(coordinates["cell_uid"].isna().any())
        or not expression["cell_uid"].is_unique
        or not coordinates["cell_uid"].is_unique
    ):
        raise ValueError("Expression and UMAP cell_uid values must be non-null and unique")
    if (
        not expression["cell_uid"]
        .reset_index(drop=True)
        .equals(coordinates["cell_uid"].reset_index(drop=True))
    ):
        raise ValueError("Expression and UMAP cell_uid values/order do not match")
    if len(labels) != len(expression):
        raise ValueError("Label count must match expression row count")
    result = expression.copy()
    result["labels"] = assign_biological_labels(labels)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_file, index=False)
    return result
