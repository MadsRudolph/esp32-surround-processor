#!/usr/bin/env python3
"""Netlist JSON -> hardware/surround.kicad_pcb with footprints, nets, outline,
mounting holes, a B.Cu GND pour and the cnc-fine netclass. Linux port of the
kicad-laser-pcb skill's pcb_build.py (which joins paths with backslashes).

    python3 tools/pcb_bootstrap.py [WxH mm]      # default 120x100

Parts land on a coarse grid only so the file is valid; tools/surround_board.py
places and routes them afterwards.
"""
import json, os, sys, math
from pathlib import Path
import pcbnew
from pcbnew import VECTOR2I, FromMM

ROOT = Path(__file__).resolve().parents[1]
JSONF = ROOT / "hardware/surround.json"
OUT = ROOT / "hardware/surround.kicad_pcb"
LIB_ROOTS = [ROOT / "lib", Path.home() / ".claude/skills/kicad-laser-pcb/lib",
             Path("/usr/share/kicad/footprints")]
W, H = (float(v) for v in (sys.argv[1] if len(sys.argv) > 1 else "120x100").lower().split("x"))
X0, Y0 = 20.0, 20.0
CLEARANCE, TRACK = 0.50, 0.50         # cnc-fine profile: 0.8 mm ball mill, 0.44 mm channel


def load_fp(fpid):
    lib, name = fpid.split(":")
    for base in LIB_ROOTS:
        d = base / f"{lib}.pretty"
        if d.is_dir():
            fp = pcbnew.FootprintLoad(str(d), name)
            if fp is not None:
                return fp
    raise SystemExit(f"footprint not found: {fpid}")


data = json.loads(JSONF.read_text(encoding="utf-8"))
board = pcbnew.NewBoard(str(OUT))
netmap = {}
for name in data["nets"]:
    ni = pcbnew.NETINFO_ITEM(board, name); board.Add(ni); netmap[name] = ni

fps = {}
for c in sorted(data["components"], key=lambda c: c["ref"]):
    fp = load_fp(c["footprint"])
    fp.SetReference(c["ref"]); fp.SetValue(c["value"] or "")
    board.Add(fp)
    hit = 0
    for p in fp.Pads():
        net = c["pads"].get(p.GetNumber())
        if net:
            p.SetNet(netmap[net]); hit += 1
    if c["pads"] and hit == 0:
        raise SystemExit(f"{c['ref']}: no pad got a net (pin-number mismatch)")
    fps[c["ref"]] = fp

# four M3 mounting holes, locked, 4 mm in from the corners
# H1 sits in from the corner: the output terminals line up with the DAC pads and fill it
for i, (dx, dy) in enumerate([(15, 4), (W - 4, 4), (15, H - 4), (W - 4, H - 4)], 1):
    fp = load_fp("MountingHole:MountingHole_3.2mm_M3")
    fp.SetReference(f"H{i}"); fp.SetValue("M3")
    board.Add(fp)
    fp.SetPosition(VECTOR2I(FromMM(X0 + dx), FromMM(Y0 + dy)))
    fp.SetLocked(True)
    fp.Reference().SetVisible(False)   # a screw hole in the corner needs no silk
    fps[f"H{i}"] = fp

# provisional grid placement (bbox centres), 4 columns
x, y, rowh, col = X0 + 15, Y0 + 15, 0, 0
for ref, fp in fps.items():
    if ref.startswith("H"):
        continue
    bb = fp.GetBoundingBox(False)
    w, h = pcbnew.ToMM(bb.GetWidth()) + 4, pcbnew.ToMM(bb.GetHeight()) + 4
    if x + w > X0 + W - 5:
        x, y, rowh = X0 + 15, y + rowh, 0
    t = VECTOR2I(FromMM(x + w / 2), FromMM(y + h / 2))
    fp.SetPosition(t)
    c = fp.GetBoundingBox(False).Centre()
    fp.SetPosition(VECTOR2I(t.x + (t.x - c.x), t.y + (t.y - c.y)))
    x += w; rowh = max(rowh, h)

# outline
rect = pcbnew.PCB_SHAPE(board)
rect.SetShape(pcbnew.SHAPE_T_RECT)
rect.SetStart(VECTOR2I(FromMM(X0), FromMM(Y0))); rect.SetEnd(VECTOR2I(FromMM(X0 + W), FromMM(Y0 + H)))
rect.SetLayer(pcbnew.Edge_Cuts); rect.SetWidth(FromMM(0.1)); rect.SetFilled(False)
board.Add(rect)

# GND pour on B.Cu over the whole outline
z = pcbnew.ZONE(board)
z.SetLayer(pcbnew.B_Cu); z.SetNet(netmap["GND"]); z.SetZoneName("GND_pour")
ol = z.Outline(); ol.NewOutline()
for (px, py) in [(X0, Y0), (X0 + W, Y0), (X0 + W, Y0 + H), (X0, Y0 + H)]:
    ol.Append(FromMM(px), FromMM(py))
z.SetLocalClearance(FromMM(CLEARANCE)); z.SetMinThickness(FromMM(0.5))
# solid pad connection: no thermal spokes to starve or for the mill to nick;
# the pads are hand-soldered into a plane the iron can keep up with
z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
board.Add(z)

ds = board.GetDesignSettings()
ds.SetCopperLayerCount(2)
ds.m_TrackMinWidth = FromMM(TRACK)
nc = board.GetAllNetClasses()["Default"]
nc.SetTrackWidth(FromMM(TRACK)); nc.SetClearance(FromMM(CLEARANCE))
# a via on this process is a drilled hole with a wire link through it
nc.SetViaDiameter(FromMM(1.6)); nc.SetViaDrill(FromMM(0.8))
ds.m_ViasMinSize = FromMM(1.6); ds.m_MinThroughDrill = FromMM(0.8)
pcbnew.SaveBoard(str(OUT), board)
print(f"wrote {OUT.name}: {len(fps)} footprints, {len(netmap)} nets, {W:g}x{H:g} mm, GND pour on B.Cu")
