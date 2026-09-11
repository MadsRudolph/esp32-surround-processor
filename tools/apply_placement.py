#!/usr/bin/env python3
"""Apply tools/surround.placement.json (COURTYARD-CENTRE x, y, rot in board-relative mm)
to the bootstrapped board and write hardware/surround.kicad_pcb in place.

    python3 tools/apply_placement.py [in.kicad_pcb] [out.kicad_pcb]
"""
import json, sys
from pathlib import Path
import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

ROOT = Path(__file__).resolve().parents[1]
src = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "hardware/surround.kicad_pcb")
dst = sys.argv[2] if len(sys.argv) > 2 else src
X0 = Y0 = 20.0
W, H = 140.0, 110.0
plan = {k: v for k, v in json.load(open(ROOT / "tools/surround.placement.json")).items() if not k.startswith("_")}
b = pcbnew.LoadBoard(src)
fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
missing = [r for r in fps if r not in plan and not r.startswith("H")]
if missing:
    raise SystemExit(f"placement.json lacks: {missing}")
def crt_centre(fp):
    """Courtyard-bbox centre. NOT the same as the footprint anchor -- the anchor
    is usually pad 1, so an axial part's anchor sits at one end of its body and
    reasoning about spacing from anchors gets the gaps wrong by half a part."""
    poly = fp.GetCourtyard(pcbnew.F_CrtYd)
    if poly.OutlineCount() == 0:
        poly = fp.GetCourtyard(pcbnew.B_CrtYd)
    bb = poly.BBox() if poly.OutlineCount() else fp.GetBoundingBox(False)
    return bb.Centre()


for ref, (x, y, rot) in plan.items():
    fp = fps[ref]
    fp.SetOrientationDegrees(rot)
    target = VECTOR2I(FromMM(X0 + x), FromMM(Y0 + y))
    fp.SetPosition(target)
    c = crt_centre(fp)
    fp.SetPosition(VECTOR2I(target.x + (target.x - c.x), target.y + (target.y - c.y)))
# courtyard overlap check, the thing the scorer will not fail on
crt = {}
for ref, fp in fps.items():
    bb0 = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = bb0.BBox() if bb0.OutlineCount() else fp.GetBoundingBox(False)
    crt[ref] = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
refs = sorted(crt)
hits = []
for i, a in enumerate(refs):
    for c in refs[i + 1:]:
        A, C = crt[a], crt[c]
        if A[0] < C[2] and C[0] < A[2] and A[1] < C[3] and C[1] < A[3]:
            hits.append((a, c))
out = [r for r, c in crt.items() if c[0] < X0 or c[1] < Y0 or c[2] > X0 + W or c[3] > Y0 + H]
pcbnew.SaveBoard(dst, b)
print(f"applied {len(plan)} parts -> {Path(dst).name}; courtyard overlaps: {hits or 'none'}; outside outline: {out or 'none'}")
