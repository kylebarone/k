# render_payload.py
import sys, json
import plotly.io as pio
import plotly.graph_objects as go

def load_any(path: str) -> tuple[go.Figure, dict]:
    """Load either:
       A) your payload: { figure: {...}, plotly_config: {...} }, or
       B) a pure Plotly figure JSON (pio.write_json).
    """
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    # A) payload shape (your engine outputs this)
    if isinstance(obj, dict) and "figure" in obj:
        fig = pio.from_json(json.dumps(obj["figure"]), output_type="Figure", skip_invalid=False)
        cfg = obj.get("plotly_config", {}) or {}
        return fig, cfg

    # B) pure figure JSON (created by pio.write_json or fig.to_json)
    fig = pio.read_json(path, output_type="Figure", skip_invalid=False)
    return fig, {}

def main():
    if len(sys.argv) < 2:
        print("usage: python render_payload.py path/to/file.plotly.json")
        raise SystemExit(2)

    fig, cfg = load_any(sys.argv[1])

    # Show in your default browser (or set pio.renderers.default elsewhere)
    pio.show(fig, config=cfg)

if __name__ == "__main__":
    main()
