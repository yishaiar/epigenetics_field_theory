"""Focused parity checks for notebook-extracted annotation operations."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from app.annotation.clustering import (
    calc_leiden,
    plot_cluster_heatmap,
    plot_clusters,
    plot_clusters_by_condition,
)
from app.annotation.embedding import (
    calculate_umap,
    get_umap_markers,
    plot_condition_umap,
    plot_full_umap,
)
from app.annotation.labeling import (
    assign_biological_labels,
    assign_manual_labels,
    predict_noise_xgboost,
    save_labeled_data,
)
from app.annotation.plotting import plot_umap_class_probabilities, plot_umap_staining


class ManualLabelTests(unittest.TestCase):
    def test_source_region_boundaries_and_precedence(self) -> None:
        coordinates = pd.DataFrame(
            {
                "UMAP1": [5.0, 5.1, -0.1, -5.0, -5.1],
                "UMAP2": [12.1, 12.1, 10.1, 10.1, 0.0],
            }
        )
        np.testing.assert_array_equal(assign_manual_labels(coordinates), [-1, 0, 1, 1, 1])

    def test_biological_label_mapping(self) -> None:
        self.assertEqual(assign_biological_labels(np.array([-1, 0, 1])), [-1, "classical", "basal"])

    def test_noise_predictions_propagate_single_class_without_a_model(self) -> None:
        expression = pd.DataFrame(
            {"GAL4": [0.1, 0.2, 0.3], "GATA6": [0.4, 0.5, 0.6], "TSPAN8": [0.7, 0.8, 0.9]}
        )
        labels, probabilities, model, encoder = predict_noise_xgboost(
            expression, pd.Series([1, -1, -1]), features=["GAL4", "GATA6", "TSPAN8"]
        )
        np.testing.assert_array_equal(labels, [1, 1, 1])
        self.assertIsNone(probabilities)
        self.assertIsNone(model)
        self.assertIsNone(encoder)

    def test_noise_predictions_return_model_probabilities(self) -> None:
        expression = pd.DataFrame(
            {
                "GAL4": [0.0, 0.1, 0.9, 1.0, 0.05, 0.95],
                "GATA6": [0.1, 0.0, 0.9, 1.0, 0.0, 1.0],
                "TSPAN8": [0.0, 0.1, 1.0, 0.9, 0.05, 0.95],
            }
        )
        labels = pd.Series([0, 0, 1, 1, -1, -1])

        predicted, probabilities, model, encoder = predict_noise_xgboost(
            expression,
            labels,
            n_estimators=10,
            max_depth=2,
            features=["GAL4", "GATA6", "TSPAN8"],
        )

        if probabilities is None or model is None or encoder is None:
            raise AssertionError("XGBoost should return probabilities for every input row")
        self.assertEqual(probabilities.shape, (len(expression), 2))
        np.testing.assert_allclose(probabilities.sum(axis=1), np.ones(len(expression)))
        np.testing.assert_array_equal(predicted, model.classes_[probabilities.argmax(axis=1)])

    def test_xgboost_trains_on_manual_rows_and_predicts_all_rows(self) -> None:
        expression = pd.DataFrame(
            {
                "GAL4": [0.1, 0.2, 0.3, 0.4],
                "GATA6": [0.5, 0.6, 0.7, 0.8],
                "TSPAN8": [0.9, 1.0, 1.1, 1.2],
            },
            index=pd.Index([10, 20, 30, 40]),
        )
        manual_labels = pd.Series([0, -1, 1, -1])
        expected_probabilities = np.array(
            [[0.9, 0.1], [0.7, 0.3], [0.2, 0.8], [0.1, 0.9]], dtype=np.float32
        )
        model = object()

        encoder = LabelEncoder().fit([0, 1])
        expected_labels = np.array([0, 0, 1, 1])
        with (
            patch(
                "app.annotation.labeling.fit_xgboost_classifier",
                return_value=(model, encoder),
            ) as fit,
            patch(
                "app.annotation.labeling.predict_xgboost_classifier",
                return_value=(expected_labels, expected_probabilities),
            ) as predict,
        ):
            predicted, probabilities, actual_model, actual_encoder = predict_noise_xgboost(
                expression, manual_labels, features=["GAL4", "GATA6", "TSPAN8"]
            )

        np.testing.assert_allclose(
            fit.call_args.args[0], expression.iloc[[0, 2]].to_numpy(dtype=np.float32)
        )
        np.testing.assert_array_equal(fit.call_args.args[1], [0, 1])
        self.assertEqual(fit.call_args.kwargs["n_estimators"], 100)
        self.assertEqual(fit.call_args.kwargs["max_depth"], 3)
        self.assertEqual(fit.call_args.kwargs["learning_rate"], 0.1)
        self.assertIs(predict.call_args.args[0], model)
        pd.testing.assert_frame_equal(predict.call_args.args[1], expression)
        self.assertEqual(predict.call_args.args[2], ["GAL4", "GATA6", "TSPAN8"])
        self.assertIs(predict.call_args.args[3], encoder)
        if probabilities is None:
            self.fail("XGBoost should return probabilities for every input row")
        np.testing.assert_array_equal(probabilities, expected_probabilities)
        np.testing.assert_array_equal(predicted, [0, 0, 1, 1])
        self.assertIs(actual_model, model)
        self.assertIs(actual_encoder, encoder)

    def test_noise_predictions_reject_empty_training_labels(self) -> None:
        expression = pd.DataFrame(
            {"GAL4": [0.1, 0.2, 0.3], "GATA6": [0.4, 0.5, 0.6], "TSPAN8": [0.7, 0.8, 0.9]}
        )
        with self.assertRaisesRegex(ValueError, "No manually labeled cells"):
            predict_noise_xgboost(
                expression,
                pd.Series([-1, -1, -1]),
                features=["GAL4", "GATA6", "TSPAN8"],
            )

    def test_save_rejects_misaligned_cell_ids(self) -> None:
        expression = pd.DataFrame(
            {"cell_id": ["a", "b"], "cell_uid": ["source:0", "source:1"], "GAL4": [0.1, 0.2]}
        )
        coordinates = pd.DataFrame(
            {"cell_id": ["b", "a"], "cell_uid": ["source:1", "source:0"], "UMAP1": [0.0, 1.0]}
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "cell_id values/order"):
                save_labeled_data(
                    expression, coordinates, np.array([0, 1]), Path(directory) / "out.csv"
                )

    def test_save_keeps_expression_order_and_maps_labels(self) -> None:
        expression = pd.DataFrame(
            {"cell_id": ["a", "b"], "cell_uid": ["source:0", "source:1"], "GAL4": [0.1, 0.2]}
        )
        coordinates = pd.DataFrame(
            {"cell_id": ["a", "b"], "cell_uid": ["source:0", "source:1"], "UMAP1": [0.0, 1.0]}
        )
        with tempfile.TemporaryDirectory() as directory:
            output_file = Path(directory) / "out.csv"
            result = save_labeled_data(expression, coordinates, np.array([0, 1]), output_file)
            saved = pd.read_csv(output_file)
        self.assertEqual(result["cell_id"].tolist(), ["a", "b"])
        self.assertEqual(result["cell_uid"].tolist(), ["source:0", "source:1"])
        self.assertEqual(result["labels"].tolist(), ["classical", "basal"])
        self.assertEqual(saved["cell_uid"].tolist(), ["source:0", "source:1"])

    def test_save_rejects_misaligned_cell_uids(self) -> None:
        expression = pd.DataFrame({"cell_id": ["a", "b"], "cell_uid": ["source:0", "source:1"]})
        coordinates = pd.DataFrame({"cell_id": ["a", "b"], "cell_uid": ["source:1", "source:0"]})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "cell_uid values/order"):
                save_labeled_data(
                    expression, coordinates, np.array([0, 1]), Path(directory) / "out.csv"
                )


class EmbeddingAndClusteringTests(unittest.TestCase):
    def test_marker_selection_preserves_requested_order(self) -> None:
        data = pd.DataFrame({"B": [1, 2], "A": [None, None]})
        self.assertEqual(get_umap_markers(data, ["A", "missing", "B"]), (["B"], ["A", "missing"]))

    def test_marker_selection_excludes_numeric_annotation_metadata(self) -> None:
        data = pd.DataFrame({"CD109": [1, 2], "leiden_cluster": [0, 1]})
        self.assertEqual(
            get_umap_markers(data, ["leiden_cluster", "CD109"]),
            (["CD109"], ["leiden_cluster"]),
        )

    def test_calculate_umap_saves_parquet_and_skips_missing_markers(self) -> None:
        data = pd.DataFrame(
            {
                "cell_id": ["a", "b", "c"],
                "condition": ["untreated", "treated", "untreated"],
                "CD109": [0.1, 0.2, 0.3],
            }
        )
        embedding = np.array([[0.0, 0.1], [1.0, 1.1], [2.0, 2.1]])
        with tempfile.TemporaryDirectory() as directory:
            cache_file = Path(directory) / "umap.parquet"
            with patch("app.annotation.embedding.umap.UMAP") as umap_model:
                umap_model.return_value.fit_transform.return_value = embedding
                actual = calculate_umap(data, ["missing", "CD109"], cache_file)
            saved = pd.read_parquet(cache_file)
        np.testing.assert_allclose(actual[["UMAP1", "UMAP2"]], embedding)
        pd.testing.assert_frame_equal(actual, saved)
        umap_model.return_value.fit_transform.assert_called_once()

    def test_calculate_umap_reuses_existing_parquet(self) -> None:
        data = pd.DataFrame(
            {
                "cell_id": ["a", "b"],
                "condition": ["untreated", "treated"],
                "CD109": [0.1, 0.2],
                "UMAP1": [4.0, 5.0],
                "UMAP2": [6.0, 7.0],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            cache_file = Path(directory) / "umap.parquet"
            data.to_parquet(cache_file, index=False)
            with patch("app.annotation.embedding.umap.UMAP") as umap_model:
                actual = calculate_umap(
                    data.drop(columns=["UMAP1", "UMAP2"]), ["CD109"], cache_file
                )
        pd.testing.assert_frame_equal(actual, data)
        umap_model.assert_not_called()

    def test_calculate_umap_rejects_cached_cell_order_mismatch(self) -> None:
        data = pd.DataFrame(
            {
                "cell_id": ["a", "b"],
                "CD109": [0.1, 0.2],
                "UMAP1": [4.0, 5.0],
                "UMAP2": [6.0, 7.0],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            cache_file = Path(directory) / "umap.parquet"
            data.iloc[::-1].to_parquet(cache_file, index=False)
            with self.assertRaisesRegex(ValueError, "cell_id values/order"):
                calculate_umap(data.drop(columns=["UMAP1", "UMAP2"]), ["CD109"], cache_file)

    def test_leiden_rejects_neighbor_count_outside_graph_bounds(self) -> None:
        data = pd.DataFrame({"UMAP1": [0.0, 1.0], "UMAP2": [0.0, 1.0]})
        with self.assertRaisesRegex(ValueError, "n_neighbors"):
            calc_leiden(data, n_neighbors=2)

    def test_leiden_returns_one_integer_label_per_coordinate(self) -> None:
        data = pd.DataFrame(
            {
                "UMAP1": [0.0, 0.1, 0.2, 5.0, 5.1, 5.2],
                "UMAP2": [0.0, 0.2, -0.1, 5.0, 5.2, 4.9],
            }
        )
        labels = calc_leiden(data, n_neighbors=2, resolution=0.5, random_state=42)
        self.assertEqual(labels.shape, (len(data),))
        self.assertTrue(np.issubdtype(labels.dtype, np.integer))

    def test_embedding_and_cluster_plots_are_shown(self) -> None:
        data = pd.DataFrame(
            {
                "UMAP1": [0.0, 1.0, 0.5],
                "UMAP2": [0.0, 0.0, 1.0],
                "condition": ["untreated", "treated", "untreated"],
            }
        )
        with tempfile.TemporaryDirectory() as directory, patch("matplotlib.pyplot.show") as show:
            root = Path(directory)
            plot_full_umap(data, root / "full.png")
            plot_condition_umap(data, root / "conditions.png")
            plot_clusters(data, pd.Series([0, 1, 0]), "clusters", root / "clusters.png")
            plot_clusters_by_condition(
                data,
                np.array([0, 1, 0]),
                ["untreated", "treated"],
                root / "condition_clusters.png",
            )
            self.assertTrue((root / "condition_clusters.png").is_file())
        self.assertEqual(show.call_count, 4)

    def test_cluster_heatmap_returns_cluster_means_and_saves_figure(self) -> None:
        data = pd.DataFrame(
            {
                "M1": [1.0, 2.0, 5.0, 6.0],
                "M2": [2.0, 3.0, 7.0, 8.0],
            }
        )
        with tempfile.TemporaryDirectory() as directory, patch("matplotlib.pyplot.show"):
            output = Path(directory) / "heatmap.png"
            _, means = plot_cluster_heatmap(data, np.array([0, 0, 1, 1]), ["M1", "M2"], output)
            self.assertTrue(output.is_file())
        self.assertEqual(means.index.tolist(), ["Cluster 0", "Cluster 1"])
        np.testing.assert_allclose(means.loc["Cluster 0"], [1.5, 2.5])

    def test_staining_plot_is_shown(self) -> None:
        data = pd.DataFrame(
            {
                "UMAP1": [0.0, 1.0],
                "UMAP2": [0.0, 1.0],
                "condition": ["untreated", "treated"],
                "marker": [0.2, 0.8],
            }
        )
        with tempfile.TemporaryDirectory() as directory, patch("matplotlib.pyplot.show") as show:
            plots = plot_umap_staining(
                data, Path(directory), marker_group="cell_identity", markers=["marker"]
            )
        self.assertEqual(len(plots), 1)
        show.assert_called_once_with()

    def test_probability_umap_saves_class_panels_for_all_rows(self) -> None:
        data = pd.DataFrame(
            {
                "UMAP1": [0.0, 1.0, 2.0],
                "UMAP2": [0.0, 1.0, 2.0],
                "condition": ["untreated", "treated", "untreated"],
            }
        )
        with tempfile.TemporaryDirectory() as directory, patch("matplotlib.pyplot.show") as show:
            output = Path(directory) / "probabilities.png"
            plot_umap_class_probabilities(
                data,
                np.array([[0.8, 0.2], [0.2, 0.8], [0.7, 0.3]]),
                np.array([0, 1]),
                output,
            )
            self.assertTrue(output.is_file())
        show.assert_called_once_with()

    def test_probability_umap_rejects_misaligned_rows(self) -> None:
        data = pd.DataFrame(
            {
                "UMAP1": [0.0, 1.0],
                "UMAP2": [0.0, 1.0],
                "condition": ["untreated", "treated"],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Probability rows"):
                plot_umap_class_probabilities(
                    data,
                    np.array([[0.5, 0.5]]),
                    np.array([0, 1]),
                    Path(directory) / "probabilities.png",
                )


if __name__ == "__main__":
    unittest.main()
