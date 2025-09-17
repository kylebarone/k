
from __future__ import annotations
from typing import Dict, Any, Optional
import json

import plotly.graph_objects as go
import plotly.io as pio

def figure_to_json_dict(fig: go.Figure) -> Dict[str, Any]:
    # ensure clean JSON-serializable dict (no numpy types etc.)
    return json.loads(pio.to_json(fig))

def json_dict_to_figure(d: Dict[str, Any]) -> go.Figure:
    return pio.from_json(json.dumps(d))

def write_html(fig: go.Figure, path: str, *, include_plotlyjs: str = "cdn", full_html: bool = True) -> None:
    pio.write_html(fig, path, include_plotlyjs=include_plotlyjs, full_html=full_html)

def to_image_bytes(fig: go.Figure, *, format: str = "png", scale: float = 2.0) -> Optional[bytes]:
    """Return image bytes if kaleido is available; otherwise return None."""
    try:
        return pio.to_image(fig, format=format, scale=scale)
    except Exception:
        return None
