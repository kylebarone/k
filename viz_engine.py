from __future__ import annotations
from typing import Any, Dict, Optional, Union, List, Tuple
import json

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

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
            return VizSpec.model_validate_json(spec)
        return VizSpec.model_validate(spec)
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

# --- serde helpers for figure JSON round-trip ---
import json
import plotly.io as pio
import plotly.graph_objects as go
from typing import Tuple, Dict, Any

def figure_to_json_dict(fig: go.Figure) -> Dict[str, Any]:
    """Use Plotly's encoder to get a pure-JSON dict for a figure."""
    return json.loads(pio.to_json(fig, validate=False, pretty=False))

def json_dict_to_figure(fig_json: Dict[str, Any]) -> go.Figure:
    """Construct a Figure from a JSON-safe dict (the reverse of figure_to_json_dict)."""
    return pio.from_json(json.dumps(fig_json), output_type="Figure", skip_invalid=False)


def compile_payload(
    df: pd.DataFrame,
    spec: Union[VizSpec, Dict[str, Any], str],
    *,
    ensure_ascii: bool = False,
    separators: Tuple[str, str] = (",", ":"),
) -> Dict[str, Any]:
    model = parse_viz_spec(spec)
    fig = compile_figure(df, model)

    fig.show()
    # Force pure-JSON (lists for arrays), not json+binary
    fig_json_str = pio.to_json(fig, validate=False, pretty=False, engine="json", remove_uids=True)
    fig_json: Dict[str, Any] = json.loads(fig_json_str)

    payload = {
        "figure": fig_json,
        "plotly_config": (model.plotly_config.model_dump(by_alias=True) if model.plotly_config else {}),
        "viz_spec_version": model.version,
    }

    json.dumps(payload, ensure_ascii=ensure_ascii, separators=separators)  # final guard
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
            display_name = _label_y(spec, yc)
            tr = go.Scatter(
                x=df[x] if x else None,
                y=df[yc],
                mode=mode,
                name=display_name,
                text=textvals,
                **area_opts,
            )
            _apply_common(tr, name_key=display_name, spec=spec)
            _route_axis(tr, ycol=yc, spec=spec)
            fig.add_trace(tr)

    elif data.series and data.series.by:
        group_col = data.series.by
        ycol = data.y if isinstance(data.y, str) or data.y is None else data.y[0]
        for key, g in df.groupby(group_col):
            display_name = _label_series(spec, key, fallback=_label_y(spec, ycol))
            tr = go.Scatter(
                x=g[x] if x else None,
                y=g[ycol] if ycol else None,
                mode=mode,
                name=display_name,
                text=g[data.text] if data.text else None,
                **area_opts,
            )
            _apply_common(tr, name_key=display_name, spec=spec)
            _route_axis(tr, ycol=ycol, spec=spec)
            fig.add_trace(tr)

    else:
        ycol = data.y if isinstance(data.y, str) or data.y is None else data.y[0]
        display_name = _label_y(spec, ycol)
        tr = go.Scatter(
            x=df[x] if x else None,
            y=df[ycol] if ycol else None,
            mode=mode,
            name=display_name,
            text=textvals,
            **area_opts,
        )
        _apply_common(tr, name_key=display_name, spec=spec)
        _route_axis(tr, ycol=ycol, spec=spec)
        fig.add_trace(tr)


def _add_bar(fig: go.Figure, df: pd.DataFrame, spec: VizSpec) -> None:
    data = spec.data
    orient = (spec.chart.orientation.value if spec.chart.orientation else Orientation.v.value)
    X, Y = (data.x, data.y) if orient == "v" else (data.y, data.x)
    textvals = df[data.text] if data.text else None

    if isinstance(data.y, list) and not (data.series and data.series.by):
        for yc in data.y:
            display_name = _label_y(spec, yc)
            tr = go.Bar(**(
                {"x": df[X], "y": df[yc]} if orient == "v" else {"x": df[yc], "y": df[X]}
            ), name=display_name, text=textvals)
            _apply_common(tr, name_key=display_name, spec=spec)
            _route_axis(tr, ycol=yc, spec=spec)
            fig.add_trace(tr)

    elif data.series and data.series.by:
        group_col = data.series.by
        ycol = data.y if isinstance(data.y, str) else data.y[0]
        for key, g in df.groupby(group_col):
            display_name = _label_series(spec, key, fallback=_label_y(spec, ycol))
            tr = go.Bar(**(
                {"x": g[X], "y": g[ycol]} if orient == "v" else {"x": g[ycol], "y": g[X]}
            ), name=display_name, text=g[data.text] if data.text else None)
            _apply_common(tr, name_key=display_name, spec=spec)
            _route_axis(tr, ycol=ycol, spec=spec)
            fig.add_trace(tr)

    else:
        ycol = data.y if isinstance(data.y, str) else data.y[0]
        display_name = _label_y(spec, ycol)
        tr = go.Bar(**(
            {"x": df[X], "y": df[ycol]} if orient == "v" else {"x": df[ycol], "y": df[X]}
        ), name=display_name, text=textvals)
        _apply_common(tr, name_key=display_name, spec=spec)
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
        display_name = _label_y(spec, data.y)
        tr = go.Box(x=df[data.x], y=df[data.y], boxpoints="outliers", name=display_name,
                    text=df[data.text] if data.text else None)
        _apply_common(tr, name_key=display_name, spec=spec)
        fig.add_trace(tr)
    else:
        ycol = data.y if isinstance(data.y, str) else (data.y[0] if isinstance(data.y, list) else None)
        display_name = _label_y(spec, ycol)
        tr = go.Box(y=df[ycol], boxpoints="outliers", name=display_name,
                    text=df[data.text] if data.text else None)
        _apply_common(tr, name_key=display_name or "", spec=spec)
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
    display_name = data.name or _label_y(spec, val_col)
    tr = go.Pie(labels=df[data.x], values=df[val_col], text=df[data.text] if data.text else None,
                name=display_name)
    _apply_common(tr, name_key=display_name, spec=spec)
    fig.add_trace(tr)


# ---------- Helpers: cosmetics & guards ----------

def _marker_json(trace: go.BaseTraceType) -> Dict[str, Any]:
    m = getattr(trace, "marker", None)
    if m is None:
        return {}
    try:
        return (m.to_plotly_json() or {})  # Plotly object → dict
    except Exception:
        return dict(m) if isinstance(m, dict) else {}

def _line_json(trace: go.BaseTraceType) -> Dict[str, Any]:
    l = getattr(trace, "line", None)
    if l is None:
        return {}
    try:
        return (l.to_plotly_json() or {})
    except Exception:
        return dict(l) if isinstance(l, dict) else {}


# --- replace your existing _apply_common with this version ---
def _apply_common(trace: go.BaseTraceType, *, name_key: str, spec: VizSpec) -> None:
    enc = spec.data.encodings
    colors = spec.data.colors.color_map if (spec.data.colors and spec.data.colors.color_map) else None

    # Encodings: opacity, marker.size, line.shape
    if enc:
        if enc.opacity is not None:
            trace.update(opacity=enc.opacity)

        if hasattr(trace, "marker") and enc.marker_size is not None:
            marker = _marker_json(trace)
            marker.update(size=enc.marker_size)
            trace.update(marker=marker)

        if hasattr(trace, "line") and enc.line_shape is not None:
            line = _line_json(trace)
            line.update(shape=enc.line_shape.value)
            trace.update(line=line)

    # Color mapping (applies to marker.color and/or line.color when present)
    if colors and name_key:
        col = colors.get(str(name_key))
        if col:
            if hasattr(trace, "marker"):
                marker = _marker_json(trace)
                marker.update(color=col)
                trace.update(marker=marker)
            if hasattr(trace, "line"):
                line = _line_json(trace)
                line.update(color=col)
                trace.update(line=line)



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
