"""Cut file for the acrylic lid.

Dependency: ezdxf (https://pypi.org/project/ezdxf/), plus FreeCAD for design.py.
Run from the repository root:

    uv run --no-project --python /usr/bin/python3 --with ezdxf python3 enclosure/lasercut.py

design.py also calls export(). If ezdxf is not installed in the Python that runs
design.py, export() re-runs this file through the uv command above.

Writes, 1:1 in millimetres, seen from above (outside face up, front of the box
to the right, rear to the left):
  lasercut/Lid_Plate_4mm_acrylic.dxf        DXF, AutoCAD 2018 (AC1032). Open this one first.
  lasercut/Lid_Plate_4mm_acrylic_R2000.dxf  the same drawing as AutoCAD 2000 (AC1015), a fallback
  lasercut/Lid_Plate_4mm_acrylic.svg        the same drawing as SVG

Layers and colours, the same in all three files:
  CUT                                red    through cuts: outline, screw holes, button hole, pin holes, vent slots
  ENGRAVE                            blue   labels and the product name, single-line strokes
  LED_OPTIONAL_NOT_FOR_CLEAR_ACRYLIC green  two holes over the LEDs. ONLY for an opaque plate; delete or switch off

DXF entities are kept to what Illustrator imports reliably: closed LWPOLYLINE
with bulge arcs for the outline and the slots, CIRCLE for round holes, and
LWPOLYLINE for the engraving strokes. No splines, hatches, blocks or text.

Cut lines are compensated for design.LASER_KERF: holes and slots are drawn
smaller and the outline larger by half the kerf per side.
"""
import json, math, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
NAME = 'Lid_Plate_4mm_acrylic'
LED_LAYER = 'LED_OPTIONAL_NOT_FOR_CLEAR_ACRYLIC'
LAYERS = {'CUT': (1, '#ff0000'), 'ENGRAVE': (5, '#0000ff'), LED_LAYER: (3, '#00ff00')}   # name: (ACI colour, SVG colour)
HAIRLINE = 0.0254        # mm, = 0.072 pt = 0.001 in: the usual "hairline" a laser driver reads as a vector cut
UV_CMD = ['uv', 'run', '--no-project', '--python', sys.executable, '--with', 'ezdxf', 'python3']

# Single-stroke capitals on a 4 x 6 grid; each glyph is a list of polylines.
GLYPHS = {
    'A': [[(0, 0), (0, 4), (2, 6), (4, 4), (4, 0)], [(0, 2.5), (4, 2.5)]],
    'B': [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    'D': [[(0, 0), (0, 6), (2.5, 6), (4, 4.5), (4, 1.5), (2.5, 0), (0, 0)]],
    'E': [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    'F': [[(0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    'L': [[(0, 6), (0, 0), (4, 0)]],
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

def text_strokes(text, x_top, y_mid, h):
    """Stroke polylines for text read from the front of the box: it runs toward +Y
    and its letters stand toward -X. x_top is the X of the letter tops."""
    k = h / 6
    width = (len(text) * ADVANCE - (ADVANCE - 4)) * k
    out = []
    for i, ch in enumerate(text):
        for poly in GLYPHS[ch]:
            out.append([(x_top + (6 - v) * k, y_mid - width / 2 + (i * ADVANCE + u) * k) for u, v in poly])
    return out

def shapes(m):
    """{layer: [('rrect', x0, y0, x1, y1, r) | ('slot', x, ya, yb, r) | ('circle', x, y, r) | ('stroke', [(x, y), ...])]}
    in model coordinates, kerf compensation applied. A slot runs along Y; ya and yb are its arc centres."""
    c = m.LASER_KERF / 2
    out = {k: [] for k in LAYERS}
    x0, y0, x1, y1, r = m.plate_outline()
    out['CUT'].append(('rrect', x0 - c, y0 - c, x1 + c, y1 + c, r + c))
    for layer, kind, *a in m.plate_openings():
        key = {'cut': 'CUT', 'led_optional': LED_LAYER}[layer]
        if kind == 'circle':
            out[key].append(('circle', a[0], a[1], a[2] / 2 - c))
        else:
            x, ya, yb, w = a
            out[key].append(('slot', x, ya + w / 2, yb - w / 2, w / 2 - c))
    for text, x_top, y_mid, h in m.plate_labels():
        out['ENGRAVE'] += [('stroke', p) for p in text_strokes(text, x_top, y_mid, h)]
    return out

# ----------------------------------------------------------------------- DXF
QUARTER = math.tan(math.radians(90) / 4)     # bulge of a 90 degree CCW arc

def lw_points(s):
    """(points with bulge as (x, y, 0, 0, bulge), closed) for an rrect or a slot, counter-clockwise."""
    if s[0] == 'rrect':
        _, x0, y0, x1, y1, r = s
        q = QUARTER
        pts = [(x0 + r, y0, 0), (x1 - r, y0, q), (x1, y0 + r, 0), (x1, y1 - r, q),
               (x1 - r, y1, 0), (x0 + r, y1, q), (x0, y1 - r, 0), (x0, y0 + r, q)]
    else:
        _, x, ya, yb, r = s
        pts = [(x + r, ya, 0), (x + r, yb, 1), (x - r, yb, 0), (x - r, ya, 1)]   # bulge 1 = semicircle
    return [(px, py, 0, 0, b) for px, py, b in pts], True

def write_dxf(sh, path, version):
    import ezdxf
    from ezdxf import bbox, units, zoom
    doc = ezdxf.new(version, setup=False)
    doc.units = units.MM                       # $INSUNITS = 4
    doc.header['$MEASUREMENT'] = 1             # metric
    for name, (aci, _) in LAYERS.items():
        doc.layers.add(name, color=aci, linetype='Continuous')
    msp = doc.modelspace()
    for layer, rows in sh.items():
        a = {'layer': layer}
        for s in rows:
            if s[0] == 'circle':
                msp.add_circle((s[1], s[2]), s[3], dxfattribs=a)
            elif s[0] == 'stroke':
                p = s[1]
                closed = len(p) > 2 and math.dist(p[0], p[-1]) < 1e-9
                msp.add_lwpolyline(p[:-1] if closed else p, format='xy', close=closed, dxfattribs=a)
            else:
                pts, closed = lw_points(s)
                msp.add_lwpolyline(pts, format='xyseb', close=closed, dxfattribs=a)
    # Real drawing extents in $EXTMIN/$EXTMAX. ezdxf copies them from the layout
    # on save; left alone they stay at the "empty drawing" placeholder (+-1e20),
    # which makes some importers (LibreOffice, tested) shrink the drawing to a dot.
    ext = bbox.extents(msp)
    msp.reset_extents((ext.extmin.x, ext.extmin.y, 0), (ext.extmax.x, ext.extmax.y, 0))
    msp.reset_limits((ext.extmin.x, ext.extmin.y), (ext.extmax.x, ext.extmax.y))
    zoom.extents(msp)
    doc.saveas(path)

# ----------------------------------------------------------------------- SVG
def write_svg(sh, path, bounds):
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    f = lambda v: f'{v:.4f}'.rstrip('0').rstrip('.')
    X = lambda x: f(x - x0)
    Y = lambda y: f(y1 - y)                    # SVG Y runs down
    o = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{f(w)}mm" height="{f(h)}mm" viewBox="0 0 {f(w)} {f(h)}">',
         f'<title>{NAME}: 1:1, millimetres, seen from above</title>']
    for layer, rows in sh.items():
        st = f'fill="none" stroke="{LAYERS[layer][1]}" stroke-width="{HAIRLINE}"'
        o.append(f'<g id="{layer}">')
        for s in rows:
            if s[0] == 'circle':
                o.append(f'<circle cx="{X(s[1])}" cy="{Y(s[2])}" r="{f(s[3])}" {st}/>')
            elif s[0] == 'rrect':
                _, a, b, c, d, r = s
                o.append(f'<rect x="{X(a)}" y="{Y(d)}" width="{f(c - a)}" height="{f(d - b)}" rx="{f(r)}" ry="{f(r)}" {st}/>')
            elif s[0] == 'slot':
                _, x, ya, yb, r = s
                o.append(f'<rect x="{X(x - r)}" y="{Y(yb + r)}" width="{f(2 * r)}" height="{f(yb - ya + 2 * r)}" rx="{f(r)}" ry="{f(r)}" {st}/>')
            else:
                p = s[1]
                closed = len(p) > 2 and math.dist(p[0], p[-1]) < 1e-9
                pts = p[:-1] if closed else p
                d = 'M ' + ' L '.join(f'{X(px)} {Y(py)}' for px, py in pts) + (' Z' if closed else '')
                o.append(f'<path d="{d}" {st} stroke-linecap="round" stroke-linejoin="round"/>')
        o.append('</g>')
    o.append('</svg>')
    Path(path).write_text('\n'.join(o) + '\n')

# -------------------------------------------------------------------- export
def export(m):
    try:
        import ezdxf  # noqa: F401
    except ImportError:
        if not shutil.which('uv'):
            raise SystemExit('lasercut.py needs ezdxf: pip install ezdxf, or install uv and re-run design.py')
        r = subprocess.run(UV_CMD + [str(ROOT / 'lasercut.py')], check=True, capture_output=True, text=True)
        return json.loads(r.stdout.strip().splitlines()[-1])
    out = ROOT / 'lasercut'; out.mkdir(exist_ok=True)
    sh = shapes(m)
    x0, y0, x1, y1, _ = m.plate_outline()
    c = m.LASER_KERF / 2
    pad = c + 1.0
    write_dxf(sh, out / f'{NAME}.dxf', 'R2018')
    write_dxf(sh, out / f'{NAME}_R2000.dxf', 'R2000')
    write_svg(sh, out / f'{NAME}.svg', (x0 - pad, y0 - pad, x1 + pad, y1 + pad))
    return {'files': [f'lasercut/{NAME}.dxf', f'lasercut/{NAME}_R2000.dxf', f'lasercut/{NAME}.svg'],
            'plate_mm': [round(x1 - x0, 3), round(y1 - y0, 3), m.PLATE_T],
            'drawn_outline_mm': [round(x1 - x0 + 2 * c, 3), round(y1 - y0 + 2 * c, 3)],
            'kerf_compensated_mm': m.LASER_KERF, 'entities': {k: len(v) for k, v in sh.items()}}

if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    import design
    print(json.dumps(export(design)))
