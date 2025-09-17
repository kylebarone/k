
from __future__ import annotations
from typing import List, Dict, Callable, Optional, Any
from dataclasses import dataclass
import pandas as pd
import plotly.graph_objects as go

# Import your VizSpec models from the uploaded file (assumed in PYTHONPATH)
from pydantic_viz_spec import (
    VizSpec, ChartType, Mode, Orientation, BarMode, HistNorm, LineShape,
)

TraceFactory = Callable[[pd.DataFrame, VizSpec], List[go.BaseTraceType]]

@dataclass
class _State:
    df: Optional[pd.DataFrame] = None
    spec: Optional[VizSpec] = None
    traces: Optional[List[go.BaseTraceType]] = None
    layout: Dict[str, Any] = None

class PlotlyFigureBuilder:
    """Concrete builder that consumes a VizSpec + DataFrame and produces a plotly.graph_objects.Figure."""
    def __init__(self):
        self._s = _State(traces=[], layout={})

    # Builder-ish lifecycle
    def start(self) -> "PlotlyFigureBuilder":
        self._s = _State(traces=[], layout={})
        return self

    def bind_data(self, df: pd.DataFrame) -> "PlotlyFigureBuilder":
        self._s.df = df
        return self

    def apply_spec(self, spec: VizSpec) -> "PlotlyFigureBuilder":
        self._s.spec = spec
        self._s.traces = _build_traces(self._s.df, spec)
        self._s.layout = _hydrate_layout(spec)
        return self

    def build(self) -> go.Figure:
        fig = go.Figure(data=self._s.traces or [])
        fig.update_layout(**(self._s.layout or {}))
        return fig


# ---------- Registry & dispatch ----------

_MARK_REGISTRY: Dict[ChartType, TraceFactory] = {}

def register_mark(t: ChartType):
    def deco(fn: TraceFactory):
        _MARK_REGISTRY[t] = fn
        return fn
    return deco

def _build_traces(df: pd.DataFrame, spec: VizSpec) -> List[go.BaseTraceType]:
    t = spec.chart.type
    if t not in _MARK_REGISTRY:
        raise ValueError(f"No mark factory registered for chart type: {t}")
    return _MARK_REGISTRY[t](df, spec)


# ---------- Shared helpers ----------

def _resolve_trace_name(raw: str, labels_map: Optional[Dict[str, str]]) -> str:
    if labels_map and raw in labels_map:
        return labels_map[raw]
    return raw

def _apply_common_encodings(trace: go.BaseTraceType, spec: VizSpec) -> None:
    enc = (spec.data.encodings or None)
    if not enc:
        return
    # opacity
    if enc.opacity is not None:
        trace.opacity = enc.opacity
    # marker size
    try:
        if enc.marker_size is not None and hasattr(trace, "marker"):
            # merge-friendly update
            marker = getattr(trace, "marker", {}) or {}
            marker["size"] = enc.marker_size
            trace.marker = marker
    except Exception:
        pass
    # line shape (Scatter)
    if enc.line_shape is not None and isinstance(trace, go.Scatter):
        trace.line = {**(trace.line or {}), "shape": enc.line_shape.value}

def _apply_color(trace: go.BaseTraceType, name: str, spec: VizSpec) -> None:
    cmap = (spec.data.colors.color_map if spec.data.colors else None)
    if not cmap:
        return
    color = cmap.get(name)
    if not color:
        return
    # Try to set both marker and line color when available
    if hasattr(trace, "marker") and trace.marker is not None:
        m = dict(trace.marker)
        m["color"] = color
        trace.marker = m
    if hasattr(trace, "line") and trace.line is not None:
        l = dict(trace.line)
        l["color"] = color
        trace.line = l

def _maybe_y2(name: str, spec: VizSpec) -> Optional[str]:
    axis = spec.data.axis
    if axis and axis.y2_for:
        if name in axis.y2_for:
            return "y2"
    return None

def _hydrate_layout(spec: VizSpec) -> Dict[str, Any]:
    L = {}
    if spec.layout:
        # simple passthrough of known fields
        if spec.layout.title is not None:       L["title"] = spec.layout.title
        if spec.layout.xaxis_title is not None: L["xaxis_title"] = spec.layout.xaxis_title
        if spec.layout.yaxis_title is not None: L["yaxis_title"] = spec.layout.yaxis_title
        # y2 axis setup if requested
        y2_title = spec.layout.yaxis2_title if spec.layout.yaxis2_title is not None else None
        if (spec.data and spec.data.axis and spec.data.axis.y2_for) or y2_title:
            L["yaxis2"] = {"overlaying": "y", "side": "right"}
            if y2_title:
                L["yaxis2"]["title"] = y2_title

        if spec.layout.hovermode is not None:   L["hovermode"] = spec.layout.hovermode.value
        if spec.layout.template is not None:    L["template"] = spec.layout.template
        if spec.layout.colorway is not None:    L["colorway"] = spec.layout.colorway
        if spec.layout.legend is not None:      L["legend"] = spec.layout.legend
        if spec.layout.height is not None:      L["height"] = spec.layout.height
        if spec.layout.width is not None:       L["width"] = spec.layout.width
    return L


# ---------- Mark factories ----------

@register_mark(ChartType.line)
def _line(df: pd.DataFrame, spec: VizSpec) -> List[go.BaseTraceType]:
    return _scatter_like(df, spec, mode=spec.chart.mode.value if spec.chart.mode else "lines")

@register_mark(ChartType.area)
def _area(df: pd.DataFrame, spec: VizSpec) -> List[go.BaseTraceType]:
    traces = _scatter_like(df, spec, mode=spec.chart.mode.value if spec.chart.mode else "lines")
    # area fill + stacking
    stackgroup = spec.data.axis.area_stackgroup if (spec.data and spec.data.axis) else None
    for tr in traces:
        if isinstance(tr, go.Scatter):
            tr.fill = "tozeroy"
            if stackgroup:
                tr.stackgroup = stackgroup
    return traces

@register_mark(ChartType.scatter)
def _scatter(df: pd.DataFrame, spec: VizSpec) -> List[go.BaseTraceType]:
    return _scatter_like(df, spec, mode=spec.chart.mode.value if spec.chart.mode else "markers")

def _scatter_like(df: pd.DataFrame, spec: VizSpec, *, mode: str) -> List[go.BaseTraceType]:
    xcol = spec.data.x
    labels_y = (spec.data.labels.y if spec.data.labels else None)
    labels_series = (spec.data.labels.series if spec.data.labels else None)

    traces: List[go.BaseTraceType] = []

    if isinstance(spec.data.y, list):
        # multi-y (no series.by). One trace per y column.
        for ycol in spec.data.y:
            name = _resolve_trace_name(labels_y.get(ycol, ycol) if labels_y else ycol, labels_y)
            tr = go.Scatter(x=df[xcol] if xcol else None, y=df[ycol], name=name, mode=mode)
            axis = _maybe_y2(ycol, spec)
            if axis:
                tr.yaxis = axis
            _apply_common_encodings(tr, spec)
            _apply_color(tr, name, spec)
            traces.append(tr)
    else:
        ycol = spec.data.y
        by = spec.data.series.by if (spec.data.series and spec.data.series.by) else None
        if by:
            for cat, g in df.groupby(by, dropna=False):
                raw_name = str(cat)
                name = _resolve_trace_name(raw_name, labels_series)
                tr = go.Scatter(x=g[xcol] if xcol else None, y=g[ycol] if ycol else None, name=name, mode=mode)
                _apply_common_encodings(tr, spec)
                _apply_color(tr, name, spec)
                traces.append(tr)
        else:
            name = spec.data.name or (labels_y.get(ycol, ycol) if (labels_y and ycol) else str(ycol))
            tr = go.Scatter(x=df[xcol] if xcol else None, y=df[ycol] if ycol else None, name=name, mode=mode)
            axis = _maybe_y2(name, spec)
            if axis:
                tr.yaxis = axis
            _apply_common_encodings(tr, spec)
            _apply_color(tr, name, spec)
            traces.append(tr)

    return traces


@register_mark(ChartType.bar)
def _bar(df: pd.DataFrame, spec: VizSpec) -> List[go.BaseTraceType]:
    xcol = spec.data.x
    yval = spec.data.y
    by = spec.data.series.by if (spec.data.series and spec.data.series.by) else None
    orient = (spec.chart.orientation or Orientation.v)

    labels_y = (spec.data.labels.y if spec.data.labels else None)
    labels_series = (spec.data.labels.series if spec.data.labels else None)

    def _xy_for_bar(x, y):
        # Swap if horizontal
        if orient == Orientation.h:
            return y, x
        return x, y

    traces: List[go.BaseTraceType] = []

    if isinstance(yval, list):
        for ycol in yval:
            name = _resolve_trace_name(labels_y.get(ycol, ycol) if labels_y else ycol, labels_y)
            X, Y = _xy_for_bar(df[xcol] if xcol else None, df[ycol])
            tr = go.Bar(x=X, y=Y, name=name, orientation=orient.value)
            axis = _maybe_y2(ycol, spec)
            if axis:
                tr.yaxis = axis if orient == Orientation.v else None
                tr.xaxis = axis if orient == Orientation.h else None
            _apply_common_encodings(tr, spec)
            _apply_color(tr, name, spec)
            traces.append(tr)
    else:
        if by:
            # one bar trace per category in 'by'
            for cat, g in df.groupby(by, dropna=False):
                raw_name = str(cat)
                name = _resolve_trace_name(raw_name, labels_series)
                X, Y = _xy_for_bar(g[xcol] if xcol else None, g[yval] if yval else None)
                tr = go.Bar(x=X, y=Y, name=name, orientation=orient.value)
                _apply_common_encodings(tr, spec)
                _apply_color(tr, name, spec)
                traces.append(tr)
        else:
            name = spec.data.name or (labels_y.get(yval, yval) if (labels_y and yval) else str(yval))
            X, Y = _xy_for_bar(df[xcol] if xcol else None, df[yval] if yval else None)
            tr = go.Bar(x=X, y=Y, name=name, orientation=orient.value)
            axis = _maybe_y2(name, spec)
            if axis:
                tr.yaxis = axis if orient == Orientation.v else None
                tr.xaxis = axis if orient == Orientation.h else None
            _apply_common_encodings(tr, spec)
            _apply_color(tr, name, spec)
            traces.append(tr)

    return traces


@register_mark(ChartType.histogram)
def _histogram(df: pd.DataFrame, spec: VizSpec) -> List[go.BaseTraceType]:
    # Spec guarantees at least one of x or y is present.
    xcol, ycol = spec.data.x, spec.data.y if isinstance(spec.data.y, str) else None
    traces: List[go.BaseTraceType] = []
    if xcol and not ycol:
        tr = go.Histogram(x=df[xcol], histnorm=spec.chart.histnorm.value if spec.chart.histnorm else None)
    elif ycol and not xcol:
        tr = go.Histogram(y=df[ycol], histnorm=spec.chart.histnorm.value if spec.chart.histnorm else None)
    else:
        # If both given, default to x (common convention); could be extended to 2D hist.
        tr = go.Histogram(x=df[xcol], histnorm=spec.chart.histnorm.value if spec.chart.histnorm else None)
    _apply_common_encodings(tr, spec)
    traces.append(tr)
    return traces


@register_mark(ChartType.box)
def _box(df: pd.DataFrame, spec: VizSpec) -> List[go.BaseTraceType]:
    xcol = spec.data.x
    yval = spec.data.y
    by = spec.data.series.by if (spec.data.series and spec.data.series.by) else None
    traces: List[go.BaseTraceType] = []

    if isinstance(yval, list):
        for ycol in yval:
            tr = go.Box(x=df[xcol] if xcol else None, y=df[ycol], name=str(ycol), boxpoints="outliers")
            _apply_common_encodings(tr, spec)
            traces.append(tr)
    else:
        if by:
            for cat, g in df.groupby(by, dropna=False):
                tr = go.Box(x=g[xcol] if xcol else None, y=g[yval] if yval else None, name=str(cat), boxpoints="outliers")
                _apply_common_encodings(tr, spec)
                traces.append(tr)
        else:
            tr = go.Box(x=df[xcol] if xcol else None, y=df[yval] if yval else None, name=str(yval), boxpoints="outliers")
            _apply_common_encodings(tr, spec)
            traces.append(tr)
    return traces


@register_mark(ChartType.heatmap)
def _heatmap(df: pd.DataFrame, spec: VizSpec) -> List[go.BaseTraceType]:
    # Expect long-form with unique (x,y); pivot wide without aggregation.
    xcol, ycol, zcol = spec.data.x, spec.data.y, spec.data.z
    if isinstance(ycol, list):
        raise ValueError("heatmap does not support list(y); provide scalar y and z.")
    piv = df.pivot(index=ycol, columns=xcol, values=zcol).sort_index().sort_index(axis=1)
    tr = go.Heatmap(z=piv.values, x=list(piv.columns), y=list(piv.index))
    _apply_common_encodings(tr, spec)
    return [tr]


@register_mark(ChartType.pie)
def _pie(df: pd.DataFrame, spec: VizSpec) -> List[go.BaseTraceType]:
    # Simple mapping: prefer (names = series.by) if present; else names = x; values = y
    by = spec.data.series.by if (spec.data.series and spec.data.series.by) else None
    if by and isinstance(spec.data.y, str):
        names = df[by]
        values = df[spec.data.y]
    else:
        names = df[spec.data.x] if spec.data.x else None
        values = df[spec.data.y] if isinstance(spec.data.y, str) else None
    tr = go.Pie(labels=names, values=values, sort=False)
    return [tr]
