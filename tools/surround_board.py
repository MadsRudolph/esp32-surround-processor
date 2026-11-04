#!/usr/bin/env python3
"""Place and route the ball-milled board: floorplan and copper as code.

    python3 tools/kpy.py tools/surround_board.py

Reads the bootstrapped hardware/surround.kicad_pcb (tools/pcb_bootstrap.py) and
writes it back placed, routed and with the ground pour filled. Every coordinate
is board-relative mm, outline origin top-left, and hangs off the anchors below.

THE ROUTING RULES, enforced by check_run(); the build stops if one is broken:
  * every segment is horizontal, vertical or exactly 45 degrees;
  * no run ever turns by more than 45 degrees. A square corner written in a run
    is chamfered automatically, and any other sharper turn is an error;
  * a net with a pad on the ESP32 is 0.9 mm wide, the width of the module's pads.
Parts are placed so their pins line up and the traces can run dead straight.

WHY THIS IS HAND-PLANNED AND NOT AUTOROUTED. One copper layer makes this a
planarity problem, and FreeRouting cannot see the trick that solves it: an axial
part's two pads sit either side of a gap, so a track can run underneath its body.
Every series part here is therefore also a free crossing.

THE TOPOLOGY, from the two nets everything else has to fit around.

  DIR_BCK and DIR_LRCK reach the same pads on two 1x6 DAC rows sitting in a line,
  so on one side of the rows they interleave. BCK therefore runs up the east face
  of the rows and LRCK up the west face.

  That traps three pads between the two runs: A4.1, A4.2, A3.6. R18 carries
  +5V_DAC2 in over both clocks, C3 sits inside with it, and the two ground pads
  get a short wire. DIN1 and DIN2 land inside too, so R4 and R5 straddle the BCK
  run. Both clocks come off the ESP32's east row: LRCK crosses the BCK line through
  the gap in R1, and the pot's R20 carries it over both.

  The DIR9001 row and the ESP32 east row list the same signals in the same order,
  so the five I2S and status lines fan out on parallel 45 degree runs.
"""
import math
import sys
from pathlib import Path
import pcbnew
from pcbnew import VECTOR2I, FromMM

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "hardware/surround.kicad_pcb"
X0 = Y0 = 20.0                  # outline origin, set by pcb_bootstrap.py

# ---------------------------------------------------------------- anchors
XC = 48.0                       # DAC socket column; bodies and outputs to the west
YN = 14.0                       # A4 centre, the surround DAC
YS = 47.0                       # A3 centre, the front DAC; the gap between holds C3
UX = 84.0                       # WROOM-32 centre, on B.Cu, antenna north
UY = YN - 1.27 + 6.98           # so U1 pin 37 (DIN2) is level with A4 pin 4
AX = 126.6                      # DIR9001 socket column; module overhangs east
JX = 6.0                        # output terminal column

BCK_RUN = 55.6                  # DIR_BCK up the east face of the DAC rows
LRCK_RUN = 45.5                 # DIR_LRCK up the west face
BCK_Y, LRCK_Y = 48.7, 50.1      # the two clocks heading west, south of the ESP32
V5_Y = 51.85                    # +5V heading west to the DACs
V33_Y = 41.5                    # +3V3 heading east from the LM317
V33_X = 129.8                   # +3V3 heading north, under the DIR9001 module
V33_S = 65.5                    # +3V3 along the south edge, to R15
XSMT_X = 58.0                   # the DAC XSMT wire pads
BOOT_X = 62.5                   # BOOT heading south to R15
EE = UX + 9.5                   # outer edge of the east pads
EW = UX - 9.5                   # outer edge of the west pads


def pin(n):
    """(x, y) of a WROOM pad, seen from the top of the board."""
    if n <= 14:
        return UX + 8.75, UY - 8.25 + (n - 1) * 1.27
    if n >= 25:
        return UX - 8.75, UY - 8.25 + (38 - n) * 1.27
    return UX + 5.71 - (n - 15) * 1.27, UY + 9.51


def yp(n):
    return pin(n)[1]


def ydac(cy, n):
    """y of pad n on a DAC socket row, rotated so pad 1 is at the south end."""
    return cy + 6.35 - (n - 1) * 2.54


def ya2(n):
    return 14.2 + (10 - n) * 2.54


# ---------------------------------------------------------------- placement
# ref -> (pad number, x, y, rot): put that pad at that point, then rotate about it.
BCK_T = 104.0                  # DIR_BCK turns south here, off the end of its fan
LRCK_T = 105.76                  # DIR_LRCK turns south here, through the gap in R1
PLACE = {
    "A2": ("10", AX, ya2(10), 180),
    "R1": ("2", BCK_T, ya2(4), 180),
    "R2": ("2", 113.8, ya2(5), 180),
    "R3": ("2", 103.5, ya2(6), 180),
    "A4": ("1", XC, ydac(YN, 1), 180),
    "A3": ("1", XC, ydac(YS, 1), 180),
    # the parts that straddle the BCK run
    "R5": ("2", XC + 5.0, ydac(YN, 4), 180),
    "R4": ("2", XC + 5.0, ydac(YS, 4), 180),
    "R18": ("1", XC + 2.9, V5_Y, 90),
    "C3": ("1", XC + 2.2, 30.5, 0),
    # ESP32 supply and reset, in the corner north of the 3V3 line
    "C1": ("1", 102.1, 5.4, 0),
    "C9": ("2", 95.5, 9.0, 180),
    "C11": ("1", 113.0, 13.75, 90),
    "SW1": ("1", 123.5, yp(3), 180),
    "R14": ("1", 123.0, ya2(9), 180),
    # ESP32 west row
    "J2": ("1", 67.0, yp(35), 0),
    "SW3": ("1", 64.5, 27.2, 0),
    "SW2": ("1", 64.5, 35.2, 0),
    "R10": ("1", 73.4, yp(26), 270),
    "D1": ("2", 75.0, 37.0, 90),
    "R11": ("1", XSMT_X, 43.0, 0),
    "R15": ("1", 71.0, 55.66, 90),
    # scope ground, and the DIR9001's return across the clocks
    "TP1": ("1", 96.5, 34.05, 0),
    "TP2": ("1", 114.0, 34.05, 0),
    # pot
    "R20": ("1", 102.0, 32.5, 0),
    "J7": ("1", 112.7, 43.96, 0),
    # DIR9001 filter
    "R19": ("1", 107.6, ya2(1), 0),
    "C4": ("1", 118.25, 33.5, 0),
    # supply: terminal, Schottky, regulators
    "J1": ("1", 80.5, 61.0, 180),
    "D2": ("1", 95.0, 61.0, 180),
    "C5": ("1", 105.6, 57.7, 0),
    "C6": ("1", 113.0, 60.2, 90),
    "U2": ("1", 101.0, 55.5, 180),
    "C7": ("1", 85.0, 52.85, 270),
    "C8": ("1", 88.5, 54.0, 0),
    "U3": ("3", 117.5, 50.0, 180),
    "R12": ("1", 120.04, 46.6, 0),
    "R13": ("1", 127.66, 49.4, 270),
    "D3": ("1", 109.88, 63.2, 0),
    "R16": ("1", 70.5, 59.0, 180),
    "D4": ("2", 62.88, 62.0, 90),
    # DAC 1 filter
    "R17": ("1", 64.0, 54.5, 180),
    "C2": ("1", 54.25, 61.5, 0),
    # outputs: DAC pad, resistor and terminal in one straight line
    "J6": ("T", JX, YN, 90),
    "J5": ("T", JX, YN + 5.08, 270),
    "J4": ("T", JX, YS, 90),
    "J3": ("T", JX, YS + 5.08, 270),
    "R8": ("1", 19.0, YN, 180),
    "R9": ("1", 11.2, YN - 5.08, 0),
    "R6": ("1", 19.0, YN + 5.08, 180),
    "R7": ("1", 11.2, YN + 10.16, 0),
}
ESP, PWR, SIG = 0.9, 1.0, 0.5


# ---------------------------------------------------------------- copper
# (net, width, [pad "REF.N" or (x, y) ...]) on B.Cu, the milled side.
def tracks():
    u = "U1.{}".format
    # the DIR9001 fan: lower lines start their 45 degree run first, so they stay parallel
    def fan(n, a2, start):
        return [u(n), (start, yp(n)), (start + ya2(a2) - yp(n), ya2(a2))]
    return [
        # ------ DIR9001 <-> ESP32 east row
        ("Net-(A2-AUDIO)", ESP, fan(4, 8, 98.11) + ["A2.8"]),
        ("Net-(A2-ERROR)", ESP, fan(5, 7, 97.31) + ["A2.7"]),
        ("Net-(U1-IO34)", ESP, fan(6, 6, 96.51) + ["R3.2"]),
        ("Net-(A2-DOUT)", SIG, ["R3.1", "A2.6"]),
        ("Net-(A2-LRCKO)", SIG, ["R2.1", "A2.5"]),
        ("Net-(A2-BCKO)", SIG, ["R1.1", "A2.4"]),

        # ------ the two clocks
        ("DIR_LRCK", ESP, fan(7, 5, 95.71) + ["R2.2"]),
        ("DIR_LRCK", ESP, [(LRCK_T - 1.5, ya2(5)), (LRCK_T, ya2(5) + 1.5), (LRCK_T, LRCK_Y),
                           (XC + 2.68, LRCK_Y), (XC + 0.85, ydac(YS, 3)), "A3.3"]),
        ("DIR_LRCK", ESP, ["A3.3", (LRCK_RUN, ydac(YS, 3)), (LRCK_RUN, ydac(YN, 3)), "A4.3"]),
        ("DIR_BCK", ESP, fan(8, 4, 94.91) + ["R1.2"]),
        ("DIR_BCK", ESP, ["R1.2", (BCK_T, BCK_Y), (BCK_RUN, BCK_Y), (BCK_RUN, ydac(YN, 5)), "A4.5"]),
        ("DIR_BCK", ESP, [(BCK_RUN, ydac(YS, 5) + 1.5), (BCK_RUN - 1.5, ydac(YS, 5)), "A3.5"]),

        # ------ DAC data: straight through R5, down and through R4
        ("Net-(U1-IO23)", ESP, [u(37), "R5.1"]),
        ("Net-(A4-DIN)", SIG, ["R5.2", "A4.4"]),
        ("Net-(U1-IO19)", ESP, [u(31), (EW - 1.06, yp(31)), (EW - 5.5, yp(31) + 4.44),
                                ("R4.1", yp(31) + 4.44), "R4.1"]),
        ("Net-(A3-DIN)", SIG, ["R4.2", "A3.4"]),

        # ------ XSMT: flying leads to both DACs
        ("XSMT", ESP, [u(33), (EW - 0.5, yp(33)), (EW - 5.4, yp(33) + 4.9), (XSMT_X, yp(33) + 4.9),
                       "A4.7", "A3.7", "R11.1"]),

        # ------ UART: TXD0 dead straight, RXD0 one jog over to the next pin
        ("TXD0", ESP, [u(35), "J2.1"]),
        ("RXD0", ESP, [u(34), (EW - 1.21, yp(34)), (EW - 2.48, yp(34) + 1.27), "J2.2"]),

        # ------ buttons and status LED
        ("USER", ESP, [u(30), (EW - 0.35, yp(30)), (71.0, yp(30) + 3.15), (71.0, 27.2)]),
        ("USER", ESP, [(71.0, 27.2), (64.5, 27.2)]),
        ("BOOT", ESP, [u(25), (EW + 0.1, yp(25)), (EW + 0.1 - 1.48, yp(25) + 1.48), (BOOT_X + 0.7, yp(25) + 1.48),
                       (BOOT_X, yp(25) + 2.18), (BOOT_X, 43.5), (BOOT_X + 2.0, 45.5), "R15.2"]),
        ("BOOT", ESP, [(BOOT_X, 35.2), (71.0, 35.2)]),
        ("LED", ESP, [u(26), "R10.1"]),
        ("Net-(D1-A)", SIG, ["R10.2", (73.4, 35.4), "D1.2"]),

        # ------ pot, R20 carries it over both clocks
        ("POT", ESP, [u(9), (EE + 0.7, yp(9)), (EE + 6.2, yp(9) + 5.5), (EE + 6.2, 30.2), "R20.1"]),
        ("Net-(J7-Pin_2)", SIG, ["R20.2", (110.5, 33.38), (110.5, 45.0), (112.0, 46.5), "J7.2"]),

        # ------ ESP32 ground and supply
        ("GND", ESP, [u(1), (EE + 1.0, yp(1))]),
        ("GND", ESP, [u(15), (pin(15)[0], 32.0)]),
        ("GND", ESP, [u(38), (EW - 2.5, yp(38))]),
        ("+3V3", ESP, [u(2), (EE + 1.5, yp(2)), (EE + 2.23, 12.0), (AX - 2.2, 12.0), "A2.10"]),
        ("+3V3", ESP, ["A2.10", "A2.9"]),
        ("+3V3", ESP, ["C1.1", (102.1, 12.0)]),
        ("+3V3", SIG, ["C9.1", (98.0, 12.0)]),
        ("+3V3", SIG, ["R14.1", "A2.9"]),
        ("EN", ESP, [u(3), (123.5, yp(3))]),
        ("EN", ESP, ["R14.2", ("R14.2", yp(3))]),

        # ------ 3V3 from the LM317
        ("+3V3", ESP, ["U3.2", (120.04, 43.0), (121.54, V33_Y), (V33_X, V33_Y), (V33_X, ya2(10)), "A2.10"]),
        ("+3V3", ESP, [(120.04, 43.0), (118.54, V33_Y), (112.7, V33_Y), "J7.1"]),
        ("+3V3", SIG, ["U3.2", (120.04, V33_S), (71.0, V33_S), "R15.1"]),
        ("+3V3", SIG, [(71.0, 59.0), "R16.1"]),
        ("Net-(D4-A)", SIG, ["R16.2", "D4.2"]),
        ("Net-(U3-ADJ)", SIG, ["U3.1", (126.16, 50.0), (127.66, 48.5)]),
        ("Net-(U3-ADJ)", SIG, ["R12.2", "R13.1"]),

        # ------ 9 V
        ("Net-(D2-A)", PWR, ["J1.1", "D2.2"]),
        ("+9V", PWR, ["D2.1", (117.5, 61.0), "U3.3"]),
        ("+9V", PWR, [(101.0, 61.0), "U2.1"]),
        ("+9V", SIG, [(109.88, 61.0), "D3.1"]),
        ("+9V", SIG, [(105.6, 61.0), "C5.1"]),
        ("+9V", SIG, [(113.0, 61.0), "C6.1"]),

        # ------ 5 V
        ("+5V", PWR, ["U2.3", (95.92, V5_Y)]),
        ("+5V", PWR, [(107.6, ya2(1)), (107.6, V5_Y), "R18.1"]),
        ("+5V", SIG, [(85.0, V5_Y), "C7.1"]),
        ("+5V", SIG, [(88.5, V5_Y), "C8.1"]),
        ("+5V", PWR, [(64.0, V5_Y), "R17.1"]),

        # ------ filtered rails
        ("+5V_DAC2", PWR, ["R18.2", (XC + 2.9, 31.2), (XC + 2.2, 30.5), (XC + 2.2, 22.55), "A4.1"]),
        ("+5V_DAC1", PWR, ["R17.2", (XC + 2.0, 54.5), (XC + 0.85, ydac(YS, 1)), "A3.1"]),
        ("+5V_DAC1", PWR, ["C2.1", (54.25, 54.5)]),
        ("+5V_DIR", PWR, ["R19.2", "A2.1"]),
        ("+5V_DIR", PWR, ["C4.1", (118.25, ya2(1))]),

        # ------ outputs
        ("Net-(A4-OUTR)", SIG, ["A4.9", "R8.1"]),
        ("Net-(J6-PadT)", SIG, ["R8.2", "J6.T"]),
        ("Net-(J6-PadR)", SIG, ["J6.R", "R9.1"]),
        ("Net-(A4-OUTL)", SIG, ["A4.8", "R6.1"]),
        ("Net-(J5-PadT)", SIG, ["R6.2", "J5.T"]),
        ("Net-(J5-PadR)", SIG, ["J5.R", "R7.1"]),
        ("Net-(A3-OUTR)", SIG, ["A3.9", "J4.T"]),
        ("Net-(A3-OUTL)", SIG, ["A3.8", "J3.T"]),
    ]


# Wire links, drawn on F.Cu so DRC and tools/wire_links.py see them.
def links():
    return [
        # the ground pads trapped between the clock runs
        ("GND", SIG, ["A3.2", (XC + 1.6, ydac(YS, 2) - 1.6), (XC + 1.6, ydac(YS, 6) + 1.6), "A3.6"]),
        # without this the clocks' return runs about 150 mm round the board
        ("GND", SIG, ["TP1.1", "TP2.1"]),
    ]


# ---------------------------------------------------------------- machinery
CHAMFER = 1.5                   # mm taken off each side of a chamfered square corner
TOL = 0.03                      # mm, for the pad positions that come back from pcbnew


def mm(v):
    return FromMM(v)


def place(fps):
    # The module goes on the milled side, seen through the board from the top.
    u1 = fps["U1"]
    u1.SetPosition(VECTOR2I(mm(X0 + UX), mm(Y0 + UY)))
    u1.Flip(u1.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for pad in u1.Pads():
        if pad.GetNumber().isdigit() and int(pad.GetNumber()) <= 38:
            x, y = pin(int(pad.GetNumber()))
            d = pad.GetPosition()
            assert abs(d.x - mm(X0 + x)) < 2000 and abs(d.y - mm(Y0 + y)) < 2000, (pad.GetNumber(), d.x, d.y)
    for ref, (padnum, x, y, rot) in PLACE.items():
        fp = fps[ref]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
        pad = next(p for p in fp.Pads() if p.GetNumber() == padnum)
        d = pad.GetPosition() - fp.GetPosition()
        fp.SetPosition(VECTOR2I(mm(X0 + x) - d.x, mm(Y0 + y) - d.y))


def check_tall(fps):
    """Cans must clear the DAC modules: nothing tall fits under them, and the module
    outline is a reservation drawn on F.Fab, so DRC's courtyards cannot see it."""
    for ref in ("C1", "C2", "C3", "C4", "C5", "C8", "C11"):
        bb = fps[ref].GetCourtyard(pcbnew.F_CrtYd).BBox()
        for cy in (YN, YS):
            x0, x1, y0, y1 = mm(X0 + XC - 29), mm(X0 + XC + 3), mm(Y0 + cy - 12), mm(Y0 + cy + 12)
            if bb.GetLeft() < x1 and bb.GetRight() > x0 and bb.GetTop() < y1 and bb.GetBottom() > y0:
                sys.exit(f"{ref} is under the DAC module at y={cy}")


def direction(a, b):
    """Unit octilinear direction of a segment, or None if it is off the 45 degree grid."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if abs(dx) > TOL and abs(dy) > TOL and abs(abs(dx) - abs(dy)) > TOL:
        return None
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n else (0.0, 0.0)


def turn(d0, d1):
    return math.degrees(math.acos(max(-1.0, min(1.0, d0[0] * d1[0] + d0[1] * d1[1]))))


def check_run(net, q):
    """The routing rules. Square corners get chamfered; anything else is a mistake."""
    out = [q[0]]
    for i in range(1, len(q) - 1):
        d0, d1 = direction(q[i - 1], q[i]), direction(q[i], q[i + 1])
        if d0 is None or d1 is None:
            sys.exit(f"{net}: off-grid segment around ({q[i][0]:.2f}, {q[i][1]:.2f})")
        if abs(turn(d0, d1) - 90) < 1.0:
            # keep the chamfer on its two segments when one of them is short
            r = min(CHAMFER, math.dist(q[i - 1], q[i]), math.dist(q[i], q[i + 1]))
            if math.dist(q[i - 1], q[i]) > r:
                out.append((q[i][0] - d0[0] * r, q[i][1] - d0[1] * r))
            if math.dist(q[i], q[i + 1]) > r:
                out.append((q[i][0] + d1[0] * r, q[i][1] + d1[1] * r))
        else:
            out.append(q[i])
    out.append(q[-1])
    if direction(q[-2], q[-1]) is None or direction(q[0], q[1]) is None:
        sys.exit(f"{net}: off-grid end segment at ({q[-1][0]:.2f}, {q[-1][1]:.2f})")
    for i in range(1, len(out) - 1):
        d0, d1 = direction(out[i - 1], out[i]), direction(out[i], out[i + 1])
        if d0 is None or d1 is None or turn(d0, d1) > 45.0 + 1.0:
            sys.exit(f"{net}: turn sharper than 45 degrees at ({out[i][0]:.2f}, {out[i][1]:.2f})")
    return out


def add_run(board, nets, pads, net, width, pts, layer):
    def resolve(p):
        if isinstance(p, str):
            v = pads[p]
            return pcbnew.ToMM(v.x) - X0, pcbnew.ToMM(v.y) - Y0
        x = pcbnew.ToMM(pads[p[0]].x) - X0 if isinstance(p[0], str) else p[0]
        return x, p[1]

    q = [resolve(p) for p in pts]
    q = [p for i, p in enumerate(q) if i == 0 or math.dist(p, q[i - 1]) > 1e-3]
    for s, e in zip(*(lambda r: (r, r[1:]))(check_run(net, q))):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(VECTOR2I(mm(X0 + s[0]), mm(Y0 + s[1])))
        t.SetEnd(VECTOR2I(mm(X0 + e[0]), mm(Y0 + e[1])))
        t.SetWidth(mm(width))
        t.SetLayer(layer)
        t.SetNet(nets[net])
        board.Add(t)


def add_escape_areas(board):
    """Where tracks leave the castellations they are still at the pads' own 0.37 mm
    gap. These rule areas are what .kicad_dru relaxes; they end where the fan does."""
    for x0, x1, y0, y1 in ((EE - 1.0, 98.5, 10.5, 24.0), (EW - 5.0, EW + 1.0, 10.5, 29.5),
                           (UX + 3.5, UX + 7.5, UY + 8.5, UY + 13.0)):
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetZoneName("U1_escape")
        z.SetLayer(pcbnew.B_Cu)
        z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False); z.SetDoNotAllowPads(False)
        z.SetDoNotAllowZoneFills(False); z.SetDoNotAllowFootprints(False)
        ol = z.Outline(); ol.NewOutline()
        for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ol.Append(mm(X0 + px), mm(Y0 + py))
        board.Add(z)


def main():
    board = pcbnew.LoadBoard(str(BOARD))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    missing = [r for r in fps if r not in PLACE and r != "U1" and not r.startswith("H")]
    if missing:
        sys.exit(f"no placement for {missing}")
    place(fps)
    check_tall(fps)
    nets = {n.GetNetname(): n for n in board.GetNetInfo().NetsByName().values()}
    pads, padnet = {}, {}
    for r, fp in fps.items():
        for p in fp.Pads():
            pads.setdefault(f"{r}.{p.GetNumber()}", p.GetPosition())
            padnet[f"{r}.{p.GetNumber()}"] = p.GetNetname()
    esp_nets = {p.GetNetname() for p in fps["U1"].Pads() if p.GetNetname()}
    for net, width, pts in tracks() + links():
        for p in pts:
            if isinstance(p, str) and padnet[p] != net:
                sys.exit(f"{p} is on {padnet[p]}, not {net}")
        if any(isinstance(p, str) and p.startswith("U1.") for p in pts) and width != ESP:
            sys.exit(f"{net}: a track leaving the ESP32 must be {ESP} mm")
    for net, width, pts in tracks():
        add_run(board, nets, pads, net, width, pts, pcbnew.B_Cu)
    for net, width, pts in links():
        add_run(board, nets, pads, net, width, pts, pcbnew.F_Cu)
    add_escape_areas(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)
    print(f"placed {len(PLACE)} parts, {len(tracks())} milled runs, {len(links())} wire links; "
          f"{len(esp_nets)} nets touch the ESP32")


if __name__ == "__main__":
    main()
