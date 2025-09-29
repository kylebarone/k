Awesome—let’s lock in a crisp “agent contract” you can drop straight into your repo. It’s tuned for an LLM that writes matplotlib + seaborn code, with zero hidden state and predictable outputs.

# Guiding Principles (TL;DR)

1. **Always OO API:** `fig, axes = plt.subplots(...)` for everything; pass `ax=` to seaborn Axes-level funcs.
2. **Figure-level seaborn only for faceting:** `relplot/catplot/pairplot/jointplot` → return `g.figure`.
3. **No implicit state:** never rely on current fig/axes; always `fig.savefig(...)` and `plt.close(fig)`.
4. **Deterministic & reproducible:** fixed seeds, explicit sizes, explicit fonts, explicit dpi.
5. **Robust to data shape:** inspect columns, types, NaNs; fail fast with clear errors.
6. **Layout-first:** `constrained_layout=True` (or `tight_layout()` fallback); avoid clipped labels.
7. **Accessible by default:** colorblind-safe palettes, adequate contrast, readable fonts.
8. **Artifacts over side-effects:** return handles + bytes (PNG/SVG) and a short JSON “spec” of what was drawn.
9. **Security & isolation:** never execute untrusted code; do not load remote URLs; no filesystem writes outside given sandbox path.
10. **Small, composable utilities > monoliths:** one responsibility per function.

---

# Agent Behavior Contract

## Inputs

* **Data**: pandas `DataFrame` (preferred) or arrays; schema provided or introspected at runtime.
* **Spec**: minimal plotting spec (type, encodings, aesthetics, layout) + theme overrides.
* **Env**: `{ "backend": "Agg", "seaborn_available": true|false }`.

## Outputs

* `fig`: matplotlib Figure handle (or `g.figure` for seaborn figure-level).
* `axes`: list/array of Axes (if applicable).
* `bytes`: exported image (`.png` by default, `.svg` on request).
* `meta`: JSON with keys `{ "plot_type", "encodings", "n_axes", "size", "dpi", "palette", "warnings": [] }`.

## Hard Requirements

* Use **`plt.subplots`** with `constrained_layout=True`.
* Use seaborn **Axes-level** (`sns.scatterplot`, `sns.lineplot`, `sns.histplot`, `sns.heatmap`, …) with `ax=...`.
* Use seaborn **figure-level** only for **faceting** (e.g., `relplot`, `catplot`, `pairplot`, `jointplot`).
* **Never** call stateful pyplot drawing functions (e.g., bare `plt.plot`, `plt.figure`, `plt.gca`) in agent-authored code.
* Save with `fig.savefig(path or BytesIO, dpi=..., bbox_inches="tight", facecolor="white")`, then `plt.close(fig)`.

---

# Plotting Decision Tree

1. **Need small multiples / coordinated legend / facet grids?**
   → Use seaborn **figure-level** (`relplot/catplot/...`). Return `g.figure`, customize via `g.set()`, `g.add_legend()`.

2. **Single or manual grid of axes?**
   → `fig, axes = plt.subplots(...)` + seaborn **Axes-level** on each `ax`.

3. **Heatmaps / images requiring shared colorbar across axes?**
   → Create with Axes-level, then `fig.colorbar(mappable, ax=axes, fraction=..., pad=...)`.

4. **Complex layout (insets, twin axes)?**
   → Still start from `subplots`; use `ax.inset_axes(...)`, `ax.twinx()` sparingly and document clearly.

---

# Style & Theming

* **Defaults**

  ```python
  import matplotlib.pyplot as plt, seaborn as sns
  sns.set_theme(context="notebook", style="ticks")  # once per entrypoint
  DEFAULT_SIZE = (6, 4)      # inches, single-axes
  DEFAULT_DPI  = 150
  DEFAULT_FONT = {"family": "DejaVu Sans"}  # cross-platform safe
  ```

* **Accessibility**

  * Prefer `palette="colorblind"` or explicit palettes (tab10 equivalents) that avoid red/green collisions.
  * Line widths ≥ 1.5, marker sizes ≥ 40 (scatter), font sizes ≥ 10pt for axis labels, 12–14pt for titles.

* **Layout**

  * `constrained_layout=True` on creation; if elements still overlap: `fig.tight_layout()` after artists are added.
  * Rotate crowded tick labels (`ax.tick_params(axis="x", rotation=30)`), use `MaxNLocator` for dense numeric axes.

---

# Legends, Colorbars, Labels

* **Legends**: prefer seaborn’s auto legend; otherwise `ax.legend(frameon=False, ncol=..., bbox_to_anchor=(1, 1))` for outside placement.
* **Colorbars**: always derive from the **returned mappable** (e.g., `im = ax.imshow(...); fig.colorbar(im, ax=ax)`); never from colormap alone.
* **Labels/Titles**: set all three explicitly: `ax.set_title(...)`, `ax.set_xlabel(...)`, `ax.set_ylabel(...)`.
* **Units**: if applicable, include units in labels (`"Temperature (°C)"`).

---

# Data Robustness

* **Schema check**: assert required fields are present; raise `ValueError` with actionable message if not.
* **Type coercion**: convert datetimes with `pd.to_datetime`, categoricals with explicit order if meaningful.
* **NA handling**: document behavior (drop vs. impute); warn via `meta["warnings"]`.
* **Sampling**: if rendering >1e6 points, auto-sample or aggregate with a logged warning (and parameter to disable).

---

# Determinism & Repro

* Set seeds upstream: `np.random.seed(0)` if synthetic randomness is introduced.
* Always fix `figsize`, `dpi`, `font` for reproducible rendering.
* Do not depend on interactive backends; enforce `"Agg"` for headless.

---

# Performance

* Prefer vector (`.svg`) for line/area; raster (`.png`) for dense scatter/heatmaps.
* Use `linecollection`/`pathcollection` defaults; avoid per-point alpha changes in huge scatters—bin into heatmaps/hexbin.
* Reuse computed encodings (bins, pivots) across facets.

---

# Error Handling & Messaging

* **Fail fast**: missing columns, incompatible dtypes, or empty data → clear `ValueError` with column names and a one-line fix.
* **Graceful degradation**: if seaborn is unavailable, fallback to matplotlib equivalents with the same encodings and document via `meta["warnings"]`.

---

# Security & I/O

* Never open arbitrary files/URLs.
* Only write to provided sandbox path or return bytes.
* Strip/escape user-supplied text used in titles/labels.

---

# Minimal API Surface (suggested)

```python
def make_axes_plot(df, spec) -> dict:
    """
    spec: {
      "kind": "scatter|line|hist|bar|heatmap|ecdf|kde|box|violin|hexbin",
      "enc":  { "x": "...", "y": "...", "hue": "...", "size": "...", "style": "...",
                "row": null, "col": null },  # row/col ignored here (axes-level)
      "opts": { "figsize": [6,4], "dpi": 150, "palette": "colorblind",
                "sharex": false, "sharey": false, "title": "", "xlabel": "", "ylabel": "" },
      "stat": { "binwidth": null, "bins": null, "agg": "mean|median|count", ... }
    }
    Returns: {"fig": fig, "axes": axes, "bytes": png_bytes, "meta": {...}}
    """
```

```python
def make_facet_plot(df, spec) -> dict:
    """
    Uses seaborn figure-level when enc.row or enc.col are provided or when `spec["facet"] is True`.
    Returns: {"fig": fig, "grid": g, "bytes": png_bytes, "meta": {...}}
    """
```

---

# Templates (battle-tested)

## 1) Axes-level (single/multi-axes)

```python
import io
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def axes_plot(df, kind, enc, opts):
    sns.set_theme(context="notebook", style="ticks")
    figsize = tuple(opts.get("figsize", (6,4)))
    dpi     = int(opts.get("dpi", 150))

    fig, axes = plt.subplots(
        nrows=opts.get("nrows", 1), ncols=opts.get("ncols", 1),
        figsize=figsize, constrained_layout=True,
        sharex=opts.get("sharex", False), sharey=opts.get("sharey", False)
    )
    ax_list = np.atleast_1d(axes).ravel()

    # Schema checks
    require = ["x"] + (["y"] if kind not in {"hist"} else [])
    missing = [k for k in require if k not in enc]
    if missing: raise ValueError(f"Missing encodings: {missing}")
    for col in [enc.get("x"), enc.get("y"), enc.get("hue"), enc.get("size")]:
        if col and col not in df.columns:
            raise ValueError(f"Column '{col}' not in DataFrame")

    # Plot dispatch (seaborn Axes-level)
    def draw(ax):
        if kind == "scatter":
            sns.scatterplot(data=df, x=enc["x"], y=enc["y"], hue=enc.get("hue"),
                            size=enc.get("size"), style=enc.get("style"),
                            ax=ax, palette=opts.get("palette", "colorblind"))
        elif kind == "line":
            sns.lineplot(data=df, x=enc["x"], y=enc["y"], hue=enc.get("hue"),
                         ax=ax, estimator=None, palette=opts.get("palette", "colorblind"))
        elif kind == "hist":
            sns.histplot(data=df, x=enc["x"], hue=enc.get("hue"),
                         bins=opts.get("bins"), multiple=opts.get("multiple","layer"),
                         ax=ax, palette=opts.get("palette", "colorblind"))
        elif kind == "heatmap":
            pivot = df.pivot_table(index=enc["y"], columns=enc["x"], values=enc.get("val"))
            m = sns.heatmap(pivot, ax=ax, cbar=False)  # cbar added at fig level below
            return m
        else:
            raise ValueError(f"Unsupported kind: {kind}")

    mappables = []
    for ax in ax_list:
        m = draw(ax)
        if m is not None: mappables.append(m)

        ax.set_title(opts.get("title",""))
        ax.set_xlabel(opts.get("xlabel") or enc["x"])
        if enc.get("y"): ax.set_ylabel(opts.get("ylabel") or enc["y"])
        ax.grid(True, alpha=0.2)

    # Shared colorbar if any mappables
    if mappables:
        fig.colorbar(mappables[0].collections[0], ax=ax_list, fraction=0.05, pad=0.02)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    buf.seek(0); png = buf.getvalue()
    plt.close(fig)

    meta = {"plot_type": kind, "n_axes": len(ax_list), "size": figsize, "dpi": dpi}
    return {"fig": fig, "axes": ax_list.tolist(), "bytes": png, "meta": meta}
```

## 2) Faceting (seaborn figure-level)

```python
import io
import seaborn as sns

def facet_plot(df, kind, enc, opts):
    sns.set_theme(context="notebook", style="ticks")
    dpi = int(opts.get("dpi", 150))

    if kind == "relplot":
        g = sns.relplot(
            data=df, x=enc["x"], y=enc["y"], hue=enc.get("hue"),
            row=enc.get("row"), col=enc.get("col"),
            kind=opts.get("rel_kind","scatter"), facet_kws={"sharex": False, "sharey": False},
            palette=opts.get("palette","colorblind"), height=opts.get("height", 3), aspect=opts.get("aspect", 1.4)
        )
    elif kind == "catplot":
        g = sns.catplot(
            data=df, x=enc["x"], y=enc.get("y"), hue=enc.get("hue"),
            row=enc.get("row"), col=enc.get("col"),
            kind=opts.get("cat_kind","bar"), palette=opts.get("palette","colorblind"),
            height=opts.get("height", 3), aspect=opts.get("aspect", 1.4)
        )
    else:
        raise ValueError("Unsupported facet kind")

    g.set_titles("{row_name} | {col_name}")
    g.set_axis_labels(opts.get("xlabel") or enc["x"], opts.get("ylabel") or enc.get("y",""))
    g.add_legend()

    fig = g.figure
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    buf.seek(0); png = buf.getvalue()
    plt.close(fig)
    meta = {"plot_type": kind, "n_axes": len(g.axes.flat), "dpi": dpi}
    return {"fig": fig, "grid": g, "bytes": png, "meta": meta}
```

---

# “Do / Don’t” Checklist (for the LLM)

**Do**

* ✅ Start with `fig, axes = plt.subplots(..., constrained_layout=True)`.
* ✅ Pass `ax=` to every seaborn Axes-level call.
* ✅ Return `fig` and export image bytes; then `plt.close(fig)`.
* ✅ Use colorblind-safe palettes; set labels, title, legend/colorbar deliberately.
* ✅ Validate columns/types; raise clear `ValueError` on mismatch.
* ✅ Seed randomness and fix `figsize`, `dpi`.

**Don’t**

* ❌ Use `plt.figure()`, `plt.subplot()`, `plt.plot()` without handles.
* ❌ Mix seaborn figure-level grids inside an existing `subplots` figure.
* ❌ Depend on global state (e.g., `plt.gca()`, global rcParams mutations without a context).
* ❌ Save with `plt.savefig(...)` or forget to close figures.
* ❌ Assume columns exist; don’t silently coerce incompatible types.

---

# Optional Enhancements

* **`with plt.rc_context({...})`** for temporary rc tweaks (fonts, tick sizes) per call.
* **Secondary axis** when physically meaningful (`ax.secondary_yaxis` with documented transform).
* **Datetime handling**: auto-format x-axis with `fig.autofmt_xdate()` or `mdates.AutoDateLocator/Formatter`.
* **Ordering categoricals**: accept `order`/`hue_order` in `spec`, enforce deterministic category order.

---

If you’d like, I can turn this into a ready-to-import `plot_agent/` module (with unit tests and a few golden-image tests for regression) or trim it down into a one-page README for contributors.
