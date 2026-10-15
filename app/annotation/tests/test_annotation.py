"""Focused parity checks for notebook-extracted annotation operations."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from app.annotation.clustering import (
    calc_leiden,
    plot_cluster_heatmap,
    plot_clusters,
    plot_clusters_by_condition,
)
from app.annotation.embedding import get_umap_markers, plot_condition_umap, plot_full_umap
from app.annotation.labeling import (
    assign_biological_labels,
    assign_manual_labels,
    predict_noise_xgboost,
    save_labeled_data,
)
from app.annotation.plotting import plot_umap_staining


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

    def test_noise_predictions_propagate_single_class_and_reject_empty_training_labels(
        self,
    ) -> None:
        expression = pd.DataFrame(
            {"GAL4": [0.1, 0.2, 0.3], "GATA6": [0.4, 0.5, 0.6], "TSPAN8": [0.7, 0.8, 0.9]}
        )
        labels, model = predict_noise_xgboost(expression, np.array([1, -1, -1]))
        np.testing.assert_array_equal(labels, [1, 1, 1])
        self.assertIsNone(model)
        with self.assertRaisesRegex(ValueError, "No manually labeled cells"):
            predict_noise_xgboost(expression, np.array([-1, -1, -1]))

    def test_save_rejects_misaligned_cell_ids(self) -> None:
        expression = pd.DataFrame({"cell_id": ["a", "b"], "GAL4": [0.1, 0.2]})
        coordinates = pd.DataFrame({"cell_id": ["b", "a"], "UMAP1": [0.0, 1.0]})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "cell_id values/order"):
                save_labeled_data(
                    expression, coordinates, np.array([0, 1]), Path(directory) / "out.csv"
                )

    def test_save_keeps_expression_order_and_maps_labels(self) -> None:
        expression = pd.DataFrame({"cell_id": ["a", "b"], "GAL4": [0.1, 0.2]})
        coordinates = pd.DataFrame({"cell_id": ["a", "b"], "UMAP1": [0.0, 1.0]})
        with tempfile.TemporaryDirectory() as directory:
            result = save_labeled_data(
                expression, coordinates, np.array([0, 1]), Path(directory) / "out.csv"
            )
        self.assertEqual(result["cell_id"].tolist(), ["a", "b"])
        self.assertEqual(result["labels"].tolist(), ["classical", "basal"])


class EmbeddingAndClusteringTests(unittest.TestCase):
    def test_marker_selection_preserves_requested_order(self) -> None:
        data = pd.DataFrame({"B": [1, 2], "A": [None, None]})
        self.assertEqual(get_umap_markers(data, ["A", "missing", "B"]), (["B"], ["A", "missing"]))

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
            plot_full_umap(data, "all", "markers", root / "full.png")
            plot_condition_umap(
                data,
                "all",
                "markers",
                {"all": ["untreated", "treated"]},
                root / "conditions.png",
            )
            plot_clusters(data, np.array([0, 1, 0]), "clusters", root / "clusters.png")
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
            plots = plot_umap_staining(data, ["marker"], "all", "surface", Path(directory))
        self.assertEqual(len(plots), 1)
        show.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
