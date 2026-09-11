#!/usr/bin/env python3
"""Import a FreeRouting session (.ses) into the placed board, refill the GND
pour, and report what the single-sided process has to live with: every F.Cu
track run is a wire link soldered on top, every via a drilled hole for it.

    python3 tools/kpy.py tools/ses_import.py <placed.kicad_pcb> <routed.ses> <out.kicad_pcb>
"""
import sys
import pcbnew
src, ses, dst = sys.argv[1:4]
b = pcbnew.LoadBoard(src)
ok = pcbnew.ImportSpecctraSES(b, ses)
if not ok:
    raise SystemExit("SES import failed")
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
tracks = list(b.GetTracks())
vias = [t for t in tracks if t.GetClass() == "PCB_VIA"]
segs = [t for t in tracks if t.GetClass() == "PCB_TRACK"]
top = [t for t in segs if t.GetLayerName() == "F.Cu"]
bot = [t for t in segs if t.GetLayerName() == "B.Cu"]
mm = lambda ts: sum(pcbnew.ToMM(t.GetLength()) for t in ts)
# F.Cu runs: connected groups of top segments, by net
from collections import defaultdict
runs = defaultdict(int)
for t in top:
    runs[t.GetNetname()] += 1
print(f"imported {len(segs)} segments, {len(vias)} vias -> {dst}")
print(f"  B.Cu {len(bot)} segs {mm(bot):.0f} mm | F.Cu {len(top)} segs {mm(top):.0f} mm on nets: "
      + ", ".join(f"{n} ({c})" for n, c in sorted(runs.items())))
