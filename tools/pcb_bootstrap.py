#!/usr/bin/env python3
"""Netlist JSON -> hardware/surround.kicad_pcb with footprints, nets, outline,
mounting holes, a B.Cu GND pour and the cnc netclass. Linux port of the
kicad-laser-pcb skill's pcb_build.py (which joins paths with backslashes).

    python3 tools/pcb_bootstrap.py [WxH mm]      # default 120x100

Parts land on a coarse grid only so the file is valid; placement is done by
the kicad-place DSL (tools/surround.place.py) afterwards.
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
CLEARANCE, TRACK = 0.85, 1.0          # cnc profile: 0.8 mm end mill


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
for i, (dx, dy) in enumerate([(4, 4), (W - 4, 4), (4, H - 4), (W - 4, H - 4)], 1):
    fp = load_fp("MountingHole:MountingHole_3.2mm_M3")
    fp.SetReference(f"H{i}"); fp.SetValue("M3")
    board.Add(fp)
    fp.SetPosition(VECTOR2I(FromMM(X0 + dx), FromMM(Y0 + dy)))
    fp.SetLocked(True)
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
z.SetLocalClearance(FromMM(CLEARANCE)); z.SetMinThickness(FromMM(0.8))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
z.SetThermalReliefGap(FromMM(CLEARANCE)); z.SetThermalReliefSpokeWidth(FromMM(1.0))
z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
board.Add(z)

ds = board.GetDesignSettings()
ds.SetCopperLayerCount(2)
ds.m_TrackMinWidth = FromMM(0.8)
nc = board.GetAllNetClasses()["Default"]
nc.SetTrackWidth(FromMM(TRACK)); nc.SetClearance(FromMM(CLEARANCE))
pcbnew.SaveBoard(str(OUT), board)
print(f"wrote {OUT.name}: {len(fps)} footprints, {len(netmap)} nets, {W:g}x{H:g} mm, GND pour on B.Cu")
