awesome. here’s a clean, production-lean **two-file engine** you can drop straight into your tool:

* `pydantic_viz_spec.py` — strict schema for structured LLM output (v1 style; v2 works via `from pydantic.v1 import ...`)
* `viz_engine.py` — parser + compiler + hydrator helpers that return `{ "figure": <plotly_json>, "plotly_config": {...}, "viz_spec_version": "1.0" }`

no DI ceremony, but with small seams (label/color maps in the spec) and defensive checks. zero filtering/aggregation. minimal, deterministic, fast.

---

### `pydantic_viz_spec.py`

```python
from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Union, Any
import re

from pydantic import BaseModel, Field, validator, root_validator


# ---------- Enums ----------

class ChartType(str, Enum):
    line = "line"
    scatter = "scatter"
    bar = "bar"
    histogram = "histogram"
    box = "box"
    heatmap = "heatmap"
    pie = "pie"
    area = "area"

class Mode(str, Enum):
    lines = "lines"
    markers = "markers"
    lines_markers = "lines+markers"

class Orientation(str, Enum):
    v = "v"
    h = "h"

class BarMode(str, Enum):
    group = "group"
    stack = "stack"
    relative = "relative"

class HistNorm(str, Enum):
    none = "none"
    percent = "percent"
    probability = "probability"
    density = "density"

class HoverMode(str, Enum):
    x = "x"
    y = "y"
    closest = "closest"
    x_unified = "x unified"
    y_unified = "y unified"

class LineShape(str, Enum):
    linear = "linear"
    spline = "spline"


# ---------- Small validators ----------

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

def _valid_color(s: str) -> bool:
    # Allow hex (#RRGGBB[AA]) or any CSS color name string
    return bool(_HEX.match(s)) or isinstance(s, str)


# ---------- Nested leaf models ----------

class EncodingsSpec(BaseModel):
    marker_size: Optional[int] = Field(6, ge=1, le=64)
    opacity: Optional[float] = Field(0.9, ge=0.0, le=1.0)
    line_shape: Optional[LineShape] = None

class SeriesSpec(BaseModel):
    by: Optional[str] = None

class AxisSpec(BaseModel):
    y2_for: Optional[List[str]] = None            # route these y columns to y2
    area_stackgroup: Optional[str] = None         # only meaningful for area

class LabelsSpec(BaseModel):
    y: Optional[Dict[str, str]] = None            # per-y friendly labels
    series: Optional[Dict[str, str]] = None       # per-series/category labels

class ColorsSpec(BaseModel):
    color_map: Optional[Dict[str, str]] = None

    @validator("color_map")
    def _validate_colors(cls, v):
        if not v:
            return v
        for k, c in v.items():
            if not _valid_color(c):
                raise ValueError(f"Invalid color for key '{k}': {c}")
        return v


# ---------- Core sections ----------

class ChartSpec(BaseModel):
    type: ChartType
    mode: Optional[Mode] = None                   # used by line/scatter/area
    orientation: Optional[Orientation] = None     # used by bar
    barmode: Optional[BarMode] = None             # bar layout behavior
    histnorm: Optional[HistNorm] = None           # histogram

    @root_validator
    def _defaults_and_semantics(cls, values):
        t: ChartType = values.get("type")
        mode: Optional[Mode] = values.get("mode")
        if t in {ChartType.line, ChartType.area} and mode is None:
            values["mode"] = Mode.lines
        if t != ChartType.bar:
            # keep orientation only when bar
            values["orientation"] = None
        if t != ChartType.histogram:
            values["histnorm"] = None
        return values

class DataSpec(BaseModel):
    frame_name: Optional[str] = None
    x: Optional[str] = None
    y: Optional[Union[str, List[str]]] = None
    z: Optional[str] = None
    text: Optional[str] = None
    name: Optional[str] = None  # optional static trace name override (rare)

    series: Optional[SeriesSpec] = None
    axis: Optional[AxisSpec] = None
    encodings: Optional[EncodingsSpec] = None
    labels: Optional[LabelsSpec] = None
    colors: Optional[ColorsSpec] = None

    @validator("y")
    def _unique_y_list(cls, v):
        if isinstance(v, list):
            if not v:
                raise ValueError("y list cannot be empty")
            if len(set(v)) != len(v):
                raise ValueError("y list contains duplicates")
        return v

class LayoutSpec(BaseModel):
    title: Optional[str] = None
    xaxis_title: Optional[str] = None
    yaxis_title: Optional[str] = None
    yaxis2_title: Optional[str] = None
    hovermode: Optional[HoverMode] = None
    template: Optional[str] = None                # let Plotly validate at runtime
    colorway: Optional[List[str]] = None
    legend: Optional[Dict[str, Any]] = None       # open dict to allow any Plotly legend args
    height: Optional[int] = Field(450, ge=200, le=2000)
    width: Optional[int] = Field(None, ge=200, le=4000)

    @validator("colorway")
    def _validate_colorway(cls, v):
        if v:
            for c in v:
                if not _valid_color(c):
                    raise ValueError(f"Invalid color in colorway: {c}")
        return v

class PlotlyJSConfig(BaseModel):
    responsive: bool = True
    displayModeBar: bool = True
    displaylogo: bool = False
    scrollZoom: bool = False
    modeBarButtonsToRemove: Optional[List[str]] = None

    class Config:
        allow_population_by_field_name = True
        allow_population_by_alias = True
        extra = "ignore"

class VizSpec(BaseModel):
    version: str = Field("1.0", const=True)
    chart: ChartSpec
    data: DataSpec
    layout: Optional[LayoutSpec] = None
    plotly_config: Optional[PlotlyJSConfig] = Field(None, alias="plotly_config")

    class Config:
        allow_population_by_field_name = True
        allow_population_by_alias = True
        extra = "forbid"

    @root_validator
    def _semantic_checks(cls, values):
        chart: ChartSpec = values.get("chart")
        data: DataSpec = values.get("data")

        # Heatmap requires x, y, z to be named. (Matrix hydration will enforce shape)
        if chart and chart.type == ChartType.heatmap:
            missing = [k for k in ("x", "y", "z") if getattr(data, k) is None]
            if missing:
                raise ValueError(f"heatmap requires x, y, z; missing: {missing}")

        # y2_for must reference y columns if y is a list
        if data and data.axis and data.axis.y2_for and isinstance(data.y, list):
            bad = set(data.axis.y2_for) - set(data.y)
            if bad:
                raise ValueError(f"y2_for contains columns not in y: {sorted(bad)}")

        # Disallow simultaneous multi-y and series split (keeps traces predictable)
        if data and isinstance(data.y, list) and data.series and data.series.by:
            raise ValueError("cannot use list(y) together with series.by; choose one strategy")

        # Histogram must specify at least one column (x or y)
        if chart and chart.type == ChartType.histogram:
            if not (data and (data.x or data.y)):
                raise ValueError("histogram requires one of x or y")

        # Area must not be 'markers' only
        if chart and chart.type == ChartType.area and chart.mode == Mode.markers:
            raise ValueError("area charts require 'lines' or 'lines+markers' mode")

        return values
```

---

### `viz_engine.py`

```python
from __future__ import annotations
from typing import Any, Dict, Optional, Union, List, Tuple
import json

import pandas as pd
import numpy as np
import plotly.graph_objects as go

from pydantic import ValidationError
from pydantic_viz_spec import VizSpec, ChartType, Mode, Orientation


__all__ = [
    "VizEngineError",
    "SpecParseError",
    "SpecValidationError",
    "CompileError",
    "parse_viz_spec",
    "compile_figure",
    "compile_payload",
]


# ---------- Errors ----------

class VizEngineError(Exception): ...
class SpecParseError(VizEngineError): ...
class SpecValidationError(VizEngineError): ...
class CompileError(VizEngineError): ...


# ---------- Public API ----------

def parse_viz_spec(spec: Union[str, Dict[str, Any], VizSpec]) -> VizSpec:
    """
    Parse/validate a spec provided by an LLM (str JSON or dict) into VizSpec.
    """
    if isinstance(spec, VizSpec):
        return spec
    try:
        if isinstance(spec, str):
            # Allow both raw JSON string and already-dumped JSON
            return VizSpec.parse_raw(spec)
        return VizSpec.parse_obj(spec)
    except ValidationError as ve:
        raise SpecValidationError(ve.json()) from ve
    except Exception as e:
        raise SpecParseError(str(e)) from e


def compile_figure(df: pd.DataFrame, spec: Union[VizSpec, Dict[str, Any], str]) -> go.Figure:
    """
    Deterministic, transform-free (no filters/agg) hydration of a VizSpec into a Plotly Figure.
    """
    model = parse_viz_spec(spec)
    chart = model.chart
    data = model.data
    layout = model.layout

    _ensure_columns(df, [c for c in [data.x] + _listify(data.y) + [data.z, data.text] if c])

    fig = go.Figure()

    # Trace creation
    if chart.type in (ChartType.line, ChartType.scatter, ChartType.area):
        _add_scatter_family(fig, df, model)

    elif chart.type == ChartType.bar:
        _add_bar(fig, df, model)

    elif chart.type == ChartType.histogram:
        _add_histogram(fig, df, model)

    elif chart.type == ChartType.box:
        _add_box(fig, df, model)

    elif chart.type == ChartType.heatmap:
        _add_heatmap(fig, df, model)

    elif chart.type == ChartType.pie:
        _add_pie(fig, df, model)

    else:
        raise CompileError(f"Unsupported chart type: {chart.type}")

    # Layout (presentation only)
    if layout:
        fig.update_layout(
            title=layout.title,
            xaxis_title=layout.xaxis_title,
            yaxis_title=layout.yaxis_title,
            hovermode=(layout.hovermode.value if layout.hovermode else None),
            template=layout.template,
            colorway=layout.colorway,
            legend=layout.legend,
            height=layout.height,
            width=layout.width,
        )
        # y2 only when referenced
        if data.axis and data.axis.y2_for:
            fig.update_layout(yaxis2=dict(
                title=layout.yaxis2_title,
                overlaying="y",
                side="right",
            ))

    # Bar mode lives on layout
    if chart.type == ChartType.bar and chart.barmode:
        fig.update_layout(barmode=chart.barmode.value)

    # Defensive limits
    _guard_traces(fig, max_traces=64)

    return fig


def compile_payload(
    df: pd.DataFrame,
    spec: Union[VizSpec, Dict[str, Any], str],
    *,
    ensure_ascii: bool = False,
    separators: Tuple[str, str] = (",", ":"),
) -> Dict[str, Any]:
    """
    Compile and return a JSON-serializable payload for the FE:
      { "figure": <plotly_json>, "plotly_config": {...}, "viz_spec_version": "1.0" }
    """
    model = parse_viz_spec(spec)
    fig = compile_figure(df, model)
    payload = {
        "figure": fig.to_plotly_json(),
        "plotly_config": (model.plotly_config.dict(by_alias=True) if model.plotly_config else {}),
        "viz_spec_version": model.version,
    }
    # validate serializability early (raises TypeError if something is off)
    json.dumps(payload, ensure_ascii=ensure_ascii, separators=separators)
    return payload


# ---------- Helpers: traces ----------

def _add_scatter_family(fig: go.Figure, df: pd.DataFrame, spec: VizSpec) -> None:
    data = spec.data
    chart = spec.chart
    mode = chart.mode.value if chart.mode else (Mode.lines.value if chart.type in (ChartType.line, ChartType.area) else Mode.markers.value)

    # Area = Scatter + fill (+ optional stackgroup)
    area_opts = {}
    if chart.type == ChartType.area:
        area_opts.update(fill="tozeroy")
        if data.axis and data.axis.area_stackgroup:
            area_opts.update(stackgroup=data.axis.area_stackgroup)

    # Normalize x dtype if it looks like dates (no transform, just dtype casting)
    x = data.x
    if x and not np.issubdtype(df[x].dtype, np.datetime64):
        try:
            df = df.copy()
            df[x] = pd.to_datetime(df[x], errors="ignore")
        except Exception:
            pass

    textvals = df[data.text] if data.text else None

    if isinstance(data.y, list) and not (data.series and data.series.by):
        for yc in data.y:
            tr = go.Scatter(
                x=df[x] if x else None,
                y=df[yc],
                mode=mode,
                name=_label_y(spec, yc),
                text=textvals,
                **area_opts,
            )
            _apply_common(tr, name_key=yc, spec=spec)
            _route_axis(tr, ycol=yc, spec=spec)
            fig.add_trace(tr)

    elif data.series and data.series.by:
        group_col = data.series.by
        for key, g in df.groupby(group_col):
            ycol = data.y if isinstance(data.y, str) or data.y is None else data.y[0]
            tr = go.Scatter(
                x=g[x] if x else None,
                y=g[ycol] if ycol else None,
                mode=mode,
                name=_label_series(spec, key, fallback=_label_y(spec, ycol)),
                text=g[data.text] if data.text else None,
                **area_opts,
            )
            _apply_common(tr, name_key=str(key), spec=spec)
            _route_axis(tr, ycol=ycol, spec=spec)
            fig.add_trace(tr)

    else:
        ycol = data.y if isinstance(data.y, str) or data.y is None else data.y[0]
        tr = go.Scatter(
            x=df[x] if x else None,
            y=df[ycol] if ycol else None,
            mode=mode,
            name=_label_y(spec, ycol),
            text=textvals,
            **area_opts,
        )
        _apply_common(tr, name_key=ycol or "", spec=spec)
        _route_axis(tr, ycol=ycol, spec=spec)
        fig.add_trace(tr)


def _add_bar(fig: go.Figure, df: pd.DataFrame, spec: VizSpec) -> None:
    data = spec.data
    orient = (spec.chart.orientation.value if spec.chart.orientation else Orientation.v.value)
    X, Y = (data.x, data.y) if orient == "v" else (data.y, data.x)
    textvals = df[data.text] if data.text else None

    if isinstance(data.y, list) and not (data.series and data.series.by):
        for yc in data.y:
            tr = go.Bar(**(
                {"x": df[X], "y": df[yc]} if orient == "v" else {"x": df[yc], "y": df[X]}
            ), name=_label_y(spec, yc), text=textvals)
            _apply_common(tr, name_key=yc, spec=spec)
            _route_axis(tr, ycol=yc, spec=spec)
            fig.add_trace(tr)

    elif data.series and data.series.by:
        group_col = data.series.by
        ycol = data.y if isinstance(data.y, str) else data.y[0]
        for key, g in df.groupby(group_col):
            tr = go.Bar(**(
                {"x": g[X], "y": g[ycol]} if orient == "v" else {"x": g[ycol], "y": g[X]}
            ), name=_label_series(spec, key, fallback=_label_y(spec, ycol)),
                text=g[data.text] if data.text else None)
            _apply_common(tr, name_key=str(key), spec=spec)
            _route_axis(tr, ycol=ycol, spec=spec)
            fig.add_trace(tr)

    else:
        ycol = data.y if isinstance(data.y, str) else data.y[0]
        tr = go.Bar(**(
            {"x": df[X], "y": df[ycol]} if orient == "v" else {"x": df[ycol], "y": df[X]}
        ), name=_label_y(spec, ycol), text=textvals)
        _apply_common(tr, name_key=ycol, spec=spec)
        _route_axis(tr, ycol=ycol, spec=spec)
        fig.add_trace(tr)


def _add_histogram(fig: go.Figure, df: pd.DataFrame, spec: VizSpec) -> None:
    data = spec.data
    col = data.x or (data.y if isinstance(data.y, str) else (data.y[0] if isinstance(data.y, list) else None))
    tr = go.Histogram(x=df[col], histnorm=(spec.chart.histnorm.value if spec.chart.histnorm else None))
    _apply_common(tr, name_key=col or "", spec=spec)
    fig.add_trace(tr)


def _add_box(fig: go.Figure, df: pd.DataFrame, spec: VizSpec) -> None:
    data = spec.data
    if data.x and isinstance(data.y, str):
        tr = go.Box(x=df[data.x], y=df[data.y], boxpoints="outliers", name=_label_y(spec, data.y),
                    text=df[data.text] if data.text else None)
        _apply_common(tr, name_key=data.y, spec=spec)
        fig.add_trace(tr)
    else:
        ycol = data.y if isinstance(data.y, str) else (data.y[0] if isinstance(data.y, list) else None)
        tr = go.Box(y=df[ycol], boxpoints="outliers", name=_label_y(spec, ycol),
                    text=df[data.text] if data.text else None)
        _apply_common(tr, name_key=ycol or "", spec=spec)
        fig.add_trace(tr)


def _add_heatmap(fig: go.Figure, df: pd.DataFrame, spec: VizSpec) -> None:
    # Shape rules:
    # - If df is already matrix-like (z only), use values directly
    # - If x,y,z given in long form, require uniqueness on (x,y) pairs; pivot wide without aggregation
    data = spec.data
    x, y, z = data.x, data.y, data.z

    if x and y and z:
        # Enforce uniqueness; no aggregation allowed per contract
        dupe_mask = df.duplicated(subset=[x, y], keep=False)
        if dupe_mask.any():
            raise CompileError("heatmap long-form requires unique (x,y) pairs; pre-aggregate upstream.")
        mat = df.pivot(index=y, columns=x, values=z)
        tr = go.Heatmap(z=mat.values, x=mat.columns.astype(str), y=mat.index.astype(str))
        fig.add_trace(tr)
    else:
        # Fallback: treat df as a numeric matrix
        tr = go.Heatmap(z=df.values)
        fig.add_trace(tr)


def _add_pie(fig: go.Figure, df: pd.DataFrame, spec: VizSpec) -> None:
    data = spec.data
    val_col = data.y if isinstance(data.y, str) else (data.y[0] if isinstance(data.y, list) else None)
    if not (data.x and val_col):
        raise CompileError("pie requires x (labels) and y (values)")
    tr = go.Pie(labels=df[data.x], values=df[val_col], text=df[data.text] if data.text else None,
                name=(data.name or _label_y(spec, val_col)))
    _apply_common(tr, name_key=val_col, spec=spec)
    fig.add_trace(tr)


# ---------- Helpers: cosmetics & guards ----------

def _apply_common(trace: go.BaseTraceType, *, name_key: str, spec: VizSpec) -> None:
    enc = spec.data.encodings
    colors = spec.data.colors.color_map if (spec.data.colors and spec.data.colors.color_map) else None

    if enc:
        if enc.opacity is not None:
            trace.update(opacity=enc.opacity)
        if enc.marker_size is not None and hasattr(trace, "marker"):
            trace.update(marker={"size": enc.marker_size, **(trace.marker.to_plotly_json() if hasattr(trace, "marker") else {})})
        if enc.line_shape is not None and hasattr(trace, "line"):
            trace.update(line={"shape": enc.line_shape.value, **(trace.line.to_plotly_json() if hasattr(trace, "line") else {})})

    if colors and name_key:
        col = colors.get(str(name_key))
        if col:
            if hasattr(trace, "marker"):
                trace.update(marker={"color": col, **(trace.marker.to_plotly_json() if hasattr(trace, "marker") else {})})
            if hasattr(trace, "line"):
                trace.update(line={"color": col, **(trace.line.to_plotly_json() if hasattr(trace, "line") else {})})


def _route_axis(trace: go.BaseTraceType, *, ycol: Optional[str], spec: VizSpec) -> None:
    y2_for = spec.data.axis.y2_for if (spec.data.axis and spec.data.axis.y2_for) else None
    if y2_for and ycol in set(y2_for):
        trace.update(yaxis="y2")


def _guard_traces(fig: go.Figure, *, max_traces: int) -> None:
    count = len(fig.data)
    if count > max_traces:
        raise CompileError(f"trace count {count} exceeds limit {max_traces}")


def _label_y(spec: VizSpec, ycol: Optional[str]) -> str:
    if ycol is None:
        return ""
    labels = spec.data.labels.y if (spec.data.labels and spec.data.labels.y) else {}
    return str(labels.get(str(ycol), ycol))

def _label_series(spec: VizSpec, key: Any, *, fallback: str = "") -> str:
    labels = spec.data.labels.series if (spec.data.labels and spec.data.labels.series) else {}
    return str(labels.get(str(key), key)) if key is not None else fallback


def _listify(v: Optional[Union[str, List[str]]]) -> List[str]:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _ensure_columns(df: pd.DataFrame, cols: List[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise CompileError(f"columns not found in dataframe: {missing}")
```

---

### How you’ll call it in your tool

```python
# df: pandas.DataFrame (already transformed)
# spec_json: dict or JSON string returned by your LLM
from viz_engine import compile_payload

payload = compile_payload(df, spec_json)
# payload["figure"] is Plotly JSON (data + layout)
# payload["plotly_config"] is your FE config
# -> save this payload as one artifact for your FE to render
```

that’s it. if you want me to add tiny unit tests or a micro “smoke” example (fake df + spec) to sanity-check in your IDE, say the word and i’ll drop them in the same style.
