#!/usr/bin/env python3
"""Place and route the double-sided ball-milled board: floorplan as code.

    python3 tools/kpy.py tools/surround_board.py [--place-only]

Reads the bootstrapped hardware/surround.kicad_pcb (tools/pcb_bootstrap.py) and
writes it back placed, routed and poured on both faces. Every coordinate is
board-relative mm, outline origin top-left, and through-hole pads sit on a
1.27 mm grid wherever the part allows it.

THE TWO FACES. The holes are not plated and there are no vias. The bottom
(B.Cu) carries every clock, data and audio track and the WROOM-32. The top
(F.Cu) is a ground plane that the mill only opens with a ring around each
non-ground hole, plus the supply runs listed in TOP_ROUTES. The faces meet only
where a lead is soldered on both: TOP_OK() says which leads the iron can reach
from the top, and tools/check_board.py proves the board is connected using only
those.

FLOORPLAN, west to east:

  * output terminals on the west edge, wire entry outward, first pin of each
    DAC level with that DAC's output row;
  * the two PCM5102 modules face down in one column of sockets at XC. The front
    DAC block and the surround DAC block are the same drawing, 25.4 mm apart:
    DIN resistor, supply cap and 10 R feed all straddle the BCK trunk, which
    runs dead straight up the east face of the column. LRCK runs up the west
    face and XSMT further west, under the modules;
  * the WROOM-32 on the milled side at the east edge, antenna off the board,
    centred between the two DIN levels so both data lines leave its west face
    as mirror images;
  * under the module, a row of resistors on its alternate south pins takes the
    DIR9001 lines; the pigtail holes sit below them. EN and +3V3 run down the
    east edge to the reset parts and the bulk cap;
  * boot and user buttons, LEDs and the UART header along the north edge;
    regulators along the south edge with their tabs outward and the +9V rail
    beneath them.
"""
import sys
from pathlib import Path
import pcbnew
from pcbnew import VECTOR2I, FromMM

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "hardware/surround.kicad_pcb"
X0 = Y0 = 20.0                  # outline origin, set by pcb_bootstrap.py
W, H = 101.88, 71.12             # must match the size given to pcb_bootstrap.py

# ---------------------------------------------------------------- anchors
UXc, UYc = W - 9.8, 24.77       # WROOM centre: keep-out edge = board edge
XC = 48.26                      # DAC socket column; bodies and outputs to the west
CF, CS = 12.70, 38.10           # front (A3) and surround (A4) module centres
XT = XC + 7.62                  # BCK trunk, between the pads of the parts east of the column
JX = 5.08                       # output terminal column
YR = 39.37                      # tops of the resistor row under the module
YA2 = 49.53                     # DIR9001 pigtail holes
YS = 67.31                      # south row: regulators and diodes
YQ = 58.42                      # second row above it: output caps and the DIR feed
YB = 60.96                      # the +3V3 bus between them
YEN = 53.34                     # EN lane, under the reset button
XP = 66.04                      # pot column
XV5 = 61.595                    # +5V on the top face


def upin(n):
    """(x, y) of a WROOM pad, antenna east, seen from the top of the board."""
    if n <= 14:
        return UXc + 8.25 - (n - 1) * 1.27, UYc + 8.75
    if n >= 25:
        return UXc + 8.25 - (38 - n) * 1.27, UYc - 8.75
    return UXc - 9.51, UYc + 5.71 - (n - 15) * 1.27


def ydac(cy, n):
    """y of pad n on a DAC socket column, pad 1 (VIN) at the south end."""
    return cy + 6.35 - (n - 1) * 2.54


def yrow(cy):
    """y of a DAC module's 1x9 row, on the north edge of the module."""
    return cy - 6.74


XSM = XC - 13 + 1.43            # x of pad 7 (XSMT) in the 1x9 row
XLO, XRO = XC - 13 - 13.81, XC - 13 - 8.73      # LOUT and ROUT

# U1 pad -> net, as the schematic assigns them. The floorplan depends on every
# one of these; check_pinmap() stops the build if the schematic drifts.
PINMAP = {
    "1": "GND", "15": "GND", "38": "GND",
    "2": "+3V3", "3": "EN",
    # south row, alternate pins: the DIR9001 lines and the pot
    "13": "DIR_BCK", "11": "DIR_LRCK", "9": "POT", "7": "Net-(U1-IO35)",
    # west column: the two free pins, one per DAC
    "24": "Net-(U1-IO2)",        # DIN front  -> R4 -> A3
    "16": "Net-(U1-IO13)",       # DIN surround -> R5 -> A4
    "23": "USER",                # IO15, in the pocket beside the data lines
    # north row
    "25": "BOOT", "28": "LED", "33": "XSMT", "34": "RXD0", "35": "TXD0",
}

# ref -> (pad number, x, y, rot): put that pad at that point, then rotate about it.
# rot 90 turns a part's +x axis to point north (KiCad turns counter-clockwise).
PLACE = {}


def dac_block(cy, dac, r_din, cap, r_feed):
    PLACE[dac] = ("1", XC, ydac(cy, 1), 180)
    PLACE[r_din] = ("2", XC + 3.81, ydac(cy, 4), 180)        # DIN, across the trunk
    PLACE[cap] = ("1", XT - 2.5, ydac(cy, 1), 0)             # VIN bulk, across the trunk
    PLACE[r_feed] = ("2", XC + 3.81, ydac(cy, 1) + 6.35, 180)  # 10 R feed, across the trunk


dac_block(CF, "A3", "R4", "C2", "R17")
dac_block(CS, "A4", "R5", "C3", "R18")

PLACE.update({
    # XSMT pull-down, between the modules: it lies across LRCK so that its ground
    # lead ties the copper between the sockets to the plane
    "R11": ("1", XC - 6.35, 28.575, 0),
    # ---- outputs, west edge: wire entry west, tip level with the DAC row
    "J3": ("T", JX, yrow(CF), 270),
    "J4": ("T", JX, yrow(CF) + 10.16, 270),
    "J5": ("T", JX, yrow(CS), 270),
    "J6": ("T", JX, yrow(CS) + 15.24, 270),
    "R6": ("2", 11.43, yrow(CS), 180),
    "R7": ("1", 11.43, yrow(CS) + 5.08, 0),
    "R8": ("2", 11.43, yrow(CS) + 15.24, 180),
    "R9": ("1", 11.43, yrow(CS) + 20.32, 0),
    # ---- DIR9001: resistor row under the module, pigtail below
    "R1": ("1", upin(13)[0] - 2.54, YR + 7.62, 90),
    "R2": ("1", upin(11)[0], YR + 7.62, 90),
    "R3": ("1", upin(7)[0], YR + 7.62, 90),
    "A2": ("6", upin(9)[0], YA2, 270),
    "C4": ("1", 76.20, 57.15, 0),
    # ---- pot: lane from pin 9, series resistor, header, in one column
    "R20": ("1", XP, 44.45, 270),
    "J7": ("1", XP + 2.54, 54.61, 270),
    "R19": ("1", XP - 2.54, YQ, 0),                 # +5V -> +5V_DIR, over the pot's 3V3
    # ---- ESP32 supply and reset, down the east edge
    "C9": ("1", upin(1)[0], 41.275, 90),        # its GND lead straight under pin 1
    "SW1": ("1", upin(3)[0], 50.80, 270),           # RESET
    "C11": ("1", 86.36, YEN, 270),
    "R14": ("1", 90.805, YB, 90),
    "C1": ("1", 98.83, 65.40, 180),
    # ---- supply: in at the south-west, regulators on the south edge, tabs out
    "J1": ("1", 5.08, 66.04, 0),
    "D2": ("2", 15.24, YS, 180),
    "C5": ("1", 29.21, YS, 0),
    "C6": ("1", 35.56, YS, 0),
    "U2": ("3", 44.45, YS, 180),
    "C8": ("1", 46.99, YQ, 0),
    # 100 n on +5V where it lands from the top face; its ground lead ties the copper
    # that LRCK and BCK fence in to the plane
    "C7": ("1", XV5, 46.99, 90),
    "D3": ("1", 60.96, YS, 0),
    "U3": ("3", 73.66, YS, 180),
    "R12": ("1", 73.66, 63.50, 0),
    "R13": ("1", 82.55, YS, 0),
    # ---- BOOT, status and power LEDs, UART: along the north edge
    "SW2": ("1", upin(25)[0], 12.20, 180),          # BOOT
    "R15": ("1", 66.04, 8.255, 0),
    "R10": ("1", upin(28)[0], 12.70, 90),
    "D1": ("1", 67.31, 4.445, 0),                   # status
    # ---- USER and the power LED, in the pocket between the two data lines
    "R16": ("1", 66.04, 17.78, 270),
    "D4": ("2", 66.04, 27.94, 90),
    "J2": ("1", upin(35)[0] + 1.27, 8.89, 270),
    "SW3": ("1", 76.20, 20.32, 270),
    # ---- scope ground loops
    "TP1": ("1", 84.455, 58.90, 0),                 # ties the reset parts' ground to the plane
    "TP2": ("1", 100.33, 12.70, 0),                # ties module pin 38 to the plane
})
HOLES = {"H1": (13.97, 11.04), "H2": (W - 3.6, 3.6), "H3": (17.0, 60.0), "H4": (56.0, 65.4)}


# ---------------------------------------------------------------- routing
XL = XC - 3.81                  # LRCK, up the west face of the socket column, a ground strip between
XK = 63.5                       # LRCK's way south, east of the feed resistors
YLK, YPT = YR + 2.54, YR + 5.08  # LRCK and pot lanes under the resistor row
YSL = 52.832                    # LRCK's lane round the south end of the column
YTOP = 1.905                    # XSMT's lane along the north edge
YRAIL = 69.85                   # +9V rail along the south edge


# Bottom-face lanes, as guide points the router must pass through; everything
# else is routed freely afterwards.
GUIDES = {
    # BCK: pin to its resistor, then one straight line west and up the trunk.
    "DIR_BCK": [["U1.13", (upin(13)[0], 36.83), "R1.2"],
                ["R1.2", (XT, YR), (XT, ydac(CS, 5)), (XT, ydac(CF, 5)), "A3.5"],
                [(XT, ydac(CS, 5)), "A4.5"]],
    # LRCK: under R1, down past the feed resistors, round the south end of the
    # column and up its west face to both modules.
    "DIR_LRCK": [["U1.11", "R2.2"],
                 ["R2.2", (upin(13)[0], YLK), (XK, YLK), (XK, YSL), (XL, YSL),
                  (XL, ydac(CS, 3)), (XL, ydac(CF, 3)), "A3.3"],
                 [(XL, ydac(CS, 3)), "A4.3"]],
    "POT": [["U1.9", (upin(9)[0], YLK), (upin(11)[0], YPT), (XP + 2.0, YPT), "R20.1"]],
    "Net-(U1-IO35)": [["U1.7", "R3.2"]],
    # the two data lines: mirror images about the module's centre line
    "Net-(U1-IO2)": [["U1.24", (80.5, upin(24)[1]), (72.9, ydac(CF, 4)), "R4.1"]],
    "Net-(U1-IO13)": [["U1.16", (80.5, upin(16)[1]), (72.9, ydac(CS, 4)), "R5.1"]],
    # XSMT: up the east edge, along the north edge, then down under both modules
    "XSMT": [["U1.33", (89.662, 10.9), (89.662, 5.0), (86.0, YTOP), (XSM, YTOP), "A3.7"],
             ["A3.7", (XSM, 28.575), "A4.7"], [(XSM, 28.575), "R11.1"]],
    "Net-(A3-OUTR)": [["A3.9", (XRO, yrow(CF) + 10.16), "J4.T"]],
    "Net-(A4-OUTR)": [["A4.9", (XRO, yrow(CS) + 15.24), "R8.1"]],
    # EN: straight down to the reset button, then west under it to its RC parts
    "EN": [["U1.3", (97.282, 35.3), (97.282, 48.0), (upin(3)[0], 50.8)], [(upin(3)[0], 50.8), (upin(3)[0], 57.3)],
           [(upin(3)[0], YEN), "R14.2", "C11.1"]],
    # +3V3: bypass cap at the pin, down the east edge, then one bus west to the
    # regulator, the protection diode and the pot header
    "+3V3": [["U1.2", (98.552, 35.3), (98.552, 39.6), "C9.1"],
             ["C9.1", (upin(1)[0], YB), (XP + 2.54, YB), "J7.1"],
             [(XP + 2.54, YB), "D3.2"],
             [(upin(1)[0], YB), "C1.1"],
             [(76.2, YB), "U3.2"], [(73.66, YB), "R12.1"]],
    # +9V: one rail along the south edge, under every part it feeds
    "+9V": [["D2.1", (25.4, YRAIL), (73.66, YRAIL), "U3.3"],
            [(29.21, YRAIL), "C5.1"], [(35.56, YRAIL), "C6.1"], [(49.53, YRAIL), "U2.1"],
            [(60.96, YRAIL), "D3.1"]],
    # +5V: out of the 7805, under its two caps, to the DIR9001 feed resistor
    "+5V_DIR": [["R19.2", "C4.1"], ["C4.1", "A2.1"]],
    "Net-(D2-A)": [["J1.1", (7.62, 63.246), (12.7, 63.246), "D2.2"]],
    "USER": [["U1.23", (76.2, 20.32)], [(76.2, 20.32), (76.2, 26.82)]],
    "+5V": [["U2.3", (44.45, YB), (61.5, YB), "R19.1"],
            [(46.99, YB), "C8.1"]],
}
FINISH = {"+3V3"}         # guided nets that still have pads for the router to add
ORDER = []                      # nets to route first, in this order
WIDTHS = {"EN": 0.5}             # slow, and it shares the east edge with +3V3 and the pin 1 ground
# Pads the bottom face does not reach: the top-face runs below serve them.
TOP_ONLY = {"+5V": ("R17.1", "R18.1", "C7.1"), "+3V3": ("R15.1", "R16.1")}
# Top-face runs. Each end is a lead soldered on both faces.
TOP_ROUTES = {
    "+5V": [["R19.1", (XV5, 55.6), "C7.1"],
            [(XV5, ydac(CS, 1) + 6.35), "R18.1"],
            ["C7.1", (62.992, 45.466), (62.992, 41.148), (XV5, 39.6), (XV5, ydac(CF, 1) + 6.35), "R17.1"]],
    "+3V3": [["C9.1", (98.298, 39.6), (98.298, 17.78), (70.0, 17.78), "R16.1"], ["R16.1", "R15.1"]],
}
TOP_WIDTHS = {"+3V3": 0.9}


def TOP_OK(ref):
    """True if a lead of this part can be soldered on the component side: the iron
    reaches an axial lead, a disc cap, a diode, an LED or a TO-220 leg. Sockets,
    headers, screw terminals, buttons and electrolytic cans sit on their holes."""
    if ref[0] in "RD" or ref.startswith("TP") or ref in ("U2", "U3"):
        return True
    return ref in ("C6", "C7", "C9")


# ---------------------------------------------------------------- silkscreen
# Etched by the fiber laser on the top face. (text, x, y, angle, size), fixed:
LABELS = [
    ("ESP32 SURROUND CARRIER  rev D", 34.5, 55.2, 0, 1.2),
    ("U2 7805", 46.99, 69.8, 0, 0.8),
    ("U3 LM317", 76.2, 69.8, 0, 0.8),
    ("WROOM-32 ON BACK", UXc - 1.0, UYc - 1.0, 0, 1.0),
    ("ANTENNA >", UXc + 4.0, UYc + 1.5, 0, 0.9),
    ("FRONT DAC", XC - 15.0, CF - 1.0, 0, 1.2),
    ("FACE DOWN", XC - 15.0, CF + 1.0, 0, 1.0),
    ("SURROUND DAC", XC - 15.0, CS - 1.0, 0, 1.2),
    ("FACE DOWN", XC - 15.0, CS + 1.0, 0, 1.0),
]
# (text, "REF.PAD" anchor, size, fixed): placed in the nearest free spot to that
# pad, or at a fixed (dx, dy, angle) from it. The terminals' free channel is east
# of the pins, inside the body; each pin is named there, reading upwards.
_E = (2.75, 0.0, 90)
PAD_LABELS = [
    ("+9V", "J1.1", 1.0, (0.0, -5.2, 0)), ("GND", "J1.2", 1.0, (0.0, -5.2, 0)),
    ("FL T", "J3.T", 0.8, _E), ("FL S", "J3.S", 0.8, _E),
    ("FR T", "J4.T", 0.8, _E), ("FR S", "J4.S", 0.8, _E),
    ("SL T", "J5.T", 0.8, _E), ("SL R", "J5.R", 0.8, _E), ("SL S", "J5.S", 0.8, _E),
    ("SR T", "J6.T", 0.8, _E), ("SR R", "J6.R", 0.8, _E), ("SR S", "J6.S", 0.8, _E),
    ("TX", "J2.1", 0.9, None), ("RX", "J2.2", 0.9, None), ("GND", "J2.3", 0.9, None),
    ("3V3", "J7.1", 0.9, None), ("W", "J7.2", 0.9, None), ("GND", "J7.3", 0.9, None), ("POT", "J7.2", 1.0, None),
    ("RESET", "SW1.1", 1.0, None), ("BOOT", "SW2.1", 1.0, None), ("USER", "SW3.1", 1.0, None),
    ("STATUS", "D1.1", 0.9, None), ("POWER", "D4.1", 0.9, None),
    ("VIN", "A3.1", 0.8, None), ("VIN", "A4.1", 0.8, None),
    ("GND", "TP1.1", 0.8, (2.7, 0.0, 0)), ("GND", "TP2.1", 0.8, None),
    # the DIR9001 pigtail, wire by wire: four names stand between the resistors
    # above their holes, the two that have a resistor above them sit below
    ("DAT", "A2.6", 0.8, (0.0, -2.75, 90)), ("BCK", "A2.4", 0.8, (0.0, -2.75, 90)),
    ("GND", "A2.2", 0.8, (0.0, -2.75, 90)), ("+5V", "A2.1", 0.8, (0.0, -2.75, 90)),
    ("LRC", "A2.5", 0.8, (0.0, 2.0, 0)), ("MCK", "A2.3", 0.8, (0.0, 2.0, 0)),
]
# References with no room beside the part, placed by hand; and those left out
# because a label already says what the part is.
REF_POS = {"C2": (XT, ydac(CF, 1) - 4.95, 0), "C3": (XT, ydac(CS, 1) - 4.95, 0),
           "C4": (73.4, 57.15, 90), "C1": (96.33, 59.6, 0), "A2": (75.2, YA2, 0),
           "C11": (83.2, 55.1, 90)}
REF_HIDE = {"J3", "J4", "J5", "J6", "TP1", "TP2", "U2", "U3"}


# ---------------------------------------------------------------- machinery
def mm(v):
    return FromMM(float(v))


def place(fps):
    u1 = fps["U1"]
    u1.SetPosition(VECTOR2I(mm(X0 + UXc), mm(Y0 + UYc)))
    if not u1.IsFlipped():
        u1.Flip(u1.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for rot in (0, 90, 180, 270):
        u1.SetOrientationDegrees(rot)
        ok = True
        for p in u1.Pads():
            n = p.GetNumber()
            if n.isdigit() and int(n) <= 38:
                x, y = upin(int(n))
                d = p.GetPosition()
                if abs(d.x - mm(X0 + x)) > 30000 or abs(d.y - mm(Y0 + y)) > 30000:
                    ok = False
                    break
        if ok:
            break
    else:
        sys.exit("U1: no orientation puts the pads where upin() says")
    for ref, (padnum, x, y, rot) in PLACE.items():
        fp = fps[ref]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
        pad = next(p for p in fp.Pads() if p.GetNumber() == padnum)
        d = pad.GetPosition() - fp.GetPosition()
        fp.SetPosition(VECTOR2I(mm(X0 + x) - d.x, mm(Y0 + y) - d.y))
    for ref, (x, y) in HOLES.items():
        fps[ref].SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))


def check_pinmap(fps):
    got = {p.GetNumber(): p.GetNetname() for p in fps["U1"].Pads() if p.GetNetname()}
    if got != PINMAP:
        diff = sorted(set(got.items()) ^ set(PINMAP.items()))
        sys.exit(f"U1 pins differ from PINMAP: {diff}")


# stacked terminal blocks butt; R13 ends at the bulk cap: the courtyards meet, the
# bodies clear by 0.4 mm
TOUCHING_OK = {frozenset(p) for p in (("J3", "J4"), ("J5", "J6"), ("C1", "R13"), ("J7", "R20"),
                                       ("C3", "C7"), ("C11", "TP1"), ("R14", "SW1"))}



def check_overlaps(fps):
    """Courtyard collisions, parts off the board, and through-hole pads that would
    land on the module, which sits under the board."""
    crt = {}
    for ref, fp in fps.items():
        c = fp.GetCourtyard(pcbnew.F_CrtYd)
        if ref != "U1" and c.OutlineCount():
            crt[ref] = c
    bad = []
    refs = sorted(crt)
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            if frozenset((a, b)) in TOUCHING_OK:
                continue
            if not crt[a].BBox().Intersects(crt[b].BBox()):
                continue
            x = pcbnew.SHAPE_POLY_SET(crt[a])
            x.BooleanIntersection(crt[b])
            if x.OutlineCount() and x.Area() > 1e9:          # > 0.001 mm^2
                bad.append((a, b, round(x.Area() / 1e12, 2)))
    body = pcbnew.BOX2I(VECTOR2I(mm(X0 + UXc - 9.88), mm(Y0 + UYc - 9.12)), VECTOR2I(mm(19.7), mm(18.24)))
    for ref, fp in fps.items():
        if ref == "U1":
            continue
        for pad in fp.Pads():
            pb = pad.GetBoundingBox()
            pb.Inflate(mm(0.5))
            if body.Intersects(pb):
                bad.append((ref, "U1 (pad over or beside the module)", 0))
                break
    for ref, c in crt.items():
        bb = c.BBox()
        if ref == "C9":                      # its courtyard, not its body, is 0.02 mm over the edge
            continue
        if bb.GetLeft() < mm(X0) or bb.GetTop() < mm(Y0) or bb.GetRight() > mm(X0 + W) or bb.GetBottom() > mm(Y0 + H):
            bad.append((ref, "board edge", 0))
    return bad


def check_tall(fps):
    """Cans, regulators, buttons and headers must clear the face-down DAC modules
    and their jacks, which are not courtyards, so DRC cannot see them."""
    for ref, fp in fps.items():
        if not (ref[0] in "CUJ" or ref.startswith("SW") or ref in ("D1", "D4")) or ref in ("U1",):
            continue
        bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        for cy in (CF, CS):
            for what, (x0, x1, y0, y1) in (("module", (XC - 30.08, XC + 0.88, cy - 8.49, cy + 8.62)),
                                           ("jack", (XC - 30.08, XC - 20.67, cy + 8.62, cy + 14.1))):
                if (bb.GetLeft() < mm(X0 + x1) and bb.GetRight() > mm(X0 + x0)
                        and bb.GetTop() < mm(Y0 + y1) and bb.GetBottom() > mm(Y0 + y0)):
                    print(f"WARNING {ref} is under the DAC {what} at y={cy}")


def main():
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        sys.exit("usage: surround_board.py [--place-only]")
    board = pcbnew.LoadBoard(str(BOARD))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    missing = [r for r in fps if r not in PLACE and r != "U1" and r not in HOLES]
    if missing:
        sys.exit(f"no placement for {missing}")
    place(fps)
    check_pinmap(fps)
    check_tall(fps)
    for a, b, area in check_overlaps(fps):
        print(f"OVERLAP {a} / {b} {area}")
    import silk
    left = silk.dress_silk(board, fps)
    if left:
        print(f"WARNING no clean silk spot for {left}")
    if "--place-only" in sys.argv:
        pcbnew.SaveBoard(str(BOARD), board)
        print("placed; not routed")
        return
    import route2
    route2.run(board, sys.modules[__name__])
    pcbnew.SaveBoard(str(BOARD), board)


if __name__ == "__main__":
    main()
