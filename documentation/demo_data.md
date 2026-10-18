# Lightweight CyTOF demo data

The demo fixture samples 100 cells from each of the 17 raw sample files in
`batch2`, `batch3`, and `batch4_extra_treatment`, for 1,700 cells total. It
preserves the original columns and cell metadata and uses seed 42 by default.
The selected measurements come from the local raw data, so the generated fixture
stays local and is ignored by Git.

Generate or refresh it from the repository root:

```bash
uv run python -m app.preprocessing.demo_data
```

This writes sampled CSVs under `demo_data/raw_data/` and a manifest at
`demo_data/demo_dataset_manifest.csv`. It does not modify `raw_data/`.

To run the notebooks against the fixture, set `DEMO_MODE=true` in
`app/dotenv/.env`, then restart the notebook kernels and run notebooks 00
through 04 in order. Demo outputs go to `results/demo/experiment_<ddmmyy>/`.
Leave `DEMO_MODE=false` for the normal full-data run, whose output location
remains `results/experiment_<ddmmyy>/`.

The demo is intended for workflow smoke runs and development, not scientific
analysis. Change the cap or seed with `--cells-per-sample` or `--random-state`
when invoking the generator.
