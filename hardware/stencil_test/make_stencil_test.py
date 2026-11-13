#!/usr/bin/env python3
"""Laser-cut solder stencil TEST coupon: ESP32-WROOM-32 paste apertures plus
calibration features (holes, slots, fine-pitch combs, chip pads, scale check).

Writes stencil_test.dxf (R12 ASCII, mm) and stencil_test.svg (mm) next to this
script, then reads the DXF back and checks it. Standard library only.

    python3 hardware/stencil_test/make_stencil_test.py

Coordinates are millimetres, origin at the bottom-left corner of the coupon,
y pointing up (the SVG flips y on output).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- parameters
COUPON_W, COUPON_H = 22.0, 22.0
OUTLINE_RADIUS = 1.5      # corner radius of the cut-out outline
SHRINK = 0.05             # paste aperture shrink per side vs the copper pad (mm)
CORNER_R = 0.1            # corner radius on rectangular apertures (mm)
ARC_SEGS = 3              # straight segments per rounded corner
TEXT_H = 1.5              # label height (mm)
LABEL_CLEARANCE = 0.5     # minimum label-to-aperture distance (asserted)

# ESP32-WROOM-32 pads, from lib/Surround.pretty/ESP32-WROOM-32_NoVias.kicad_mod
# (footprint U1 on hardware/surround.kicad_pcb), read with pcbnew.
# Footprint coordinates: x right, y DOWN, as seen from the module side.
# Pin 1 top left, antenna end towards negative y (top).
# (pin, x, y, w, h) copper pad size in mm.
ESP32_PADS = (
    [(n, -8.75, y, 1.5, 0.9) for n, y in zip(range(1, 15), (
        -8.25, -6.98, -5.71, -4.44, -3.17, -1.9, -0.63,
        0.64, 1.91, 3.18, 4.45, 5.72, 6.99, 8.26))]
    + [(n, x, 9.51, 0.9, 1.5) for n, x in zip(range(15, 25), (
        -5.71, -4.44, -3.17, -1.9, -0.63, 0.64, 1.91, 3.18, 4.45, 5.72))]
    + [(n, 8.75, y, 1.5, 0.9) for n, y in zip(range(25, 39), (
        8.26, 6.99, 5.72, 4.45, 3.18, 1.91, 0.64,
        -0.63, -1.9, -3.17, -4.44, -5.71, -6.98, -8.25))]
)
# Centre ground pad 39: 4.2 x 4.2 at (-0.68, -0.91). Paste as a 3 x 3
# window pane, using the footprint's own 1.05 mm sub-pads at 1.525 mm pitch.
EP_CENTRE = (-0.68, -0.91)
EP_PANE, EP_PITCH = 1.05, 1.525

ESP32_ORIGIN = (11.0, 11.75)   # where the footprint origin sits on the coupon

HOLES = [0.3, 0.4, 0.5, 0.6, 0.8, 1.0]                      # diameters
HOLE_STEP = 2.2
SLOTS = [0.15, 0.20, 0.25, 0.30, 0.40, 0.50]                 # widths, 3 mm long
SLOT_STEP = 2.2
SLOT_LEN = 3.0
COMBS = [(0.5, 0.25), (0.65, 0.35)]                          # (pitch, width)
COMB_N, COMB_LEN = 8, 1.5
# Chip pads: KiCad R_xxxx_Metric land pads (IPC-7351 nominal density):
# (name, pad length along part, pad width, centre-to-centre spacing)
CHIPS = [("0402", 0.59, 0.64, 0.97),
         ("0603", 0.80, 0.95, 1.65),
         ("0805", 1.025, 1.40, 1.825),
         ("1206", 1.125, 1.75, 2.925)]
SCALE_SQUARE = 10.0
LINE_PAIR = 20.0                 # centre-to-centre spacing of the two marks
LINE_W, LINE_LEN = 0.3, 3.0

RIGHT_X0, RIGHT_X1 = 28.5, 58.0  # extent of the calibration rows

# ---------------------------------------------------------------- geometry
apertures = []   # dicts: kind 'rect' (cx, cy, w, h) or 'circle' (cx, cy, r), group
labels = []      # list of open polylines [(x, y), ...]


def rect(cx, cy, w, h, group):
    apertures.append(dict(kind="rect", cx=cx, cy=cy, w=w, h=h, group=group))


def circle(cx, cy, d, group):
    apertures.append(dict(kind="circle", cx=cx, cy=cy, r=d / 2, group=group))


def rounded_rect_pts(cx, cy, w, h, r, segs=ARC_SEGS):
    r = min(r, 0.4 * min(w, h))
    pts = []
    corners = [(cx + w / 2 - r, cy - h / 2 + r, -90),   # bottom right
               (cx + w / 2 - r, cy + h / 2 - r, 0),     # top right
               (cx - w / 2 + r, cy + h / 2 - r, 90),    # top left
               (cx - w / 2 + r, cy - h / 2 + r, 180)]   # bottom left
    for (ox, oy, a0) in corners:
        if r <= 0:
            pts.append((ox, oy))
            continue
        for i in range(segs + 1):
            a = math.radians(a0 + 90 * i / segs)
            pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return pts


# --- single-stroke font. Glyph cell 1 wide x 2 tall; (advance, strokes).
FONT = {
    "0": (1, [[(0, 0), (1, 0), (1, 2), (0, 2), (0, 0)], [(0, 0), (1, 2)]]),
    "1": (1, [[(0.2, 1.7), (0.5, 2), (0.5, 0)], [(0.2, 0), (0.8, 0)]]),
    "2": (1, [[(0, 2), (1, 2), (1, 1), (0, 1), (0, 0), (1, 0)]]),
    "3": (1, [[(0, 2), (1, 2), (1, 0), (0, 0)], [(0.2, 1), (1, 1)]]),
    "4": (1, [[(0, 2), (0, 1), (1, 1)], [(1, 2), (1, 0)]]),
    "5": (1, [[(1, 2), (0, 2), (0, 1), (1, 1), (1, 0), (0, 0)]]),
    "6": (1, [[(1, 2), (0, 2), (0, 0), (1, 0), (1, 1), (0, 1)]]),
    "7": (1, [[(0, 2), (1, 2), (1, 0)]]),
    "8": (1, [[(0, 0), (1, 0), (1, 2), (0, 2), (0, 0)], [(0, 1), (1, 1)]]),
    "9": (1, [[(0, 0), (1, 0), (1, 2), (0, 2), (0, 1), (1, 1)]]),
    ".": (0.4, [[(0.1, 0), (0.3, 0), (0.3, 0.2), (0.1, 0.2), (0.1, 0)]]),
    "A": (1, [[(0, 0), (0, 1.4), (0.5, 2), (1, 1.4), (1, 0)], [(0, 1), (1, 1)]]),
    "D": (1, [[(0, 0), (0, 2), (0.6, 2), (1, 1.6), (1, 0.4), (0.6, 0), (0, 0)]]),
    "E": (1, [[(1, 2), (0, 2), (0, 0), (1, 0)], [(0, 1), (0.7, 1)]]),
    "N": (1, [[(0, 0), (0, 2), (1, 0), (1, 2)]]),
    "P": (1, [[(0, 0), (0, 2), (1, 2), (1, 1), (0, 1)]]),
    "S": (1, [[(1, 2), (0, 2), (0, 1), (1, 1), (1, 0), (0, 0)]]),
    "T": (1, [[(0, 2), (1, 2)], [(0.5, 2), (0.5, 0)]]),
    "W": (1, [[(0, 2), (0.2, 0), (0.5, 1), (0.8, 0), (1, 2)]]),
    "^": (1, [[(0, 1.3), (0.5, 2), (1, 1.3)], [(0.5, 2), (0.5, 0)]]),
    " ": (0.6, []),
}
GAP = 0.45   # glyph spacing, in cell units


def text_width(s, h=TEXT_H):
    k = h / 2
    return (sum(FONT[c][0] for c in s) + GAP * (len(s) - 1)) * k


def text(s, x, y, h=TEXT_H, align="center"):
    """Engrave string s with its baseline at y; x is centre or left edge."""
    k = h / 2
    if align == "center":
        x -= text_width(s, h) / 2
    for c in s:
        adv, strokes = FONT[c]
        for st in strokes:
            labels.append([(x + px * k, y + py * k) for px, py in st])
        x += (adv + GAP) * k


# --- Compact coupon: the ESP32-WROOM-32 pads, with the test features inside the
# empty middle of the footprint. No labels: see README.md for what is where.
# (footprint y-down -> coupon y-up)
ox, oy = ESP32_ORIGIN
for (_, x, y, w, h) in ESP32_PADS:
    rect(ox + x, oy - y, w - 2 * SHRINK, h - 2 * SHRINK, "esp32")
for i in (-1, 0, 1):
    for j in (-1, 0, 1):
        rect(ox + EP_CENTRE[0] + i * EP_PITCH, oy - (EP_CENTRE[1] + j * EP_PITCH),
             EP_PANE - 2 * SHRINK, EP_PANE - 2 * SHRINK, "esp32")

# round holes, a row near the antenna end, smallest at the pin 1 side
for k, d in enumerate(HOLES):
    circle(ox + (k - (len(HOLES) - 1) / 2) * HOLE_STEP, oy + 7.0, d, "holes")

# two fine-pitch combs under the holes: 0.5 mm pitch (pin 1 side) and 0.65 mm pitch
for cx, (pitch, w) in zip((-3.6, 3.6), COMBS):
    for k in range(COMB_N):
        rect(ox + cx + (k - (COMB_N - 1) / 2) * pitch, oy + 4.8, w, COMB_LEN, "combs")

# slots, a row between the centre pad and the bottom pads, narrowest at the pin 1 side
for k, w in enumerate(SLOTS):
    rect(ox + (k - (len(SLOTS) - 1) / 2) * SLOT_STEP, oy - 4.9, w, SLOT_LEN, "slots")


def shape_dist(a, b):
    """Edge-to-edge distance between two apertures (corner rounding ignored,
    so this is the conservative, slightly smaller figure)."""
    if a["kind"] == "circle" and b["kind"] == "circle":
        return math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"]) - a["r"] - b["r"]
    if a["kind"] == "circle":
        a, b = b, a
    dx = max(0.0, abs(a["cx"] - b["cx"]) - a["w"] / 2 - (b["w"] / 2 if b["kind"] == "rect" else 0))
    dy = max(0.0, abs(a["cy"] - b["cy"]) - a["h"] / 2 - (b["h"] / 2 if b["kind"] == "rect" else 0))
    d = math.hypot(dx, dy)
    return d - b["r"] if b["kind"] == "circle" else d


def point_dist(p, a):
    if a["kind"] == "circle":
        return math.hypot(p[0] - a["cx"], p[1] - a["cy"]) - a["r"]
    dx = max(0.0, abs(p[0] - a["cx"]) - a["w"] / 2)
    dy = max(0.0, abs(p[1] - a["cy"]) - a["h"] / 2)
    inside = abs(p[0] - a["cx"]) < a["w"] / 2 and abs(p[1] - a["cy"]) < a["h"] / 2
    return -1.0 if inside else math.hypot(dx, dy)


def bbox(a):
    if a["kind"] == "circle":
        return a["cx"] - a["r"], a["cy"] - a["r"], a["cx"] + a["r"], a["cy"] + a["r"]
    return a["cx"] - a["w"] / 2, a["cy"] - a["h"] / 2, a["cx"] + a["w"] / 2, a["cy"] + a["h"] / 2


def model_checks():
    webs = {}
    for i, a in enumerate(apertures):
        for b in apertures[i + 1:]:
            d = shape_dist(a, b)
            assert d > 0.1, f"apertures overlap or touch: {a} {b}"
            key = a["group"] if a["group"] == b["group"] else "between groups"
            webs[key] = min(webs.get(key, 99), d)
    # aperture to coupon edge
    edge = min(min(x0, y0, COUPON_W - x1, COUPON_H - y1)
               for x0, y0, x1, y1 in map(bbox, apertures))
    assert edge > 1.5, f"aperture too close to the outline: {edge}"
    # labels: inside the coupon and clear of every aperture
    lab_min = 99
    for st in labels:
        for (x0, y0), (x1, y1) in zip(st, st[1:]):
            n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 0.05))
            for t in range(n + 1):
                p = (x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n)
                assert 0.8 < p[0] < COUPON_W - 0.8 and 0.8 < p[1] < COUPON_H - 0.8, p
                lab_min = min(lab_min, min(point_dist(p, a) for a in apertures))
    assert lab_min >= LABEL_CLEARANCE, f"label {lab_min:.2f} mm from an aperture"
    return webs, edge, lab_min


# ---------------------------------------------------------------- writers
LAYERS = [("CUT_APERTURES", 1), ("ENGRAVE_LABELS", 5), ("CUT_OUTLINE", 3)]
SVG_COL = {"CUT_APERTURES": "#ff0000", "ENGRAVE_LABELS": "#0000ff", "CUT_OUTLINE": "#00ff00"}


def outline_pts():
    return rounded_rect_pts(COUPON_W / 2, COUPON_H / 2, COUPON_W, COUPON_H,
                            OUTLINE_RADIUS, segs=8)


def aperture_pts(a):
    return rounded_rect_pts(a["cx"], a["cy"], a["w"], a["h"], CORNER_R)


def f(v):
    return f"{v:.4f}"


def write_dxf(path):
    o = []

    def g(code, val):
        o.append(f"{code}\n{val}")
    g(0, "SECTION"); g(2, "HEADER")
    g(9, "$ACADVER"); g(1, "AC1009")
    g(9, "$INSUNITS"); g(70, 4)
    g(9, "$MEASUREMENT"); g(70, 1)
    g(9, "$EXTMIN"); g(10, f(0)); g(20, f(0)); g(30, f(0))
    g(9, "$EXTMAX"); g(10, f(COUPON_W)); g(20, f(COUPON_H)); g(30, f(0))
    g(0, "ENDSEC")
    g(0, "SECTION"); g(2, "TABLES")
    g(0, "TABLE"); g(2, "LTYPE"); g(70, 1)
    g(0, "LTYPE"); g(2, "CONTINUOUS"); g(70, 0); g(3, "Solid line"); g(72, 65); g(73, 0); g(40, f(0))
    g(0, "ENDTAB")
    g(0, "TABLE"); g(2, "LAYER"); g(70, len(LAYERS))
    for name, col in LAYERS:
        g(0, "LAYER"); g(2, name); g(70, 0); g(62, col); g(6, "CONTINUOUS")
    g(0, "ENDTAB")
    g(0, "ENDSEC")
    g(0, "SECTION"); g(2, "ENTITIES")

    def poly(layer, pts, closed):
        g(0, "POLYLINE"); g(8, layer); g(66, 1); g(10, f(0)); g(20, f(0)); g(30, f(0))
        g(70, 1 if closed else 0)
        for x, y in pts:
            g(0, "VERTEX"); g(8, layer); g(10, f(x)); g(20, f(y)); g(30, f(0))
        g(0, "SEQEND"); g(8, layer)

    for a in apertures:
        if a["kind"] == "circle":
            g(0, "CIRCLE"); g(8, "CUT_APERTURES")
            g(10, f(a["cx"])); g(20, f(a["cy"])); g(30, f(0)); g(40, f(a["r"]))
        else:
            poly("CUT_APERTURES", aperture_pts(a), True)
    for st in labels:
        poly("ENGRAVE_LABELS", st, False)
    poly("CUT_OUTLINE", outline_pts(), True)   # last, so it is cut last
    g(0, "ENDSEC"); g(0, "EOF")
    with open(path, "w", newline="\r\n") as fh:
        fh.write("\n".join(o) + "\n")


def write_svg(path):
    def sp(pts):
        return " ".join(f"{x:.4f},{COUPON_H - y:.4f}" for x, y in pts)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{COUPON_W:g}mm" '
         f'height="{COUPON_H:g}mm" viewBox="0 0 {COUPON_W:g} {COUPON_H:g}">']
    common = 'fill="none" stroke-width="0.05" stroke-linejoin="round" stroke-linecap="round"'
    o.append(f'<g id="CUT_APERTURES" stroke="{SVG_COL["CUT_APERTURES"]}" {common}>')
    for a in apertures:
        if a["kind"] == "circle":
            o.append(f'<circle cx="{a["cx"]:.4f}" cy="{COUPON_H - a["cy"]:.4f}" r="{a["r"]:.4f}"/>')
        else:
            o.append(f'<polygon points="{sp(aperture_pts(a))}"/>')
    o.append("</g>")
    o.append(f'<g id="ENGRAVE_LABELS" stroke="{SVG_COL["ENGRAVE_LABELS"]}" {common}>')
    for st in labels:
        o.append(f'<polyline points="{sp(st)}"/>')
    o.append("</g>")
    o.append(f'<g id="CUT_OUTLINE" stroke="{SVG_COL["CUT_OUTLINE"]}" {common}>')
    o.append(f'<polygon points="{sp(outline_pts())}"/>')
    o.append("</g>")
    o.append("</svg>")
    with open(path, "w") as fh:
        fh.write("\n".join(o) + "\n")


# ---------------------------------------------------------------- DXF read-back
def read_dxf(path):
    lines = open(path).read().splitlines()
    pairs = [(int(lines[i].strip()), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
    header, ents, in_ents, cur, i = {}, [], False, None, 0
    while i < len(pairs):
        c, v = pairs[i]
        if c == 9:
            header[v] = pairs[i + 1][1]
        if c == 0 and v == "SECTION" and pairs[i + 1] == (2, "ENTITIES"):
            in_ents = True
        elif in_ents and c == 0:
            if v in ("POLYLINE", "CIRCLE", "LINE", "LWPOLYLINE", "TEXT", "MTEXT",
                     "INSERT", "SPLINE", "HATCH", "ARC"):
                cur = {"type": v, "pts": [], "flag": 0}
                ents.append(cur)
            elif v == "VERTEX":
                cur["pts"].append([None, None])
            elif v == "ENDSEC":
                in_ents = False
        elif in_ents and cur is not None:
            if c == 8 and "layer" not in cur:
                cur["layer"] = v
            elif c == 70 and not cur["pts"]:
                cur["flag"] = int(v)
            elif c == 10 and cur["pts"]:
                cur["pts"][-1][0] = float(v)
            elif c == 20 and cur["pts"]:
                cur["pts"][-1][1] = float(v)
            elif c == 10:
                cur["cx"] = float(v)
            elif c == 20:
                cur["cy"] = float(v)
            elif c == 40:
                cur["r"] = float(v)
        i += 1
    return header, ents


def dxf_checks(path):
    header, ents = read_dxf(path)
    assert header.get("$INSUNITS") == "4" and header.get("$MEASUREMENT") == "1", header
    types = {e["type"] for e in ents}
    assert types <= {"POLYLINE", "CIRCLE"}, f"unexpected entity types {types}"
    by = {}
    for e in ents:
        by.setdefault((e["layer"], e["type"]), []).append(e)
    n_circ = sum(a["kind"] == "circle" for a in apertures)
    n_rect = len(apertures) - n_circ
    assert len(by.get(("CUT_APERTURES", "CIRCLE"), [])) == n_circ
    assert len(by.get(("CUT_APERTURES", "POLYLINE"), [])) == n_rect
    assert len(by.get(("ENGRAVE_LABELS", "POLYLINE"), [])) == len(labels)
    assert len(by.get(("CUT_OUTLINE", "POLYLINE"), [])) == 1
    for (layer, t), es in by.items():
        if layer.startswith("CUT") and t == "POLYLINE":
            assert all(e["flag"] & 1 for e in es), f"open cut polyline on {layer}"
        if layer == "ENGRAVE_LABELS":
            assert all(not e["flag"] & 1 for e in es)
    xs, ys = [], []
    for e in ents:
        if e["type"] == "CIRCLE":
            xs += [e["cx"] - e["r"], e["cx"] + e["r"]]; ys += [e["cy"] - e["r"], e["cy"] + e["r"]]
        else:
            xs += [p[0] for p in e["pts"]]; ys += [p[1] for p in e["pts"]]
    bb = (min(xs), min(ys), max(xs), max(ys))
    assert all(abs(u - v) < 1e-3 for u, v in zip(bb, (0, 0, COUPON_W, COUPON_H))), bb
    # no duplicated cut shapes
    sig = [tuple(round(c, 3) for p in e["pts"] for c in p) if e["type"] == "POLYLINE"
           else (round(e["cx"], 3), round(e["cy"], 3), round(e["r"], 3))
           for e in ents if e["layer"].startswith("CUT")]
    assert len(sig) == len(set(sig)), "duplicate cut shape"
    return by, bb


def main():
    webs, edge, lab_min = model_checks()
    dxf = os.path.join(HERE, "stencil_test.dxf")
    svg = os.path.join(HERE, "stencil_test.svg")
    write_dxf(dxf)
    write_svg(svg)
    by, bb = dxf_checks(dxf)
    print(f"wrote {dxf}\nwrote {svg}")
    for (layer, t), es in sorted(by.items()):
        print(f"  {layer:15s} {t:9s} {len(es):4d}")
    print(f"  bounding box {bb[2] - bb[0]:.2f} x {bb[3] - bb[1]:.2f} mm")
    print("smallest web (edge to edge between neighbouring apertures, mm):")
    for k, v in sorted(webs.items(), key=lambda kv: kv[1]):
        print(f"  {k:15s} {v:.3f}")
    print(f"smallest aperture to outline: {edge:.2f} mm, label to aperture: {lab_min:.2f} mm")
    print("all checks passed")


if __name__ == "__main__":
    sys.exit(main())
