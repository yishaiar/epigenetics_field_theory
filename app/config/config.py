"""Shared marker selections and experiment-specific analysis parameters."""

# Exclude metadata from marker operations; measured marker columns are not listed here.
# fmt: off
METADATA_COLUMNS = [
    "experiment",  # Experiment or batch used to group and compare cells.
    "sample_name",  # Sample or mouse identifier used for per-mouse analyses.
    "condition",  # Treatment condition, such as treated or untreated.
    "labels",  # Biological subtype annotation used in downstream comparisons.
    "cell_uid",  # Stable cell identifier used to join annotations to cells.
    "cell_id",  # Legacy cell identifier retained by source CSVs.
    "leiden_cluster",  # Leiden cluster assignment exported with annotations.
    "annotation_present",  # Flag indicating whether a cell has annotation data.

    "path",  # Full input CSV path used to trace each cell to its source file.
    "raw_row_id",  # Original source-row index used to construct cell_uid.
]
# fmt: on

# Experiment folders processed by the staged notebooks.
EXPERIMENTS = ["batch2", "batch3", "batch4_extra_treatment"]

# Marker controls used to calculate each sample's normalization factor.
CONTROL_MARKERS = ["H3.3", "H4"]

# CD45 ArcSinh cutoffs used to select cells in each experiment.
CD45_CUTOFFS_ASINH = {
    "batch2": 2.0,
    "batch3": 2.0,
    "batch4_extra_treatment": 2.0,
}

# GFP ArcSinh cutoffs used to split cells in each experiment.
GFP_CUTOFFS_ASINH = {"batch2": 2.0, "batch3": 4.0, "batch4_extra_treatment": 3.0}

# Features used to fit Notebook 3's cell identity UMAP.
CELL_IDENTITY_MARKERS = (
    "CD109",
    "CD133",
    "CD24",
    "CD44",
    "CXCR4",
    "E-cadherin",
    "EpCAM",
    "GAL4",
    "GATA6",
    "KI67",
    "KRT17",
    "KRT5",
    "MHC-II",
    "S100A4",
    "SLC44A4",
    "TSPAN8",
    "Vimentin",
    "pRb",
)


# Markers used for Notebook 3 heatmaps and Notebook 4 basal/classical comparisons.
BASAL_CLASSICAL_SEPARATING_MARKERS = (
    "TSPAN8",
    "GATA6",
    "GAL4",
    "KRT5",
    "KRT17",
    "CD44",
    "CD109",
    "Vimentin",
    "EpCAM",
    "CD24",
    "E-cadherin",
    "KI67",
    "pRb",
    "CD109",
)
