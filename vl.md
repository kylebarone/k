Got it — here’s a compact, “teach-then-steer” guide the agent can follow to read CSVs, inspect with pandas, transform, and emit **base Altair (Vega-Lite) JSON**—no extra installs.

# Overview: what “declarative” means (for the agent)

* **Altair** is a Python API that **compiles to Vega-Lite JSON**. The JSON is the artifact you pass to the frontend. Use `.to_json()` to get a string or `.save('*.json')` to write a spec file. ([altair-viz.github.io][1])
* Your loop is always: **Plan → Read CSV (pandas) → Inspect (Jupyter-style) → Transform (pandas) → Declare chart (Altair) → Save JSON spec**. ([altair-viz.github.io][1])
* **Vega-Lite basics** you’ll speak in JSON through Altair: *mark*, *encoding*, and optional *transform* (run in the browser). Supported data types are `quantitative`, `temporal`, `nominal`, `ordinal`, and `geojson`. ([Vega][2])

# Canonical agent workflow (repeat every request)

1. **Planning text (natural language → intent)**

   * Identify measures, dimensions, filters, time grains, comparisons, interactivity (brush, drill), and output granularity (aggregate vs detail).

2. **Code block 1 — Read + Inspect (pandas, Jupyter style)**

   * `pd.read_csv(...)`
   * Show quick profile: `df.shape`, `df.dtypes`, `df.head()`, `df.isna().sum()`, unique counts for keys, and sample of categorical values.
   * If dates/currency: parse (`pd.to_datetime`), normalize currency/units, and confirm sortedness.

3. **Code block 2 — Transform (pandas)**

   * Do **row-reducing** work here: filtering, grouping, resampling (weekly/monthly), joins, window calcs, top-N, bucketing.
   * Keep the result **≤ 5k rows** when possible; otherwise consider **explicit pre-aggregation** or (as a last resort) `alt.data_transformers.disable_max_rows()` which lifts the limit but may degrade browser perf. ([altair-viz.github.io][3])

4. **Code block 3 — Altair spec**

   * Build the chart declaratively: choose a **mark** (bar/line/point/area/rect/text/boxplot), set **encodings** (`x`, `y`, `color`, `row/column` for facet), add **tooltips**, and (optionally) **params/selections** for interactivity.
   * Prefer explicit channel types: `field:Q/T/N/O` to avoid inference mistakes. ([Vega][2])
   * Save the JSON: `chart.save('foo.json')` (you can adopt a `.vl.json` naming convention, but `.json` is sufficient). ([altair-viz.github.io][1])

---

# What the agent should do on each step (with examples)

## 1) Planning prompts the agent can emit

* “Grain: week? month? Compare YoY?”
* “Measures: `net_sales`, `units`, `gm%`? Filters: channel/region?”
* “Chart family: trend, ranked bar, heatmap, distribution, boxplot, breakdown dashboard?”
* “Interactivity: time brush, category click-to-filter, hover tooltips?”

## 2) Read + Inspect (always show output)

Typical code block (example — not scaffolding):

```python
import pandas as pd
df = pd.read_csv("sales.csv")
display(df.head(5))
display(df.dtypes)
print("rows, cols:", df.shape)
display(df.isna().sum())
display(df[['order_date','region','category']].nunique())
```

Agent checks: parse dates, standardize price columns, confirm unique keys (e.g., order_id).

## 3) Transform (pandas first)

Keep the JSON light; do heavy lifting here. Examples the agent should reach for:

* **Time grain**: `df.assign(order_date=pd.to_datetime(df.order_date)).groupby(pd.Grouper(key='order_date', freq='W'))['net_sales'].sum().reset_index()`
* **Top-N**: rank by period total then filter; keep “Other” bucket if requested.
* **Window metrics**: rolling 7-day avg; period-over-period deltas.
* **Basket/bucket**: bin prices or quantities; create flags for promo/stock-out.

> Why pandas first? Vega-Lite supports transforms (`aggregate`, `bin`, `timeUnit`, `filter`, `window`, `joinaggregate`, `lookup`, etc.), but they run client-side. Use them for **small/medium** data or light tweaks; keep big reductions in pandas. ([Vega][4])

## 4) Declare the visualization (Altair → Vega-Lite)

Core building blocks the agent should use:

### Marks & Encodings

* Choose a **mark**: `mark_bar`, `mark_line`, `mark_point`, `mark_area`, `mark_rect` (heatmaps), `mark_text`, and composite marks like **`mark_boxplot`**. ([Vega][5])
* Encodings: map fields to `x`, `y`, `color`, `size`, `opacity`, `tooltip`, `row/column` (facets). Prefer `:Q/:T/:N/:O` type suffixes. ([Vega][2])
* Aggregates in encodings (e.g., `y='sum(net_sales):Q'`) for clean specs. ([Vega][6])

### Transforms (lightweight, optional)

* `.transform_filter(...)`, `.transform_calculate(...)`, `.transform_bin(...)`, `.transform_timeunit(...)`, `.transform_window(...)`, `.transform_joinaggregate(...)`, `.transform_lookup(...)`. Keep them simple if you already aggregated in pandas. ([Vega][4])

### Composition

* **Layer** multiple marks; **facet** by a categorical field; **hconcat/vconcat** for dashboards. Use `.properties(width=..., height=..., title=...)` for polish.

### Interactivity (no plugins)

* Use **selection parameters**: `alt.selection_interval()` for brushing ranges; `alt.selection_point()` for category toggles. Filter with `.transform_filter(sel)` or condition encodings with `alt.condition(sel, ...)`. ([altair-viz.github.io][7])

### Saving the spec

* `chart.save("name.json")` writes a **Vega-Lite JSON** file you can feed to the frontend (e.g., via vega-embed). `.to_json()` returns the JSON string if you need to post-process. ([altair-viz.github.io][1])

---

# Retail analyst intents → what the agent should produce

**“Show weekly revenue by category, with 7-day rolling avg, highlight Black Friday.”**

* **Inspect**: confirm date, revenue types; check nulls.
* **Transform**: parse dates, group weekly by category, compute rolling mean, flag `black_friday`.
* **Altair**: layered **line + point**; color by category; vertical `rule` at event; tooltip on hover; optional **x-brush** to zoom.

**“Rank top 20 SKUs by returns rate last quarter.”**

* Transform: filter date, compute `returns / units_sold`, pick top-20.
* Altair: **bar** sorted desc (`sort='-x'`), color by category, tooltip (SKU, rate, units).

**“Heatmap of stockouts by store × week.”**

* Transform: weekly store counts of stockouts.
* Altair: `mark_rect()` with `x='week:T'`, `y='store:N'`, `color='sum(stockouts):Q'`, grid axes; optional **layered text** with counts. ([Vega][8])

**“Compare YoY net sales with a hoverable detail.”**

* Transform: align weeks across years; compute YoY delta if requested.
* Altair: multi-line **trend** colored by year; **point selection** to show a detail table or annotate the hovered week.

**“Distribution of basket sizes by channel.”**

* Transform: compute `items_per_basket`;
* Altair: **boxplot** by channel (or binned histogram + density by channel). ([Vega][9])

> Note: **Treemap** is a *Vega* (not Vega-Lite) pattern; in **base Altair/Vega-Lite** you’ll use alternatives like ranked bars or heatmaps for hierarchical-ish views. ([GitHub][10])

---

# Guardrails & decision rules the agent should follow

**A. Data volume**

* If final dataset **> 5,000 rows**, prefer pandas pre-aggregation, sampling, or limiting rows. As a last resort (only if required), call `alt.data_transformers.disable_max_rows()` and warn in the plan that the browser may struggle. ([altair-viz.github.io][3])
* Avoid the `json/csv` data transformers unless your environment guarantees file access/serving; they write temp files and can break portability. Use only if explicitly requested. ([altair-viz.github.io][11])

**B. Types & scales**

* Always tag types (`:Q/:T/:N/:O`). For temporal, choose `timeUnit` carefully (week, month, yearquarter). ([Vega][2])
* Set axes/titles explicitly; use `scale=alt.Scale(zero=False)` when a zero baseline is misleading.

**C. Interactivity**

* Prefer `selection_interval()` for zoom/brush on time; `selection_point()` for category toggles; wire conditions or filters accordingly. ([altair-viz.github.io][7])

**D. JSON emission**

* Emit a single **Vega-Lite JSON** per view or dashboard (use concat/layer/facet if you need multiple coordinated views). Save via `chart.save('*.json')`; return the path or the JSON string to the caller. ([altair-viz.github.io][1])

**E. When to use Vega-Lite transforms**

* OK for: simple `filter`, `calculate` flags, final binning, tooltip-friendly aggregates, window ranks for small datasets.
* Prefer pandas for: major joins, heavy window calcs over large tables, expensive reshaping. ([Vega][4])

---

# Minimal code patterns the agent can emit (per step)

**Inspect**

```python
import pandas as pd
df = pd.read_csv(".../retail.csv")
df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
display(df.head(10)); display(df.dtypes); print(df.shape); display(df.isna().sum())
```

**Transform**

```python
weekly = (df
  .query("channel in ['Online','Store']")
  .assign(week=lambda d: d['order_date'].dt.to_period('W').dt.start_time)
  .groupby(['week','category'], as_index=False)['net_sales'].sum())
```

**Altair → JSON**

```python
import altair as alt
chart = (alt.Chart(weekly)
  .mark_line(point=True)
  .encode(
      x='week:T', y='net_sales:Q', color='category:N',
      tooltip=['week:T','category:N','net_sales:Q']
  )
  .properties(width=720, height=360, title='Weekly Net Sales by Category'))
chart.save("weekly_sales.json")  # hand off to frontend
```

(Uses only base Altair and Vega-Lite features; JSON is ready for vega-embed or equivalent. ([altair-viz.github.io][1]))

---

# Quick reference (for the agent’s “mental autocomplete”)

* **Marks**: bar, line, point, area, rect (heatmap), rule, text, boxplot. ([Vega][5])
* **Types**: `:Q` numbers, `:T` datetimes, `:N` categories, `:O` ordered categories, `:G` geojson. ([Vega][2])
* **Common transforms**: `filter`, `calculate`, `aggregate`, `bin`, `timeUnit`, `window`, `joinaggregate`, `lookup`. ([Vega][4])
* **Selections**: `selection_interval()` (ranges), `selection_point()` (discrete toggles). ([altair-viz.github.io][7])
* **Large data**: aim ≤ 5k rows; otherwise aggregate/sample in pandas or explicitly disable the limit (with caution). ([altair-viz.github.io][3])
* **Save**: `.save('*.json')` or `.to_json()` → frontend renders the spec. ([altair-viz.github.io][1])

---

If you want, I can tailor a **prompting template** the agent uses before every chart (slots for grain/measures/filters/interactivity/output), plus a few retail task recipes (stockout heatmap, promo-lift comparison, ABC analysis) that map straight to this 3-block pattern.

[1]: https://altair-viz.github.io/user_guide/saving_charts.html?utm_source=chatgpt.com "Saving Altair Charts — Vega-Altair 5.5.0 documentation"
[2]: https://vega.github.io/vega-lite/docs/type.html?utm_source=chatgpt.com "Type | Vega-Lite"
[3]: https://altair-viz.github.io/user_guide/large_datasets.html?utm_source=chatgpt.com "Large Datasets — Vega-Altair 5.5.0 documentation"
[4]: https://vega.github.io/vega-lite/docs/transform.html?utm_source=chatgpt.com "Transformation - Vega-Lite"
[5]: https://vega.github.io/vega-lite/docs/mark.html?utm_source=chatgpt.com "Mark | Vega-Lite"
[6]: https://vega.github.io/vega-lite/docs/aggregate.html?utm_source=chatgpt.com "Aggregation | Vega-Lite"
[7]: https://altair-viz.github.io/user_guide/generated/api/altair.selection_interval.html?utm_source=chatgpt.com "altair.selection_interval — Vega-Altair 5.5.0 documentation"
[8]: https://vega.github.io/vega-lite/docs/rect.html?utm_source=chatgpt.com "Rect | Vega-Lite"
[9]: https://vega.github.io/vega-lite/docs/boxplot.html?utm_source=chatgpt.com "Box Plot | Vega-Lite"
[10]: https://github.com/altair-viz/altair/issues/2457?utm_source=chatgpt.com "Treemap / Mosaic Chart Example · Issue #2457 · vega/altair"
[11]: https://altair-viz.github.io/user_guide/data_transformers.html?utm_source=chatgpt.com "Data Transformers — Vega-Altair 5.5.0 documentation"
