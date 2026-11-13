"""Normalise products into 'constructs' (a product = a list of primitive parts), compute bounds, lay them out.

Conventions (all lengths in centimetres in the scene, y is up, the item sits on y = 0):
  box       size [x_width, y_height, z_depth]
  cylinder  size [radius, height]      axis = y
  cone      size [radius, height]      axis = y
  sphere    size [radius]
  torus     size [ring_radius, tube_radius]   lies in the XY plane (like three.js TorusGeometry)
  part pos  = centre of the part in item-local coordinates; rot = [rx, ry, rz] degrees, three.js 'XYZ' order.
"""
from __future__ import annotations
import csv, io, json, math, re

SHAPES = {"box": 3, "cylinder": 2, "cone": 2, "sphere": 1, "torus": 2}
UNITS = {"cm": 1.0, "mm": 0.1, "m": 100.0, "in": 2.54}
MAX_DIM = 10000.0
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
PALETTE = ["#c0392b", "#2980b9", "#27ae60", "#d68910", "#8e44ad", "#16a085", "#7f8c8d", "#2c3e50"]


class InputError(ValueError):
    pass


def _num(v, what):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise InputError(f"{what}: not a number: {v!r}")
    if not math.isfinite(x):
        raise InputError(f"{what}: not finite: {v!r}")
    return x


def _pos(v, what):
    x = _num(v, what)
    if x <= 0 or x > MAX_DIM:
        raise InputError(f"{what}: must be > 0 and <= {MAX_DIM:g}, got {x:g}")
    return x


def _color(c, idx):
    if c in (None, ""):
        return PALETTE[idx % len(PALETTE)]
    c = str(c).strip()
    if not c.startswith("#"):
        c = "#" + c
    if not HEX.match(c):
        raise InputError(f"color must be #rrggbb, got {c!r}")
    return c.lower()


def rotate_xyz(v, rot_deg):
    """Apply three.js Euler 'XYZ' (matrix = Rx * Ry * Rz) to vector v."""
    rx, ry, rz = (math.radians(a) for a in rot_deg)
    x, y, z = v
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)       # Rz first
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)      # then Ry
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)       # then Rx
    return (x, y, z)


def local_half_extents(shape, size):
    if shape == "box":
        return (size[0] / 2, size[1] / 2, size[2] / 2)
    if shape in ("cylinder", "cone"):
        return (size[0], size[1] / 2, size[0])
    if shape == "sphere":
        return (size[0],) * 3
    if shape == "torus":
        r = size[0] + size[1]
        return (r, r, size[1])
    raise InputError(f"unknown shape {shape!r}")


def part_bounds(part):
    """Axis-aligned bounds of a part, same rule as three.js Box3.setFromObject (rotate the local AABB corners)."""
    hx, hy, hz = local_half_extents(part["shape"], part["size"])
    rot = part.get("rot") or [0, 0, 0]
    px, py, pz = part["pos"]
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                v = rotate_xyz((sx * hx, sy * hy, sz * hz), rot)
                for i, c in enumerate((v[0] + px, v[1] + py, v[2] + pz)):
                    lo[i] = min(lo[i], c)
                    hi[i] = max(hi[i], c)
    return lo, hi


def parts_bounds(parts):
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for p in parts:
        a, b = part_bounds(p)
        for i in range(3):
            lo[i] = min(lo[i], a[i])
            hi[i] = max(hi[i], b[i])
    return lo, hi


def _r(x):
    return round(x + 0.0, 4)


def clean_part(raw, idx, k):
    if not isinstance(raw, dict):
        raise InputError(f"part {k}: must be an object")
    shape = str(raw.get("shape", "")).lower()
    if shape not in SHAPES:
        raise InputError(f"part {k}: shape must be one of {sorted(SHAPES)}, got {shape!r}")
    size = raw.get("size")
    if not isinstance(size, (list, tuple)) or len(size) != SHAPES[shape]:
        raise InputError(f"part {k}: {shape} needs a size list of {SHAPES[shape]} numbers")
    size = [_pos(s, f"part {k} size") for s in size]
    pos = raw.get("pos", [0, 0, 0])
    if not isinstance(pos, (list, tuple)) or len(pos) != 3:
        raise InputError(f"part {k}: pos must be [x, y, z]")
    pos = [_num(p, f"part {k} pos") for p in pos]
    rot = raw.get("rot")
    if rot is not None:
        if not isinstance(rot, (list, tuple)) or len(rot) != 3:
            raise InputError(f"part {k}: rot must be [rx, ry, rz] degrees")
        rot = [_num(r, f"part {k} rot") for r in rot]
    out = {"name": str(raw.get("name") or f"{shape}-{k + 1}")[:80], "shape": shape,
           "size": [_r(s) for s in size], "pos": [_r(p) for p in pos], "color": _color(raw.get("color"), idx)}
    if rot and any(rot):
        out["rot"] = [_r(r) for r in rot]
    return out


def preset(kind, w, d, h, color):
    """Rough stand-in parts for a product from its overall size. Heuristic by name/category keyword; see README."""
    r = min(w, d) / 2
    if kind == "mug":
        return [{"name": "body", "shape": "cylinder", "size": [r, h], "pos": [0, h / 2, 0], "color": color},
                {"name": "handle", "shape": "torus", "size": [h * 0.25, h * 0.05], "pos": [r + h * 0.2, h / 2, 0], "color": color}]
    if kind == "bottle":
        nh = h * 0.25
        return [{"name": "body", "shape": "cylinder", "size": [r, h - nh], "pos": [0, (h - nh) / 2, 0], "color": color},
                {"name": "neck", "shape": "cone", "size": [r * 0.45, nh], "pos": [0, h - nh / 2, 0], "color": color}]
    if kind == "poster":
        t = max(min(w, h) * 0.02, 0.2)
        return [{"name": "sheet", "shape": "box", "size": [w, h, t], "pos": [0, h / 2, 0], "color": color},
                {"name": "stand", "shape": "box", "size": [w * 0.3, h * 0.04, d], "pos": [0, h * 0.02, 0], "color": "#555555"}]
    if kind == "ball":
        return [{"name": "ball", "shape": "sphere", "size": [min(w, d, h) / 2], "pos": [0, min(w, d, h) / 2, 0], "color": color}]
    if kind == "cylinder":
        return [{"name": "body", "shape": "cylinder", "size": [r, h], "pos": [0, h / 2, 0], "color": color}]
    return [{"name": "body", "shape": "box", "size": [w, h, d], "pos": [0, h / 2, 0], "color": color}]


KEYWORDS = [("mug", "mug"), ("cup", "mug"), ("bottle", "bottle"), ("tumbler", "bottle"), ("poster", "poster"), ("print", "poster"),
            ("frame", "poster"), ("ball", "ball"), ("candle", "cylinder"), ("jar", "cylinder"), ("can", "cylinder")]


def guess_kind(name, category, shape):
    if shape:
        return {"cylinder": "cylinder", "sphere": "ball"}.get(shape, "box") if shape in ("box", "cylinder", "sphere") else "box"
    text = f"{name} {category}".lower()
    for word, kind in KEYWORDS:
        if re.search(r"\b" + word + r"s?\b", text):
            return kind
    return "box"


def clean_product(raw, idx, unit_scale):
    if not isinstance(raw, dict):
        raise InputError(f"product {idx + 1}: must be an object")
    name = str(raw.get("name") or "").strip()
    if not name:
        raise InputError(f"product {idx + 1}: name is required")
    where = f"product {name!r}"
    color = _color(raw.get("color"), idx)
    category = str(raw.get("category") or "")[:60]
    parts_in = raw.get("parts")
    if parts_in:
        if not isinstance(parts_in, list):
            raise InputError(f"{where}: parts must be a list")
        parts = [clean_part(p, idx, k) for k, p in enumerate(parts_in)]
        if unit_scale != 1.0:
            for p in parts:
                p["size"] = [_r(s * unit_scale) for s in p["size"]]
                p["pos"] = [_r(s * unit_scale) for s in p["pos"]]
        source = "parts"
    else:
        dims = [raw.get(k) for k in ("width", "depth", "height")]
        if any(v in (None, "") for v in dims):
            raise InputError(f"{where}: give width, depth and height, or a parts list")
        w, d, h = (_pos(v, f"{where} {k}") * unit_scale for v, k in zip(dims, ("width", "depth", "height")))
        shape = str(raw.get("shape") or "").lower()
        if shape and shape not in ("box", "cylinder", "sphere"):
            raise InputError(f"{where}: shape must be box, cylinder or sphere (use parts for others), got {shape!r}")
        kind = guess_kind(name, category, shape)
        parts = [clean_part(p, idx, k) for k, p in enumerate(preset(kind, w, d, h, color))]
        source = f"preset:{kind}"
    lo, hi = parts_bounds(parts)
    # drop onto the floor and centre on x/z so layout is predictable
    off = [-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2]
    for p in parts:
        p["pos"] = [_r(p["pos"][i] + off[i]) for i in range(3)]
    lo, hi = parts_bounds(parts)
    item = {"id": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or f"item-{idx + 1}", "name": name[:120], "category": category,
            "source": source, "parts": parts, "dims_cm": [_r(hi[i] - lo[i]) for i in range(3)],
            "bounds": {"min": [_r(v) for v in lo], "max": [_r(v) for v in hi]}}
    if raw.get("price") not in (None, ""):
        item["price"] = str(raw["price"])[:30]
    url = str(raw.get("url") or "").strip()
    if url:
        if not re.match(r"^https?://", url, re.I):
            raise InputError(f"{where}: url must start with http:// or https://")
        item["url"] = url[:300]
    return item


def parse_products(text, fmt=None):
    text = text.lstrip("﻿")
    fmt = fmt or ("json" if text.lstrip()[:1] in "[{" else "csv")
    if fmt == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise InputError(f"invalid JSON: {e}")
        if isinstance(data, dict):
            data = data.get("products")
        if not isinstance(data, list):
            raise InputError("JSON must be a list of products or {\"products\": [...]}")
        return data
    rows = list(csv.DictReader(io.StringIO(text)))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in rows]


def layout(items, gap=None, cols=None):
    """Row-major grid; cell = largest footprint + gap. Sets item['position'] = [x, 0, z] (centre of the item footprint)."""
    n = len(items)
    if not n:
        return
    cell_x = max(i["dims_cm"][0] for i in items)
    cell_z = max(i["dims_cm"][2] for i in items)
    g = gap if gap is not None else 0.25 * max(cell_x, cell_z)
    cols = cols or math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    sx, sz = cell_x + g, cell_z + g
    for k, it in enumerate(items):
        c, r = k % cols, k // cols
        it["position"] = [_r((c - (cols - 1) / 2) * sx), 0, _r((r - (rows - 1) / 2) * sz)]


def build_scene(text, fmt=None, unit="cm", title="Constructs", gap=None, cols=None):
    if unit not in UNITS:
        raise InputError(f"unit must be one of {sorted(UNITS)}")
    raw = parse_products(text, fmt)
    if not raw:
        raise InputError("no products in input")
    if len(raw) > 500:
        raise InputError("at most 500 products per scene")
    scale = UNITS[unit]
    items, seen = [], {}
    for i, r in enumerate(raw):
        it = clean_product(r, i, scale)
        seen[it["id"]] = seen.get(it["id"], 0) + 1
        if seen[it["id"]] > 1:
            it["id"] += f"-{seen[it['id']]}"
        items.append(it)
    layout(items, gap, cols)
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for it in items:
        for i in range(3):
            lo[i] = min(lo[i], it["position"][i] + it["bounds"]["min"][i])
            hi[i] = max(hi[i], it["position"][i] + it["bounds"]["max"][i])
    return {"schema": "construct3d/1", "title": str(title)[:100], "unit": "cm", "items": items,
            "stats": {"items": len(items), "parts": sum(len(i["parts"]) for i in items),
                      "world_min": [_r(v) for v in lo], "world_max": [_r(v) for v in hi]}}
