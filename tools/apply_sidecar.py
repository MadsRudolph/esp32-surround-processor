#!/usr/bin/env python3
"""Apply a place_dsl.py sidecar (<stem>.autoplace.json) to a board with pcbnew.

The kicad-place compiler emits the sidecar and then tries to apply it through
KiCad's Windows python + the KiCad-Autoplace plugin; neither exists on this
machine, so this does the same thing with the system pcbnew: set each part's
absolute rotation, then move it so its COURTYARD-BBOX CENTRE lands on the
sidecar position (that is the compiler's own coordinate convention).

    python3 tools/apply_sidecar.py <sidecar.json> <in.kicad_pcb> <out.kicad_pcb>
"""
import json, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

sidecar, src, dst = sys.argv[1:4]
doc = json.load(open(sidecar, encoding="utf-8"))
b = pcbnew.LoadBoard(src)
# (the bootstrap board carries no tracks; a routed board must be stripped first)
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
locked = set(doc.get("locked", []))


def crt_centre(fp):
    poly = fp.GetCourtyard(pcbnew.F_CrtYd)
    if poly.OutlineCount() == 0:
        poly = fp.GetCourtyard(pcbnew.B_CrtYd)
    bb = poly.BBox() if poly.OutlineCount() else fp.GetBoundingBox(False)
    return bb.Centre()


n = 0
for ref, (x, y) in doc["positions"].items():
    fp = fps.get(ref)
    if fp is None or ref in locked or fp.IsLocked():
        continue
    fp.SetOrientationDegrees(float(doc.get("rotations", {}).get(ref, fp.GetOrientationDegrees())))
    target = VECTOR2I(FromMM(x), FromMM(y))
    for _ in range(3):                      # converge: centre depends on rotation only, so 1 pass suffices
        c = crt_centre(fp)
        p = fp.GetPosition()
        fp.SetPosition(VECTOR2I(p.x + (target.x - c.x), p.y + (target.y - c.y)))
    n += 1
worst = 0.0
for ref, (x, y) in doc["positions"].items():
    fp = fps.get(ref)
    if fp is None or ref in locked:
        continue
    c = crt_centre(fp)
    worst = max(worst, abs(ToMM(c.x) - x), abs(ToMM(c.y) - y))
pcbnew.SaveBoard(dst, b)
print(f"applied {n} positions -> {dst}; worst courtyard-centre residual {worst:.4f} mm")
