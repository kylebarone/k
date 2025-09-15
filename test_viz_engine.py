# test_viz_engine.py
from __future__ import annotations
import argparse, os, json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd

from viz_engine import compile_payload, SpecValidationError, CompileError


def _mk_sales_timeseries() -> pd.DataFrame:
    """Daily revenue for two regions."""
    np.random.seed(7)
    start = datetime(2024, 1, 1)
    days = 30
    rows = []
    regions = ["na", "eu"]
    for d in range(days):
        date = start + timedelta(days=d)
        for r in regions:
            base = 1000 if r == "na" else 800
            rows.append({
                "date": date,
                "region": r,
                "revenue": base + np.random.randint(-100, 120),
            })
    return pd.DataFrame(rows)


def _mk_monthly_units_aov() -> pd.DataFrame:
    """Monthly units + AOV; good for dual-axis demo."""
    months = pd.date_range("2024-01-01", periods=6, freq="MS").strftime("%Y-%m").tolist()
    units = [1200, 900, 1500, 1100, 1700, 1600]
    aov   = [42.0, 43.5, 41.2, 45.0, 47.3, 46.8]
    return pd.DataFrame({"month": months, "units": units, "aov": aov})


def _mk_category_revenue() -> pd.DataFrame:
    """Category revenue split by region; already aggregated."""
    return pd.DataFrame({
        "category": ["A","B","C","D","E","F"],
        "region":   ["na","na","eu","eu","na","eu"],
        "revenue":  [120, 90, 130, 80, 150, 70],
    })


def _mk_heatmap_long() -> pd.DataFrame:
    """Long-form product x month with value; no duplicate (x,y) pairs."""
    products = ["p1","p2","p3"]
    months   = ["2024-01","2024-02","2024-03","2024-04"]
    rows = []
    v = 10
    for m in months:
        for p in products:
            rows.append({"month": m, "product": p, "value": v})
            v += 5
    return pd.DataFrame(rows)


def spec_lines_by_region() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "chart": {"type": "line", "mode": "lines"},
        "data": {
            "x": "date",
            "y": "revenue",
            "series": {"by": "region"},
            "labels": {"series": {"na": "NA", "eu": "EU"}},
            "encodings": {"line_shape": "linear", "marker_size": 6, "opacity": 0.95}
        },
        "layout": {
            "title": "Revenue by Region (Daily)",
            "xaxis_title": "Date",
            "yaxis_title": "Revenue",
            "hovermode": "x unified",
            "legend": {"orientation": "h", "y": 1.08, "x": 0},
            "template": "plotly_white"
        },
        "plotly_config": {"responsive": True, "displaylogo": False}
    }


def spec_dual_axis_lines() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "chart": {"type": "line", "mode": "lines+markers"},
        "data": {
            "x": "month",
            "y": ["units", "aov"],
            "axis": {"y2_for": ["aov"]},
            "labels": {"y": {"units": "Units", "aov": "Avg Order Value"}},
            "encodings": {"line_shape": "linear", "marker_size": 6}
        },
        "layout": {
            "title": "Units & AOV (Dual Axis)",
            "xaxis_title": "Month",
            "yaxis_title": "Units",
            "yaxis2_title": "AOV",
            "hovermode": "x unified",
            "template": "plotly_white"
        },
        "plotly_config": {"responsive": True}
    }


def spec_bar_by_region() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "chart": {"type": "bar", "barmode": "group", "orientation": "v"},
        "data": {
            "x": "category",
            "y": "revenue",
            "series": {"by": "region"},
            "labels": {"series": {"na": "NA", "eu": "EU"}},
            "colors": {"color_map": {"NA": "#1f77b4", "EU": "#ff7f0e"}}
        },
        "layout": {
            "title": "Revenue by Category, grouped by Region",
            "xaxis_title": "Category",
            "yaxis_title": "Revenue",
            "template": "plotly_white"
        },
        "plotly_config": {"responsive": True}
    }


def spec_heatmap() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "chart": {"type": "heatmap"},
        "data": {
            "x": "month",
            "y": "product",
            "z": "value"
        },
        "layout": {
            "title": "Product × Month Heatmap",
            "xaxis_title": "Month",
            "yaxis_title": "Product",
            "template": "plotly_white"
        },
        "plotly_config": {"responsive": True}
    }


CASES: Dict[str, Tuple[pd.DataFrame, Dict[str, Any]]] = {
    "lines": (_mk_sales_timeseries(), spec_lines_by_region()),
    "dual_axis": (_mk_monthly_units_aov(), spec_dual_axis_lines()),
    "bar": (_mk_category_revenue(), spec_bar_by_region()),
    "heatmap": (_mk_heatmap_long(), spec_heatmap()),
}


def _write_payload(outdir: str, name: str, payload: Dict[str, Any]) -> str:
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"{name}.plotly.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return path


def _summarize(payload: Dict[str, Any]) -> str:
    fig = payload["figure"]
    traces = fig.get("data", [])
    ttypes = [t.get("type", "?") for t in traces]
    layout_title = (fig.get("layout", {}) or {}).get("title", None)
    if isinstance(layout_title, dict):  # sometimes Plotly wraps title as dict
        layout_title = layout_title.get("text")
    return f"traces={len(traces)} types={sorted(set(ttypes))} title={repr(layout_title)}"


def run_case(name: str, outdir: str) -> None:
    if name not in CASES:
        raise SystemExit(f"unknown --case {name}; choose one of: {', '.join(CASES.keys())} or 'all'")
    df, spec = CASES[name]
    try:
        payload = compile_payload(df, spec)
        fpath = _write_payload(outdir, name, payload)
        print(f"[ok] {name:<9} → {fpath} :: {_summarize(payload)}")
    except (SpecValidationError, CompileError) as e:
        print(f"[ERR] {name}: {e}")


def main():
    ap = argparse.ArgumentParser(description="Smoke-test viz_engine with sample specs/data")
    ap.add_argument("--case", default="all", help=f"one of: {', '.join(CASES.keys())} or 'all'")
    ap.add_argument("--outdir", default="./out", help="output directory for .plotly.json")
    args = ap.parse_args()

    if args.case == "all":
        for n in CASES.keys():
            run_case(n, args.outdir)
    else:
        run_case(args.case, args.outdir)


if __name__ == "__main__":
    main()
