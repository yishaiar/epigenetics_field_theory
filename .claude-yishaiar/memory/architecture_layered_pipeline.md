# Stages (layers) Pipeline Architecture (use when scaffolding a new repo)

A reusable way to structure any app that takes raw input, processes it
through several stages, and produces a result (e.g. clean data → extract
signals → score/classify). Use this file as the blueprint when starting a
brand-new repo for that kind of app — even though the source repo this was
learned from calls its stages "data_loading" / "features_preprocess" / "inference",
your new app should use whatever stage names fit its own domain.

## The shape, in one picture

```
<app>/
├── pipeline.py       # the "orchestrator" — see Level 1 below
├── config.py         # one place holding every field name, threshold,
│                     # and model/registry name — every stage reads from
│                     # this, nothing is hardcoded stage-by-stage
├── <stage_a>.py       # Level 2 — one file per stage, see below
├── <stage_b>.py
└── <stage_b>/          # a stage CAN be split into its own folder — only
    ├── concern_1.py    # do this once that stage has enough internal
    └── concern_2.py    # complexity to justify separate files (Level 3)
```

There are three levels. Every new repo built this way needs Level 1 and
Level 2. Level 3 is optional — only add it where it earns its keep.

## Level 1 — the orchestrator (`pipeline.py`)

This is the single entry point a caller uses to run the whole app. It is
made of two kinds of class:

- **One base class** holding setup that every use case of this app shares —
  things like resolving a database connection, loading config, etc. It does
  not run any stages itself (start empty).
- **One subclass per distinct top-level use case** the app supports. If the
  app only ever does one thing, one subclass is enough. If it supports
  multiple distinct request shapes (e.g. "score a single record" vs "score
  a whole batch"), each gets its own subclass. Each subclass has one method
  that is the actual entry point — it constructs the Level 2 stage objects
  in order and calls them one after another, passing each stage's output as
  the next stage's input.

Nothing about *how* a stage does its job lives here — the orchestrator only
knows the sequence and passes data along.

## Level 2 — stage classes (one file/class per stage)

Split the app's work into stages, where each stage is a self-contained,
named step (e.g. "cleaning", "feature extraction", "scoring" — name them for
what your domain actually needs, don't force a fixed count or fixed names).
Each stage:

- is its own class, in its own file
- takes the shared `Config` object (see below) in its constructor
- exposes one method the orchestrator calls to run that stage
- knows nothing about the stages before or after it — it only receives
  input data and returns output data

A stage is usually not "one function that does everything" — it has to
handle many small variants of the same kind of work (e.g. a cleaning stage
must clean many different field types; a scoring stage must run several
different models on different subsets of the data). How to handle that
internal variation is Level 3.

## Level 3 (optional) — handling variation inside a stage

Do not default to subclassing the stage itself per variant. Pick whichever
of these three fits, per variant if needed — a single stage can legitimately
mix approaches:

1. **Dispatch dict of plain methods** — the default, simplest choice. In
   the stage's constructor, build a dict mapping each variant's name to one
   of the stage's own methods (e.g. `self.handlers = {"field_x":
   self.clean_field_x, "field_y": self.clean_field_y}`). Use this whenever
   each variant's logic is short — a few lines each.

2. **Dispatch dict delegating to composed helper classes** — once a
   variant's logic grows large enough to want its own file (many related
   methods, its own internal state/helpers), give it its own class in its
   own file, instantiate it in the stage's constructor, and point the same
   dispatch dict at *that instance's* method instead of the stage's own.
   The dict ends up mixing plain methods and delegated methods side by
   side — that's expected, not a sign of inconsistency. Do NOT make the
   stage class itself subclassed per variant; composition, not inheritance,
   is what varies here.

3. **List of declarative entries + one generic runner** — use this instead
   of a dispatch dict when the variants are not really different logic, just
   the same operation with different parameters (e.g. "run this model, on
   this subset of rows, write the score to this column" repeated for
   several models). Build a plain list of small config records (one per
   variant, e.g. a small dataclass with fields like `which_model`,
   `which_rows`, `output_column`), and write exactly one method that loops
   over the list and applies each entry the same way. Adding a new variant
   means appending one entry — no new method, no new class.

## `config.py`

One `Config` class (or module) that every stage reads from — field-name
mappings, thresholds, model/registry names. When adding anything new to the
app (a new field, a new model, a new threshold), it starts here, then gets
wired into whichever stage(s) need it.

## Checklist for scaffolding a new repo with this pattern

1. Write `config.py` first — even a near-empty `Config` class is fine to
   start; stages will read from it.
2. Write `pipeline.py` with the base orchestrator class and one subclass
   per top-level use case — no stage logic yet, just the call sequence.
3. Write one stage class per step, each in its own file, each taking
   `Config` in its constructor.
4. Inside each stage, start with a plain dispatch dict (Level 3, option 1).
   Only split a variant into its own composed class, or switch a stage to
   the declarative-list style, once that stage's real complexity calls for
   it — don't pre-build all three patterns speculatively.
5. Adding a new signal/field/model later should only ever require: a
   `config.py` entry, plus (if needed) a new method or dispatch entry
   inside the relevant stage. It should never require changing
   `pipeline.py`.
