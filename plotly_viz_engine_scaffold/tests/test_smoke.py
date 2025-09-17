
import pandas as pd
import numpy as np
from pydantic_viz_spec import VizSpec, ChartSpec, DataSpec, LayoutSpec, ChartType, Orientation, BarMode
from plotly_viz_engine import compile_figure

def test_bar_multi():
    df = pd.DataFrame({"x":[1,2,3], "A":[1,2,3], "B":[3,2,1]})
    spec = VizSpec(
        chart=ChartSpec(type=ChartType.bar, orientation=Orientation.v, barmode=BarMode.group),
        data=DataSpec(x="x", y=["A","B"]),
        layout=LayoutSpec(title="AB")
    )
    fig = compile_figure(df, spec)
    assert len(fig.data) == 2

def test_line_series_split():
    df = pd.DataFrame({"x":[1,1,2,2], "y":[1,2,3,4], "g":["A","B","A","B"]})
    spec = VizSpec(
        chart=ChartSpec(type=ChartType.line),
        data=DataSpec(x="x", y="y", series={"by":"g"}),
        layout=LayoutSpec(title="split")
    )
    fig = compile_figure(df, spec)
    assert len(fig.data) == 2
