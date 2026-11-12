#!/usr/bin/env python3
"""Pull what the enclosure needs out of the KiCad board. Run: python3 enclosure/board_export.py

Writes cad/board.step (kicad-cli STEP export) and cad/board_data.json (outline,
mounting holes and the footprints the enclosure refers to). The board is copied
to a temporary folder first, so nothing in hardware/ is opened for writing.

Board frame used everywhere in enclosure/: millimetres, origin at the board's
south-west corner, X east, Y north, Z up, Z = 0 at the bottom face of the board.
"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HW = ROOT.parent / 'hardware'
MODELS = '/usr/share/kicad/3dmodels'

READER = r'''
import json, sys, pcbnew
if not hasattr(pcbnew.SwigPyIterator, "next"):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__
mm = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
xs, ys = [], []
for d in b.GetDrawings():
    if d.GetLayer() == pcbnew.Edge_Cuts:
        for p in (d.GetStart(), d.GetEnd()):
            xs.append(mm(p.x)); ys.append(mm(p.y))
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
fx = lambda x: round(x - x0, 3)
fy = lambda y: round(y1 - y, 3)
out = {"kicad_origin_mm": [x0, y1], "size_mm": [round(x1 - x0, 3), round(y1 - y0, 3)],
       "thickness_mm": mm(b.GetDesignSettings().GetBoardThickness()), "holes": {}, "parts": {}}
for f in b.GetFootprints():
    ref = f.GetReference()
    bb = f.GetBoundingBox(False)
    pads = [(mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in f.Pads()]
    row = {"value": f.GetValue(), "side": "bottom" if f.IsFlipped() else "top",
           "bbox": [fx(mm(bb.GetLeft())), fy(mm(bb.GetBottom())), fx(mm(bb.GetRight())), fy(mm(bb.GetTop()))]}
    if pads:
        row["pads_bbox"] = [fx(min(p[0] for p in pads)), fy(max(p[1] for p in pads)),
                            fx(max(p[0] for p in pads)), fy(min(p[1] for p in pads))]
        row["centre"] = [round((row["pads_bbox"][0] + row["pads_bbox"][2]) / 2, 3),
                         round((row["pads_bbox"][1] + row["pads_bbox"][3]) / 2, 3)]
    if f.GetValue() == "M3" and ref.startswith("H"):
        pad = list(f.Pads())[0]
        out["holes"][ref] = {"xy": row["centre"], "drill": mm(pad.GetDrillSize().x)}
    else:
        out["parts"][ref] = row
json.dump(out, open(sys.argv[2], "w"), indent=1, sort_keys=True)
'''

def main():
    (ROOT / 'cad').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        for name in ['surround.kicad_pcb', 'surround.kicad_pro', 'fp-lib-table', 'sym-lib-table']:
            shutil.copy(HW / name, t / name)
        (t / 'read.py').write_text(READER)
        subprocess.run([sys.executable, str(t / 'read.py'), str(t / 'surround.kicad_pcb'),
                        str(ROOT / 'cad' / 'board_data.json')], check=True)
        d = json.loads((ROOT / 'cad' / 'board_data.json').read_text())
        x0, y1 = d['kicad_origin_mm']
        r = subprocess.run(['kicad-cli', 'pcb', 'export', 'step', '--subst-models', '-f',
                            '-D', 'KICAD9_3DMODEL_DIR=' + MODELS,
                            '--user-origin', f'{x0}x{y1}mm',
                            '-o', str(ROOT / 'cad' / 'board.step'), str(t / 'surround.kicad_pcb')],
                           capture_output=True, text=True)
        missing = sorted({l.split()[-1].rstrip('.') for l in r.stdout.splitlines() if l.startswith('Could not add 3D model')})
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
    # Footprints that carry no 3D model, or whose model KiCad could not find, are not
    # in the STEP. design.py stands an envelope in for each of them.
    no_model = sorted(set(missing) | {'A3', 'A4', 'D1', 'D4'})
    d['not_in_step'] = no_model
    (ROOT / 'cad' / 'board_data.json').write_text(json.dumps(d, indent=1, sort_keys=True))
    print('board', d['size_mm'], 'holes', d['holes'])
    print('not in the STEP (envelopes used instead):', ', '.join(no_model))

if __name__ == '__main__':
    main()
