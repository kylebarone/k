from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Literal
import re

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


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

    @field_validator("color_map")
    @classmethod
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

    @model_validator(mode="after")
    def _defaults_and_semantics(self):
        if self.type in {ChartType.line, ChartType.area} and self.mode is None:
            self.mode = Mode.lines
        if self.type != ChartType.bar:
            self.orientation = None
        if self.type != ChartType.histogram:
            self.histnorm = None
        return self

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

    @field_validator("y")
    @classmethod
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

    @field_validator("colorway")
    @classmethod
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

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

class VizSpec(BaseModel):
    version: Literal["1.0"] = "1.0" 
    chart: ChartSpec
    data: DataSpec
    layout: Optional[LayoutSpec] = None
    plotly_config: Optional[PlotlyJSConfig] = Field(None, alias="plotly_config")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _semantic_checks(self):
        # Heatmap requires x, y, z to be named. (Matrix hydration will enforce shape)
        if self.chart and self.chart.type == ChartType.heatmap:
            missing = [k for k in ("x", "y", "z") if getattr(self.data, k) is None]
            if missing:
                raise ValueError(f"heatmap requires x, y, z; missing: {missing}")

        # y2_for must reference y columns if y is a list
        if self.data and self.data.axis and self.data.axis.y2_for and isinstance(self.data.y, list):
            bad = set(self.data.axis.y2_for) - set(self.data.y)
            if bad:
                raise ValueError(f"y2_for contains columns not in y: {sorted(bad)}")

        # Disallow simultaneous multi-y and series split (keeps traces predictable)
        if self.data and isinstance(self.data.y, list) and self.data.series and self.data.series.by:
            raise ValueError("cannot use list(y) together with series.by; choose one strategy")

        # Histogram must specify at least one column (x or y)
        if self.chart and self.chart.type == ChartType.histogram:
            if not (self.data and (self.data.x or self.data.y)):
                raise ValueError("histogram requires one of x or y")

        # Area must not be 'markers' only
        if self.chart and self.chart.type == ChartType.area and self.chart.mode == Mode.markers:
            raise ValueError("area charts require 'lines' or 'lines+markers' mode")

        return self
