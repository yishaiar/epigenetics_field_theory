# Staged pipeline architecture, for application repositories

This is the preserved generic architecture blueprint from the source repository. Use it only when scaffolding a repository that takes raw input through named stages to produce a result. `scbatch` itself is not an application repository and must use the scientific-package architecture below.

## Shape

```text
<app>/
├── pipeline.py       # Level 1 orchestrator
├── config.py         # fields, thresholds, registry names, shared settings
├── <stage_a>.py      # Level 2 stage
├── <stage_b>.py      # Level 2 stage
└── <stage_b>/        # optional Level 3 decomposition
    ├── concern_1.py
    └── concern_2.py
```

Every application needs Level 1 and Level 2. Level 3 is optional and is added only where it earns its keep.

## Level 1, the orchestrator (`pipeline.py`)

This is the single caller-facing entry point for the whole application. It has two class roles:

- One base class holds setup shared by every use case, such as configuration or a database connection. It does not run stages itself.
- One subclass per distinct top-level use case. Each subclass has one entry-point method that constructs Level 2 stages in order and passes each stage output to the next.

The orchestrator owns sequencing only. Stage implementation detail does not belong here.

## Level 2, stage classes

Split work into self-contained named steps that fit the domain. Each stage:

- is a class in its own file;
- takes the shared `Config` object in its constructor;
- exposes one method invoked by the orchestrator; and
- knows nothing about adjacent stages, receiving input and returning output.

A stage can handle variants internally. Choose the appropriate Level 3 pattern per variant.

## Level 3, optional internal variation

Do not subclass a stage for every variant. Use one or mix these patterns:

1. **Dispatch dictionary of plain methods**. Default to a mapping from variant name to a short method on the stage.
2. **Dispatch dictionary delegating to composed helpers**. When a variant grows substantial internal state or several helpers, put it in its own class and map that variant to the helper method. Use composition, not stage inheritance.
3. **Declarative entries plus one generic runner**. When variants use the same logic with different parameters, define small configuration records and loop over them in one runner. Adding a variant then means adding an entry, not a method or class.

## `config.py`

One `Config` class or module holds field mappings, thresholds, and registry names that every stage reads. A new field, model, or threshold starts there, then is wired into the stages that need it.

## Scaffolding checklist

1. Write `config.py` first, even if it initially holds an almost-empty `Config` class.
2. Write `pipeline.py` with the base orchestrator and one subclass per top-level use case. Keep it free of stage logic.
3. Add one stage class per step, each taking `Config` in its constructor.
4. Start with a dispatch dictionary of plain methods. Split into composed helpers or switch to declarative entries only when real complexity requires it.
5. A new signal, field, or model should require a `config.py` entry and, if needed, a method or dispatch entry in its owning stage. It should not require a `pipeline.py` change.

# Scientific package architecture, for `scbatch`

`scbatch` is one Scanpy-style package, not a collection of services. Its UV workspace members are ownership boundaries for scientific code.

```text
AnnData input
    |
    +-- scbatch.datasets  reproducible inputs and fixtures
    +-- scbatch.pp        validation, transformations, correction
    +-- scbatch.tl        graph, embedding, clustering, downstream analysis
    +-- scbatch.pl        diagnostics and publication-ready plots
```

## Boundaries

- `pp` may write documented corrected or intermediate layers and method provenance to `adata.uns`.
- `tl` consumes documented representations and writes graphs or embeddings to standard AnnData slots.
- `pl` reads results without mutating the input unless its public API states otherwise.
- `datasets` supplies deterministic, documented test and example inputs.

## Public interfaces

Use `AnnData` for data-bearing APIs and Pydantic v2 for public request, configuration, and result schemas. Validate metadata keys, shapes, and axis alignment before mutation. Preserve sparse representations when supported.

## Development sequence

1. Define the public schema and AnnData mutation contract.
2. Implement the owning workspace member without cross-module leakage.
3. Add tests beside that member for normal, invalid, empty, sparse, and dense inputs as applicable.
4. Export only stable public functions through the corresponding namespace.
