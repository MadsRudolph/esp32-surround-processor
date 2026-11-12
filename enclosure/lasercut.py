"""Cut file for the acrylic lid. Run: python3 enclosure/lasercut.py (design.py also calls it)

Writes lasercut/Lid_Plate_4mm_acrylic.dxf and .svg, 1:1 in millimetres, seen
from above (outside face up, front of the box to the right, rear to the left).

Layers and colours, the same in both files:
  CUT           red    through cuts: outline, screw holes, button hole, pin holes, vent slots
  ENGRAVE       blue   labels and the product name, single-line strokes
  LED_OPTIONAL  green  two holes over the LEDs. ONLY for an opaque plate; delete or switch off for clear acrylic

Cut lines are compensated for design.LASER_KERF: holes and slots are drawn
smaller and the outline larger by half the kerf per side.
"""
import math
from pathlib import Path
ROOT = Path(__file__).resolve().parent
NAME = 'Lid_Plate_4mm_acrylic'
LAYERS = {'CUT': (1, '#ff0000'), 'ENGRAVE': (5, '#0000ff'), 'LED_OPTIONAL': (3, '#00ff00')}

# Single-stroke capitals on a 4 x 6 grid; each glyph is a list of polylines.
GLYPHS = {
    'A': [[(0, 0), (0, 4), (2, 6), (4, 4), (4, 0)], [(0, 2.5), (4, 2.5)]],
    'B': [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    'D': [[(0, 0), (0, 6), (2.5, 6), (4, 4.5), (4, 1.5), (2.5, 0), (0, 0)]],
    'E': [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    'N': [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    'O': [[(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]],
    'R': [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(2, 3), (4, 0)]],
    'S': [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5)]],
    'T': [[(0, 6), (4, 6)], [(2, 6), (2, 0)]],
    'U': [[(0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)]],
    '0': [[(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]],
    '4': [[(3, 0), (3, 6), (0, 2), (4, 2)]],
    '.': [[(1.7, 0), (2.3, 0), (2.3, .6), (1.7, .6), (1.7, 0)]],
    ' ': [],
}
ADVANCE = 5.6

def text_lines(text, x_top, y_mid, h):
    """Strokes for text read from the front of the box: it runs toward +Y and its
    letters stand toward -X. x_top is the X of the letter tops."""
    k = h / 6
    width = (len(text) * ADVANCE - (ADVANCE - 4)) * k
    out = []
    for i, ch in enumerate(text):
        for poly in GLYPHS[ch]:
            pts = [(x_top + (6 - v) * k, y_mid - width / 2 + (i * ADVANCE + u) * k) for u, v in poly]
            out += [('line', *a, *b) for a, b in zip(pts, pts[1:])]
    return out

def entities(m):
    """{layer: [('line', x1, y1, x2, y2) | ('circle', x, y, r) | ('arc', cx, cy, r, a0, a1 in degrees, CCW)]}"""
    c = m.LASER_KERF / 2
    out = {k: [] for k in LAYERS}
    x0, y0, x1, y1, r = m.plate_outline()
    x0, y0, x1, y1, r = x0 - c, y0 - c, x1 + c, y1 + c, r + c
    out['CUT'] += [('line', x0 + r, y0, x1 - r, y0), ('line', x1, y0 + r, x1, y1 - r),
                   ('line', x1 - r, y1, x0 + r, y1), ('line', x0, y1 - r, x0, y0 + r),
                   ('arc', x0 + r, y0 + r, r, 180, 270), ('arc', x1 - r, y0 + r, r, 270, 360),
                   ('arc', x1 - r, y1 - r, r, 0, 90), ('arc', x0 + r, y1 - r, r, 90, 180)]
    for layer, kind, *a in m.plate_openings():
        key = {'cut': 'CUT', 'led_optional': 'LED_OPTIONAL'}[layer]
        if kind == 'circle':
            out[key].append(('circle', a[0], a[1], a[2] / 2 - c))
        else:
            x, ya, yb, w = a
            rr = w / 2 - c
            ya, yb = ya + w / 2, yb - w / 2          # arc centres
            out[key] += [('line', x - rr, ya, x - rr, yb), ('line', x + rr, yb, x + rr, ya),
                         ('arc', x, yb, rr, 0, 180), ('arc', x, ya, rr, 180, 360)]
    for text, x_top, y_mid, h in m.plate_labels():
        out['ENGRAVE'] += text_lines(text, x_top, y_mid, h)
    return out

def dxf(ents):
    o = ['0', 'SECTION', '2', 'HEADER', '9', '$INSUNITS', '70', '4', '9', '$MEASUREMENT', '70', '1', '0', 'ENDSEC',
         '0', 'SECTION', '2', 'TABLES', '0', 'TABLE', '2', 'LAYER', '70', str(len(LAYERS))]
    for name, (aci, _) in LAYERS.items():
        o += ['0', 'LAYER', '2', name, '70', '0', '62', str(aci), '6', 'CONTINUOUS']
    o += ['0', 'ENDTAB', '0', 'ENDSEC', '0', 'SECTION', '2', 'ENTITIES']
    f = lambda v: f'{v:.4f}'
    for layer, rows in ents.items():
        for e in rows:
            if e[0] == 'line':
                o += ['0', 'LINE', '8', layer, '10', f(e[1]), '20', f(e[2]), '11', f(e[3]), '21', f(e[4])]
            elif e[0] == 'circle':
                o += ['0', 'CIRCLE', '8', layer, '10', f(e[1]), '20', f(e[2]), '40', f(e[3])]
            else:
                o += ['0', 'ARC', '8', layer, '10', f(e[1]), '20', f(e[2]), '40', f(e[3]), '50', f(e[4]), '51', f(e[5])]
    o += ['0', 'ENDSEC', '0', 'EOF']
    return '\n'.join(o) + '\n'

def svg(ents, bounds):
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    X = lambda x: f'{x - x0:.3f}'
    Y = lambda y: f'{y1 - y:.3f}'                      # SVG Y runs down
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
         f'width="{w:.3f}mm" height="{h:.3f}mm" viewBox="0 0 {w:.3f} {h:.3f}">']
    for layer, rows in ents.items():
        o.append(f'<g id="{layer}" inkscape:groupmode="layer" inkscape:label="{layer}" fill="none" '
                 f'stroke="{LAYERS[layer][1]}" stroke-width="0.05" stroke-linecap="round">')
        for e in rows:
            if e[0] == 'line':
                o.append(f'<line x1="{X(e[1])}" y1="{Y(e[2])}" x2="{X(e[3])}" y2="{Y(e[4])}"/>')
            elif e[0] == 'circle':
                o.append(f'<circle cx="{X(e[1])}" cy="{Y(e[2])}" r="{e[3]:.3f}"/>')
            else:
                _, cx, cy, r, a0, a1 = e
                p = lambda a: (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
                (sx, sy), (ex, ey) = p(a0), p(a1)
                o.append(f'<path d="M {X(sx)} {Y(sy)} A {r:.3f} {r:.3f} 0 {1 if a1 - a0 > 180 else 0} 0 {X(ex)} {Y(ey)}"/>')
        o.append('</g>')
    o.append('</svg>')
    return '\n'.join(o) + '\n'

def export(m):
    out = ROOT / 'lasercut'; out.mkdir(exist_ok=True)
    ents = entities(m)
    x0, y0, x1, y1, _ = m.plate_outline()
    pad = m.LASER_KERF / 2 + 1.0
    (out / f'{NAME}.dxf').write_text(dxf(ents))
    (out / f'{NAME}.svg').write_text(svg(ents, (x0 - pad, y0 - pad, x1 + pad, y1 + pad)))
    return {'files': [f'lasercut/{NAME}.dxf', f'lasercut/{NAME}.svg'], 'plate_mm': [round(x1 - x0, 2), round(y1 - y0, 2), m.PLATE_T],
            'kerf_compensated_mm': m.LASER_KERF, 'entities': {k: len(v) for k, v in ents.items()}}

if __name__ == '__main__':
    import design
    print(export(design))
