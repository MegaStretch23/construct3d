"""construct3d command line: build / inspect / sample / selftest."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from . import __version__
from .model import InputError, build_scene
from .viewer import render_html

SAMPLE = [
    {"name": "Canvas tote", "category": "bags", "width": 38, "depth": 10, "height": 40, "color": "#7f8c8d", "price": "$16.00"},
    {"name": "Art print 30x40", "category": "wall art", "width": 30, "depth": 3, "height": 40, "color": "#d68910", "price": "$22.00"},
    {"name": "Desk lamp", "category": "lighting", "price": "$31.00",
     "parts": [
         {"name": "base", "shape": "cylinder", "size": [8, 2], "pos": [0, 1, 0], "color": "#2c3e50"},
         {"name": "arm", "shape": "cylinder", "size": [0.8, 30], "pos": [0, 17, 0], "color": "#7f8c8d"},
         {"name": "shade", "shape": "cone", "size": [7, 9], "pos": [0, 36.5, 0], "color": "#d68910"},
         {"name": "bulb", "shape": "sphere", "size": [2.5], "pos": [0, 33, 0], "color": "#f9e79f"}]},
    {"name": "Water bottle", "category": "kitchen", "width": 7, "depth": 7, "height": 24, "color": "#27ae60", "price": "$18.00"},
    {"name": "Ceramic mug", "category": "kitchen", "width": 8, "depth": 8, "height": 9.5, "color": "#2980b9", "price": "$14.00"},
    {"name": "Rubber ball", "category": "toys", "width": 6.5, "depth": 6.5, "height": 6.5, "color": "#c0392b", "price": "$3.00"},
]


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except OSError as e:
        raise InputError(f"cannot read {path}: {e.strerror}")


def _scene(a):
    fmt = a.format if a.format != "auto" else (("csv" if a.input.lower().endswith(".csv") else None) if a.input != "-" else None)
    return build_scene(_read(a.input), fmt, a.unit, a.title, a.gap, a.cols)


def cmd_build(a) -> int:
    scene = _scene(a)
    Path(a.output).write_text(render_html(scene), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps(scene, indent=1) + "\n", encoding="utf-8")
    s = scene["stats"]
    print(f"wrote {a.output}: {s['items']} products, {s['parts']} parts, scene {s['world_min']} .. {s['world_max']} cm")
    return 0


def inspect_text(scene: dict) -> str:
    rows = [("id", "W x D x H (cm)", "parts", "source", "at (x, z)")]
    for it in scene["items"]:
        d = it["dims_cm"]
        rows.append((it["id"], f"{d[0]:g} x {d[2]:g} x {d[1]:g}", str(len(it["parts"])), it["source"], f"({it['position'][0]:g}, {it['position'][2]:g})"))
    w = [max(len(r[i]) for r in rows) for i in range(5)]
    lines = ["  ".join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip() for r in rows]
    lines.insert(1, "  ".join("-" * x for x in w))
    s = scene["stats"]
    lines.append(f"{s['items']} products, {s['parts']} parts; scene bounds {s['world_min']} .. {s['world_max']} cm")
    return "\n".join(lines)


def cmd_inspect(a) -> int:
    print(inspect_text(_scene(a)))
    return 0


def cmd_sample(a) -> int:
    print(json.dumps(SAMPLE, indent=2))
    return 0


def cmd_selftest(a) -> int:
    import tempfile
    scene = build_scene(json.dumps(SAMPLE))
    page = render_html(scene)
    assert scene["stats"]["items"] == 6 and scene["stats"]["parts"] >= 9
    assert page.count("<canvas") == 1 and "scene-data" in page
    for it in scene["items"]:
        assert abs(it["bounds"]["min"][1]) < 1e-6, "items sit on the floor"
    evil = build_scene(json.dumps([{"name": "</script><b>x", "width": 1, "depth": 1, "height": 1}]))
    assert "</script><b>" not in render_html(evil), "script-safe name"
    try:
        build_scene('[{"name": "bad", "width": -1, "depth": 1, "height": 1}]')
        raise AssertionError("negative width accepted")
    except InputError:
        pass
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "x.html"
        out.write_text(page, encoding="utf-8")
        assert out.stat().st_size > 600_000
    print(f"construct3d {__version__} selftest OK ({scene['stats']['items']} products, {scene['stats']['parts']} parts, page {len(page) // 1024} KB)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="construct3d", description="Product list -> one self-contained interactive 3D HTML file.")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("input", help="products .json or .csv, or - for stdin")
        p.add_argument("--format", choices=["auto", "json", "csv"], default="auto")
        p.add_argument("--unit", choices=["cm", "mm", "m", "in"], default="cm", help="unit of the input lengths (default cm)")
        p.add_argument("--title", default="Constructs")
        p.add_argument("--gap", type=float, default=None, help="gap between products in cm (default 25%% of the largest footprint)")
        p.add_argument("--cols", type=int, default=None, help="products per row (default: square-ish)")
    b = sub.add_parser("build", help="write the viewer HTML"); common(b)
    b.add_argument("-o", "--output", default="constructs.html"); b.add_argument("--json", help="also write the scene JSON here")
    i = sub.add_parser("inspect", help="print sizes and layout as a table"); common(i)
    sub.add_parser("sample", help="print a sample product list (JSON)")
    sub.add_parser("selftest", help="quick internal check")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    try:
        return {"build": cmd_build, "inspect": cmd_inspect, "sample": cmd_sample, "selftest": cmd_selftest}[a.cmd](a)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
