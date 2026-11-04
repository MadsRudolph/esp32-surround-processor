#!/usr/bin/env python3
"""A test coupon for the one thing on this board nobody has cut yet: the WROOM-32
castellations on the ball mill.

    python3 tools/kpy.py tools/make_coupon.py
    tools/export_production.sh hardware/coupon/wroom_coupon.kicad_pcb hardware/coupon/production

Cut it with the same SRM-CAM profile as the board. Under the microscope, then with
a meter: every neighbouring pad pair must read open, and every pad must keep copper
the module can land on. A module soldered to it proves the land pattern too. The
board is scrap if this fails, so cut this first; it costs one small offcut.
"""
from pathlib import Path
import pcbnew
from pcbnew import VECTOR2I, FromMM

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "hardware/coupon/wroom_coupon.kicad_pcb"
OUT.parent.mkdir(exist_ok=True)
W, H = 40.0, 36.0
X0, Y0 = 20.0, 20.0

board = pcbnew.NewBoard(str(OUT))
ds = board.GetDesignSettings()
ds.SetCopperLayerCount(2)
nc = board.GetAllNetClasses()["Default"]
nc.SetTrackWidth(FromMM(0.5)); nc.SetClearance(FromMM(0.3))
ds.m_TrackMinWidth = FromMM(0.5)

fp = pcbnew.FootprintLoad(str(ROOT / "lib/Surround.pretty"), "ESP32-WROOM-32_NoVias")
fp.SetReference("U1"); fp.SetValue("WROOM-32 coupon")
board.Add(fp)
c = VECTOR2I(FromMM(X0 + W / 2), FromMM(Y0 + H - 17.0))
fp.SetPosition(c)
fp.Flip(c, pcbnew.FLIP_DIRECTION_LEFT_RIGHT)

# a 5 mm stub off every pad, so each pair can be metered and the tracks look like the board's
n = 0
for pad in fp.Pads():
    num = pad.GetNumber()
    if not num.isdigit() or int(num) > 38:
        continue
    net = pcbnew.NETINFO_ITEM(board, f"P{num}")
    board.Add(net)
    pad.SetNet(net)
    p = pad.GetPosition()
    i = int(num)
    d = VECTOR2I(FromMM(5), 0) if i <= 14 else (VECTOR2I(0, FromMM(5)) if i <= 24 else VECTOR2I(FromMM(-5), 0))
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(p); t.SetEnd(VECTOR2I(p.x + d.x, p.y + d.y))
    t.SetWidth(FromMM(0.5)); t.SetLayer(pcbnew.B_Cu); t.SetNet(net)
    board.Add(t)
    n += 1

rect = pcbnew.PCB_SHAPE(board)
rect.SetShape(pcbnew.SHAPE_T_RECT)
rect.SetStart(VECTOR2I(FromMM(X0), FromMM(Y0))); rect.SetEnd(VECTOR2I(FromMM(X0 + W), FromMM(Y0 + H)))
rect.SetLayer(pcbnew.Edge_Cuts); rect.SetWidth(FromMM(0.1)); rect.SetFilled(False)
board.Add(rect)
pcbnew.SaveBoard(str(OUT), board)
print(f"wrote {OUT.relative_to(ROOT)}: {W:g} x {H:g} mm, {n} pads with stubs")
