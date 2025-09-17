
import pandas as pd
import numpy as np
from pydantic_viz_spec import VizSpec, ChartSpec, DataSpec, LayoutSpec, ChartType, Orientation, BarMode, Mode, HistNorm, LineShape
from plotly_viz_engine import compile_figure, compile_payload, write_html

# Simple dataframe
df = pd.DataFrame({
    "date": pd.date_range("2024-01-01", periods=10, freq="D"),
    "revenue": np.linspace(10, 20, 10),
    "margin_pct": np.linspace(30, 50, 10),
    "region": ["NA","EMEA"] * 5,
    "category": list("ABCDEFGHIJ"),
    "value": np.random.randint(1, 100, 10),
})

# Example 1: dual-axis line
spec = VizSpec(
    chart=ChartSpec(type=ChartType.line, mode=Mode.lines),
    data=DataSpec(
        x="date",
        y=["revenue", "margin_pct"],
        axis={"y2_for": ["margin_pct"]},
        labels={"y": {"revenue": "Revenue ($)", "margin_pct": "Margin (%)"}},
        encodings={"line_shape": LineShape.spline, "opacity": 0.95}
    ),
    layout=LayoutSpec(
        title="Revenue vs Margin",
        yaxis_title="Revenue ($)",
        yaxis2_title="Margin (%)",
        hovermode="x unified"
    ),
)

fig = compile_figure(df, spec)
write_html(fig, "/mnt/data/example_dual_axis_line.html")
print("Wrote /mnt/data/example_dual_axis_line.html")

# Example 2: stacked horizontal bars by region
spec2 = VizSpec(
    chart=ChartSpec(type=ChartType.bar, orientation=Orientation.h, barmode=BarMode.stack),
    data=DataSpec(x="value", y="category", series={"by":"region"}),
    layout=LayoutSpec(title="Category Values by Region", hovermode="y unified"),
)
fig2 = compile_figure(df, spec2)
write_html(fig2, "/mnt/data/example_stacked_bars.html")
print("Wrote /mnt/data/example_stacked_bars.html")

# Example 3: histogram density
spec3 = VizSpec(
    chart=ChartSpec(type=ChartType.histogram, histnorm=HistNorm.density),
    data=DataSpec(x="value"),
    layout=LayoutSpec(title="Histogram Density")
)
fig3 = compile_figure(df, spec3)
write_html(fig3, "/mnt/data/example_hist.html")
print("Wrote /mnt/data/example_hist.html")
