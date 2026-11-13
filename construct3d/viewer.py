"""Assemble the single-file viewer: template + scene JSON + vendored three.js + viewer core. No network at view time."""
from __future__ import annotations
import html, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def asset(rel: str) -> str:
    return (HERE / rel).read_text(encoding="utf-8")


def script_safe_json(obj) -> str:
    """JSON for a <script type=application/json> block: '<' and U+2028/9 escaped so no product name can close the tag."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_html(scene: dict) -> str:
    three = asset("vendor/three.module.min.js")
    core = asset("viewer/core.js")
    for name, text in (("three", three), ("core", core)):
        if "</script" in text.lower():
            raise ValueError(f"{name} source contains '</script' and cannot be inlined")
    n = scene["stats"]["items"]
    vals = {"TITLE": html.escape(scene["title"]), "COUNT": f"{n} product{'s' if n != 1 else ''}, {scene['stats']['parts']} parts",
            "SCENE": script_safe_json(scene), "CORE": core, "THREE": three}
    # one pass: substituted text is never re-scanned for placeholders
    return re.sub(r"__(TITLE|COUNT|SCENE|THREE|CORE)__", lambda m: vals[m.group(1)], asset("viewer/template.html"))
