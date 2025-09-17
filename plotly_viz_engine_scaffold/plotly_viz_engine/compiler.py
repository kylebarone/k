
from __future__ import annotations
from typing import Dict, Any, Optional
import json

import pandas as pd
import plotly.graph_objects as go

from pydantic_viz_spec import VizSpec
from .plotly_builder import PlotlyFigureBuilder
from .io_utils import figure_to_json_dict

class Compiler:
    """Director that composes the builder steps. Keep it tiny and deterministic."""
    def __init__(self, figure_builder: Optional[PlotlyFigureBuilder] = None):
        self.builder = figure_builder or PlotlyFigureBuilder()

    def compile(self, df: pd.DataFrame, spec: VizSpec) -> go.Figure:
        return self.builder.start().bind_data(df).apply_spec(spec).build()

def compile_figure(df: pd.DataFrame, spec: VizSpec) -> go.Figure:
    return Compiler().compile(df, spec)

def compile_payload(df: pd.DataFrame, spec: VizSpec) -> Dict[str, Any]:
    """Return JSON-safe payload containing the figure dict + plotly_config + viz_spec_version."""
    fig = compile_figure(df, spec)
    payload = {
        "figure": figure_to_json_dict(fig),
        "plotly_config": (spec.plotly_config.model_dump() if spec.plotly_config else {}),
        "viz_spec_version": spec.version,
    }
    return payload
