nice — I parsed the uploaded `plotly.go.Figure` API and built you a compact manifest of every method: name, rough category, param list (names), return annotation, first docstring line, and inferred trace type for the `add_*` helpers. I dropped it into an interactive table (above) and also exported files you can pipeline:

* [Download CSV](sandbox:/mnt/data/plotly_figure_api_manifest.csv)
* [Download JSON](sandbox:/mnt/data/plotly_figure_api_manifest.json)

Key takeaways (useful for templating & deterministic generation):

* Scope of API in this file: **110 methods** total.

  * **Trace adders:** **53** `add_*` methods, each mapping 1:1 to a Plotly trace class (e.g., `add_bar`→`Bar`, `add_contour`→`Contour`, …). Common routing params across adders: `row`, `col`, and `secondary_y` for subplot addressing.
  * **Shape helpers:** **4** (`add_hline`, `add_vline`, `add_hrect`, `add_vrect`) that proxy to `add_shape` with syntactic sugar.
  * **Mutators / selection ops:** **4** (`update`, `update_layout`, `update_traces`, `for_each_trace`). These are your deterministic post-patch primitives (recursive, optional `overwrite`).
  * **Subplot builder:** **1** (`set_subplots`) thin wrapper around `make_subplots`.
  * **Constructor:** **1** (`__init__(data=None, layout=None, frames=None, skip_invalid=False, **kwargs)`), takes sequences of traces / frames or dicts.&#x20;

### How I’d structure a deterministic templating API (split traces vs. layout)

**1) Trace spec (pure data → trace instances):**

* One canonical list of trace specs, each with a required `type` (lowercase Plotly type) and **only** explicit attributes; disallow incidental defaults to keep runs deterministic.
* Include routing keys for subplot placement:

  ```json
  {
    "type": "bar",
    "args": {"x": [..], "y": [..], "name": "sales"},
    "row": 1, "col": 2, "secondary_y": false
  }
  ```

**2) Figure topology & layout spec (compositional, order-stable):**

* Subplots (if any): `{ "rows": 2, "cols": 2, "specs": [...] }` → call `set_subplots` first.
* Shapes/lines/rects (helpers): an ordered list of `{op: "add_hline", "y": 0, "annotation": {...}, "kwargs": {...}}`.
* Layout patches (post): a final deterministic patch set:

  ```json
  [
    {"op": "update_layout", "patch": {"xaxis": {"title": "X"}}},
    {"op": "update_traces", "selector": {"type": "bar"}, "patch": {"opacity": 0.8}}
  ]
  ```

**3) Determinism guardrails**

* Fix the **operation order**: `set_subplots` → `add_traces` (in given order) → shape helpers → `update_traces` → `update_layout`.
* For selections, prefer **explicit selectors** (e.g., `{"type":"bar","name":"sales"}`) over positional.
* Pin anything user-tweakable with `uirevision` where relevant.
* Never rely on implicit defaults; always pass the value you want in the template.
* Keep `skip_invalid=False` during materialization to fail fast.

### What’s next (fast wins)

* If you want, I can auto-generate:

  1. a **Pydantic** schema for `TraceSpec`, `LayoutSpec`, `FigureTemplate`, and
  2. a **materializer** that takes the JSON template → builds a `go.Figure` using only the deterministic ops above.

The table I rendered lets you filter by `category == "trace_adder"` to see every supported trace type and skim docstring first lines for your own naming/DSL choices. If you want a narrower manifest (e.g., only the signatures for `update_*` and shape helpers) or a JSON Schema, I can spin that out immediately from the extracted data.&#x20;
