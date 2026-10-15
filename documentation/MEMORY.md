# Project Memory

## Package and contracts

- `scbatch` is the sole published distribution; `pp`, `pl`, `datasets`, and
  `tl` are internal UV workspace members.
- Public computation uses `AnnData` and Scanpy-style namespaces. Preserve sparse
  matrices and axis alignment; store provenance in `uns`, intermediate matrices
  in layers, and derived data in standard AnnData slots. Public schemas use
  Pydantic v2.
- Tests belong beside their component in `scbatch/<module>/tests/`.

## Implemented behavior and limits

- `run_pipeline` mutates one `AnnData`: gating, ArcSinh, batch correction, core
  normalization, global Scanpy scaling, neighbors, UMAP, then Leiden or DBSCAN.
  It snapshots matrix stages in layers; Scanpy stores graphs and embeddings in
  standard slots.
- Gating, ArcSinh, and core normalization operate by original
  `(batch_index, sample_index)`. Gating subsets aligned AnnData contents, using
  cutoff `0.01` and per-sample upper quantile `0.9999`. ArcSinh requires dense
  NumPy `X` and uses cofactor `5`. Core normalization currently adds one.
- `batch_correct` dispatches registered choices: `boundary_extrapolated_qq`,
  `qq`, `cytonorm`, `cycombine`, `mmd_resnet`, `harmony`, and `fastmnn`. Only
  `qq` currently changes `X` (adds one); the others are scaffolds. Predictor
  fit and transform are unimplemented. Registration does not imply an algorithm.
- `create_adata_from_dataset` combines same-marker-count sample matrices and
  records batch, sample, and anchor metadata in `obs`. It does not currently
  populate `uns["anchor_pairs"]`. `summarize_samples` reports sample sizes;
  `get_sample_data_mask` selects rows by batch and sample indexes.
- `load_demo` offers synthetic and CYTOF names; verify their fixture contents
  before claiming they differ. Plotting APIs and `tl.dbscan` are scaffolds.
- Research documents describe planned methods, not implementation status; check
  public code and tests before claiming a method is complete.
