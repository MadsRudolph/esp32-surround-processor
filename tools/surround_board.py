#!/usr/bin/env python3
"""Place and route the ball-milled board: floorplan as code, copper by tools/octoroute.py.

    python3 tools/kpy.py tools/surround_board.py [--place-only]

Reads the bootstrapped hardware/surround.kicad_pcb (tools/pcb_bootstrap.py) and
writes it back placed, routed and with the ground pour filled. Every coordinate
is board-relative mm, outline origin top-left.

FLOORPLAN. The WROOM-32 sits on the milled side at the EAST edge with its antenna
pointing east, so the antenna keep-out starts exactly at the board edge and
nothing lies under it. Its castellation rows then face north and south into open
board, and its flash column (all NC) faces west:

  * north row, west to east: BOOT, LED, USER, DIN1, DIN2, XSMT ... RXD0, TXD0.
    The UI parts sit west of the module; the three DAC lines wrap over them to
    the DAC block, and the UART header sits north of the module's east end.
  * south row, east to west: GND, 3V3, EN, then the pot and the DIR9001 lines,
    which fan south into the DIR pigtail pads, the regulators and the 3V3/EN
    parts in the south-east.

The DAC block is the proven column: both modules face down in one line, BCK runs
up the east face of the column and LRCK up the west face. R4/R5 carry DIN across
the BCK run, R18 carries +5V_DAC2 across both clocks, and the output terminals
line the west edge.

THE ROUTING RULES are enforced by the router itself: every segment is horizontal,
vertical or 45 degrees, no run turns by more than 45 degrees, every net with a
pad on the ESP32 is 0.9 mm wide, power is 1.0 mm, everything else 0.5 mm, and
clearance is 0.50 mm (0.30 mm only between castellations and their escapes).
"""
import sys
from pathlib import Path
import pcbnew
from pcbnew import VECTOR2I, FromMM

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "hardware/surround.kicad_pcb"
X0 = Y0 = 20.0                  # outline origin, set by pcb_bootstrap.py
W, H = 103.0, 69.0               # must match the size given to pcb_bootstrap.py

# ---------------------------------------------------------------- anchors
UXc, UYc = W - 9.8, 19.5        # WROOM centre (keep-out edge = board edge)
XC = 48.0                       # DAC socket column; bodies and outputs to the west
YN, YS = 14.0, 37.0             # A4 (surround) and A3 (front) centres
JX = 6.0                        # output terminal column


def upin(n):
    """(x, y) of a WROOM pad, antenna east, seen from the top of the board."""
    if n <= 14:
        return UXc + 8.25 - (n - 1) * 1.27, UYc + 8.75
    if n >= 25:
        return UXc + 8.25 - (38 - n) * 1.27, UYc - 8.75
    return UXc - 9.51, UYc + 5.71 - (n - 15) * 1.27


def ydac(cy, n):
    """y of pad n on a DAC socket column, rotated so pad 1 is at the south end."""
    return cy + 6.35 - (n - 1) * 2.54


# U1 pad -> net, as the schematic assigns them. The floorplan depends on every
# one of these; check_pinmap() stops the build if the schematic drifts.
PINMAP = {
    "1": "GND", "15": "GND", "38": "GND",
    "2": "+3V3", "3": "EN",
    # north row, west to east: UI first, then the three DAC lines that wrap west
    "25": "BOOT", "26": "LED", "27": "USER",
    "28": "Net-(U1-IO17)",       # DIN1 -> R4 -> A3
    "30": "Net-(U1-IO18)",       # DIN2 -> R5 -> A4
    "31": "XSMT",
    "34": "RXD0", "35": "TXD0",
    # south row: pot, then the DIR9001 lines, spread 3.81 mm for the resistors
    "4": "POT",
    "6": "Net-(U1-IO34)",        # DOUT
    "9": "DIR_LRCK",
    "12": "DIR_BCK",
}

# ref -> (pad number, x, y, rot): put that pad at that point, then rotate about it.
# rot 90 turns a part's +x axis to point north (KiCad turns counter-clockwise).
PLACE = {
    # ---- DAC block: column at XC, bodies west, rows on their north edges
    "A4": ("1", XC, ydac(YN, 1), 180),
    "A3": ("1", XC, ydac(YS, 1), 180),
    "R5": ("2", XC + 5.0, ydac(YN, 4), 180),       # DIN2 across the BCK run
    "R4": ("2", XC + 5.0, ydac(YS, 4), 180),       # DIN1 across the BCK run
    "C3": ("1", XC + 3.0, 24.8, 0),                 # +5V_DAC2, between the modules
    "R18": ("1", XC + 2.6, YS + 5.35, 90),          # +5V_DAC2 across both clocks
    "R11": ("1", XC - 11.52, 26.0, 180),            # XSMT pull-down
    "R17": ("1", XC + 5.5, YS + 15.12, 90),         # +5V_DAC1, up to A3 VIN
    "C2": ("1", XC - 3.5, YS + 13.0, 0),
    # ---- outputs, west edge
    "J5": ("T", JX, YN, 90),
    "J6": ("T", JX, YN + 5.08, 270),
    "J3": ("T", JX, YS + 1.8, 90),
    "J4": ("T", JX, YS + 6.88, 270),
    "R6": ("1", 19.0, YN, 180),
    "R7": ("1", 11.2, YN - 5.08, 0),
    "R8": ("1", 19.0, YN + 5.08, 180),
    "R9": ("1", 11.2, YN + 10.16, 0),
    # ---- UI, between the DAC block and the module: buttons over LEDs
    "SW3": ("1", 69.1, 14.0, 270),                  # USER
    "SW2": ("1", 80.6, 14.0, 270),                  # BOOT
    "R10": ("1", 72.6, 13.0, 270),                  # status LED
    "D4": ("2", 66.0, 33.0, 180),                   # power
    "D1": ("2", 72.6, 24.0, 90),                    # status
    "R16": ("1", 66.0, 44.0, 90),                   # 3V3 up to D4, across the clocks
    "R15": ("1", 78.5, 44.0, 90),                   # BOOT pull-up, across the clocks
    # ---- UART, north of the module's east end
    "J2": ("1", W - 2.0, 7.08, 180),
    # ---- DIR9001 pigtail and its series resistors, below the module
    "R1": ("1", upin(12)[0], 39.0, 90),
    "R2": ("1", upin(9)[0], 41.0, 90),
    "R3": ("1", upin(6)[0], 39.0, 90),
    "A2": ("6", upin(6)[0], 45.5, 270),
    "R19": ("1", upin(6)[0] - 10.16, 55.62, 90),                 # +5V_DIR, under the pigtail's +5V
    "C4": ("1", 89.2, 51.5, 0),
    # ---- ESP32 3V3 bypass at pin 2; reset and pot west of the pigtail
    "C9": ("1", W - 1.7, 31.5, 270),
    "SW1": ("1", 71.0, 47.0, 0),                    # RESET
    "C11": ("1", 59.5, 51.0, 0),
    "R14": ("1", 66.5, 48.5, 270),
    "R20": ("1", 56.5, 59.0, 0),                    # pot wiper
    "J7": ("1", 81.5, 52.0, 0),
    # ---- supply: in at the south-west, regulators on the south edge, tabs out
    "J1": ("1", 4.0, 64.0, 0),
    "D2": ("1", 14.5, 64.0, 0),
    "C5": ("1", 29.0, 64.0, 0),
    "C6": ("1", 35.0, 64.0, 0),
    "U2": ("1", 45.0, 65.5, 0),
    "C7": ("1", 54.0, 64.0, 0),
    "C8": ("1", 62.0, 64.0, 0),
    "C1": ("1", 87.0, 62.5, 0),
    "U3": ("1", 74.0, 65.6, 0),
    "R12": ("2", 74.0, 60.55, 180),
    "R13": ("1", 69.5, 67.0, 90),
    "D3": ("2", W - 1.7, 47.0, 270),
    # ---- scope ground
    "TP1": ("1", 30.0, 3.0, 0),
    "TP2": ("1", 30.0, 57.5, 0),
}
HOLES = {"H1": (14.0, 3.6), "H2": (W - 4.0, H - 4.0), "H3": (4.5, 55.5), "H4": (40.0, 57.5)}


# Lanes for the nets whose order matters, as guide points the router must pass
# through; everything else is routed freely afterwards. North bundle at 1.524 mm
# pitch on the grid rows above the module: BOOT lowest, XSMT on top.
def _row(k):
    return UYc - 8.75 - k * 0.254


GUIDES = {
    "XSMT": [["U1.31", (upin(31)[0], _row(36)), (XC - 11.52, _row(36)), "A4.7"], ["A4.7", "A3.7"],
             [(XC - 11.52, 26.0), "R11.1"]],
    "Net-(U1-IO18)": [["U1.30", (upin(30)[0], _row(30)), (XC + 12.62, _row(30)), "R5.1"]],
    "Net-(U1-IO17)": [["U1.28", (upin(28)[0], _row(24)), (XC + 14.5, _row(24)), (XC + 14.5, YS - 3.5), "R4.1"]],
    "USER": [["U1.27", (upin(27)[0], _row(18)), (69.1, _row(18)), "SW3.1"]],
    "LED": [["U1.26", (upin(26)[0], _row(12)), (72.6, _row(12)), "R10.1"]],
    "BOOT": [["U1.25", (upin(25)[0], _row(6)), (80.6, _row(6)), "SW2.1"], [(80.6, 20.5), "R15.2"]],
    "TXD0": [["U1.35", (upin(35)[0], 7.08), "J2.1"]],
    "RXD0": [["U1.34", (upin(34)[0], 4.54), "J2.2"]],
    "Net-(U1-IO34)": [["U1.6", "R3.2"]],
    # BCK: down to R1, then west through the gaps in R15 and R16 to the east face
    # of the DAC column, up to the surround DAC and across to the front one.
    "DIR_BCK": [["U1.12", "R1.2"],
                [(upin(12)[0], 30.2), (78.5, 39.3), (XC + 10.5, 39.3), (XC + 10.5, ydac(YN, 5)), "A4.5"],
                [(XC + 10.5, ydac(YS, 5)), "A3.5"]],
    # LRCK: through the gap in R1, under BCK, round the south end of the column to
    # A3.3, and up the west face to A4.3.
    "DIR_LRCK": [["U1.9", "R2.2"],
                 [(upin(9)[0], 32.0), (upin(12)[0], 33.4), (78.5, 41.0), (XC + 3.0, 40.6), "A3.3"],
                 ["A3.3", (XC - 2.5, ydac(YS, 3)), (XC - 2.5, ydac(YN, 3)), "A4.3"]],
}


# ---------------------------------------------------------------- machinery
def mm(v):
    return FromMM(float(v))


def place(fps):
    # The module goes on the milled side, seen through the board from the top,
    # then turns until every pad lands where upin() says.
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
    """The schematic (tools/make_symbols.py + surround_layout.py) owns the GPIO
    choice; this floorplan depends on it, so stop if the two have drifted."""
    got = {p.GetNumber(): p.GetNetname() for p in fps["U1"].Pads() if p.GetNetname()}
    if got != PINMAP:
        diff = sorted(set(got.items()) ^ set(PINMAP.items()))
        sys.exit(f"U1 pins differ from PINMAP: {diff}")


# Footprint pairs whose courtyards touch on purpose: stacked screw terminals, and
# R18, which runs beside the DAC column to carry +5V_DAC2 across both clocks.
TOUCHING_OK = {frozenset(p) for p in (("J5", "J6"), ("J3", "J6"), ("J3", "J4"),
                                       ("R18", "A3"), ("R18", "R4"), ("R18", "C3"),
                                       # buttons either side of the status LED: the
                                       # courtyards meet, the bodies clear by 1 mm
                                       ("SW3", "D1"), ("SW3", "R10"), ("SW2", "D1"), ("SW2", "R10"))}


def check_overlaps(fps):
    """Courtyard collisions (real outlines, not boxes), parts off the board, and
    through-hole pads that would land on the module, which sits under the board."""
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
                bad.append((a, b))
    body = pcbnew.BOX2I(VECTOR2I(mm(X0 + UXc - 9.88), mm(Y0 + UYc - 9.12)), VECTOR2I(mm(19.7), mm(18.24)))
    for ref, fp in fps.items():
        if ref == "U1":
            continue
        for pad in fp.Pads():
            pb = pad.GetBoundingBox()
            pb.Inflate(mm(0.5))
            if body.Intersects(pb):
                bad.append((ref, "U1 (pad over or beside the module)"))
                break
    for ref, c in crt.items():
        bb = c.BBox()
        if bb.GetLeft() < mm(X0) or bb.GetTop() < mm(Y0) or bb.GetRight() > mm(X0 + W) or bb.GetBottom() > mm(Y0 + H):
            bad.append((ref, "board edge"))
    return bad


def check_tall(fps):
    """Cans and regulators must clear the face-down DAC modules and their jacks,
    which are not courtyards, so DRC cannot see them."""
    for ref in ("C1", "C2", "C3", "C4", "C5", "C8", "C11", "U2", "U3", "J1", "J2", "J7",
                "SW1", "SW2", "SW3", "D1", "D4"):
        bb = fps[ref].GetCourtyard(pcbnew.F_CrtYd).BBox()
        for cy in (YN, YS):
            for what, (x0, x1, y0, y1) in (("module", (XC - 30.08, XC + 0.88, cy - 8.49, cy + 8.62)),
                                           ("jack", (XC - 30.08, XC - 20.67, cy + 8.62, cy + 14.1))):
                if (bb.GetLeft() < mm(X0 + x1) and bb.GetRight() > mm(X0 + x0)
                        and bb.GetTop() < mm(Y0 + y1) and bb.GetBottom() > mm(Y0 + y0)):
                    print(f"WARNING {ref} is under the DAC {what} at y={cy}")


def gnd_islands(board):
    """GND pour islands as lists of the GND pads each one touches."""
    zone = next(z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND")
    fill = zone.GetFilledPolysList(pcbnew.B_Cu)
    gpads = [(f"{fp.GetReference()}.{p.GetNumber()}", p) for fp in board.GetFootprints()
             for p in fp.Pads() if p.GetNetname() == "GND" and p.IsOnLayer(pcbnew.B_Cu)]
    out = []
    for i in range(fill.OutlineCount()):
        out.append([(k, p) for k, p in gpads if fill.Outline(i).PointInside(p.GetPosition())])
    return [isl for isl in out if isl]


def _seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def link_islands(board, max_len=30.0):
    """Join the GND islands with the shortest pad-to-pad wire links, drawn on F.Cu
    so DRC and tools/wire_links.py see them. A link may not pass over any other
    through-hole pad. Returns the links made."""
    isl = gnd_islands(board)
    group = {}
    for g, members in enumerate(isl):
        for k, _ in members:
            group.setdefault(k, g)
    parent = list(range(len(isl)))

    def find(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    obstacles = []
    for fp in board.GetFootprints():
        for q in fp.Pads():
            if q.GetNetname() != "GND" and q.IsOnLayer(pcbnew.F_Cu):
                c = q.GetPosition()
                r = pcbnew.ToMM(max(q.GetSize(pcbnew.F_Cu).x, q.GetSize(pcbnew.F_Cu).y)) / 2
                obstacles.append(((pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)), r))
    pads = [(k, p, (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)))
            for members in isl for k, p in members]
    cands = []
    for i, (ka, pa, a) in enumerate(pads):
        for kb, pb, b in pads[i + 1:]:
            if group[ka] == group[kb]:
                continue
            d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            if d > max_len:
                continue
            if any(_seg_dist(c, a, b) < r + 0.25 + 0.5 for c, r in obstacles):
                continue
            cands.append((d, ka, pa, kb, pb))
    cands.sort(key=lambda c: c[0])
    made = []
    for d, ka, pa, kb, pb in cands:
        ga, gb = find(group[ka]), find(group[kb])
        if ga == gb:
            continue
        parent[ga] = gb
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pa.GetPosition()); t.SetEnd(pb.GetPosition())
        t.SetWidth(mm(0.5)); t.SetLayer(pcbnew.F_Cu); t.SetNet(pa.GetNet())
        board.Add(t)
        made.append((ka, kb, d))
    left = len({find(g) for g in range(len(isl))})
    if left > 1:
        print(f"WARNING {left} GND islands could not be joined by a clean link")
    return made


# ---------------------------------------------------------------- silkscreen
# The fiber laser etches F.Silkscreen only, top side, unmirrored. Every reference
# goes in the first free spot beside or on its own part; function labels say what
# each connector pin, button and LED is. Values live on F.Fab, out of the etch.
SILK_H, SILK_W = 1.0, 0.15
LABELS = [
    # (text, x, y, angle, size) in board mm, fixed
    ("ESP32 SURROUND CARRIER  rev C", 30.0, H - 1.6, 0, 1.2),
    ("WROOM-32 ON BACK", UXc - 1.0, UYc - 1.0, 0, 1.0),
    ("ANTENNA >", UXc + 4.0, UYc + 1.5, 0, 0.9),
    ("SURROUND DAC", XC - 15.0, YN - 1.0, 0, 1.2),
    ("FRONT DAC", XC - 15.0, YS - 1.0, 0, 1.2),
    ("FACE DOWN", XC - 15.0, YN + 1.0, 0, 1.0),
    ("FACE DOWN", XC - 15.0, YS + 1.0, 0, 1.0),
    ("LM317", 83.0, 64.0, 90, 1.0),
    ("C1", 86.3, 59.2, 0, 1.0),
]
# (text, "REF.PAD" anchor, size, fixed): placed in the nearest free spot to that pad,
# or at a fixed (dx, dy, angle) from it when the spot is known.
# Screw terminals: the free channel inside the body is west of the pins on the
# blocks turned 90 degrees and east of them on those turned 270 (the internal rail
# is on the other side). Each pin is named there, reading upwards.
_W, _E = (-2.75, 0.0, 90), (2.75, 0.0, 90)
PAD_LABELS = [
    ("+9V", "J1.1", 1.0, None), ("GND", "J1.2", 1.0, None),
    ("SL T", "J5.T", 0.8, _W), ("SL R", "J5.R", 0.8, _W), ("SL S", "J5.S", 0.8, _W),
    ("SR T", "J6.T", 0.8, _E), ("SR R", "J6.R", 0.8, _E), ("SR S", "J6.S", 0.8, (2.75, -0.9, 90)),
    ("FL T", "J3.T", 0.8, _W), ("FL S", "J3.S", 0.8, (-2.75, 0.9, 90)),
    ("FR T", "J4.T", 0.8, _E), ("FR S", "J4.S", 0.8, _E),
    ("TX", "J2.1", 0.9, None), ("RX", "J2.2", 0.9, None), ("GND", "J2.3", 0.9, None),
    ("3V3", "J7.1", 0.9, None), ("W", "J7.2", 0.9, None), ("GND", "J7.3", 0.9, None), ("POT", "J7.2", 1.0, None),
    ("RESET", "SW1.1", 1.0, None), ("BOOT", "SW2.1", 1.0, None), ("USER", "SW3.1", 1.0, None),
    ("STATUS", "D1.1", 0.9, None), ("POWER", "D4.1", 0.9, None),
    ("7805", "U2.2", 1.0, None),
    ("VIN", "A4.1", 0.8, None), ("VIN", "A3.1", 0.8, None),
]


def _box(t):
    b = t.GetBoundingBox()
    return (pcbnew.ToMM(b.GetLeft()) - X0, pcbnew.ToMM(b.GetTop()) - Y0,
            pcbnew.ToMM(b.GetRight()) - X0, pcbnew.ToMM(b.GetBottom()) - Y0)


def _hit(a, b, m=0.0):
    return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]


def dress_silk(board, fps):
    blocked = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            b = pad.GetBoundingBox()
            blocked.append((pcbnew.ToMM(b.GetLeft()) - X0, pcbnew.ToMM(b.GetTop()) - Y0,
                            pcbnew.ToMM(b.GetRight()) - X0, pcbnew.ToMM(b.GetBottom()) - Y0))
    def seg_box(a, b, w=0.15):
        return (min(a[0], b[0]) - w, min(a[1], b[1]) - w, max(a[0], b[0]) + w, max(a[1], b[1]) + w)

    def silk_shapes(items):
        out = []
        for g in items:
            if g.GetLayer() != pcbnew.F_SilkS or not isinstance(g, pcbnew.PCB_SHAPE):
                continue
            st = g.GetShape()
            if st in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY):
                pts = [g.GetRectCorners()[i] for i in range(4)] if st == pcbnew.SHAPE_T_RECT else \
                    [g.GetPolyShape().COutline(0).CPoint(i) for i in range(g.GetPolyShape().COutline(0).PointCount())]
                pts = [(pcbnew.ToMM(v.x) - X0, pcbnew.ToMM(v.y) - Y0) for v in pts]
                out += [seg_box(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
            elif st == pcbnew.SHAPE_T_SEGMENT:
                a = g.GetStart(); b = g.GetEnd()
                out.append(seg_box((pcbnew.ToMM(a.x) - X0, pcbnew.ToMM(a.y) - Y0), (pcbnew.ToMM(b.x) - X0, pcbnew.ToMM(b.y) - Y0)))
            else:
                bb = g.GetBoundingBox()
                out.append((pcbnew.ToMM(bb.GetLeft()) - X0, pcbnew.ToMM(bb.GetTop()) - Y0,
                            pcbnew.ToMM(bb.GetRight()) - X0, pcbnew.ToMM(bb.GetBottom()) - Y0))
        return out

    for fp in board.GetFootprints():
        blocked += silk_shapes(fp.GraphicalItems())
    placed = []

    def free(box, m=0.35):
        if box[0] < 0.6 or box[1] < 0.6 or box[2] > W - 0.6 or box[3] > H - 0.6:
            return False
        return not any(_hit(box, b, m) for b in blocked) and not any(_hit(box, b, m + 0.05) for b in placed)

    # labels first: they are where they must be
    for text, x, y, ang, size in LABELS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(SILK_W))
        t.SetTextAngleDegrees(ang); t.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
        board.Add(t)
        placed.append(_box(t))
    # module outline: it sits on the back, so its shape helps when fitting the sockets
    for (xa, ya, xb, yb) in ((UXc - 9.88, UYc - 9.12, W - 0.3, UYc - 9.12), (UXc - 9.88, UYc + 9.12, W - 0.3, UYc + 9.12),
                             (UXc - 9.88, UYc - 9.12, UXc - 9.88, UYc + 9.12)):
        ln = pcbnew.PCB_SHAPE(board)
        ln.SetShape(pcbnew.SHAPE_T_SEGMENT); ln.SetLayer(pcbnew.F_SilkS); ln.SetWidth(mm(0.15))
        ln.SetStart(VECTOR2I(mm(X0 + xa), mm(Y0 + ya))); ln.SetEnd(VECTOR2I(mm(X0 + xb), mm(Y0 + yb)))
        board.Add(ln)
        blocked.append(seg_box((xa, ya), (xb, yb)))
    pads = {f"{fp.GetReference()}.{q.GetNumber()}": q for fp in board.GetFootprints() for q in fp.Pads()}
    unplaced = []
    for text, key, size, fixed in PAD_LABELS:
        q = pads[key]
        px, py = pcbnew.ToMM(q.GetPosition().x) - X0, pcbnew.ToMM(q.GetPosition().y) - Y0
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(SILK_W))
        ok = False
        if fixed:
            dx, dy, ang = fixed
            # the stacked terminals alternate direction: follow the pin order
            t.SetTextAngleDegrees(ang)
            t.SetPosition(VECTOR2I(mm(X0 + px + dx), mm(Y0 + py + dy)))
            t.SetTextThickness(mm(0.12))
            ok = free(_box(t), m=0.05)
        else:
            for sz in (size, 0.8):
                t.SetTextSize(VECTOR2I(mm(sz), mm(sz)))
                w = len(text) * sz * 0.45
                for ang in (0, 90):
                    t.SetTextAngleDegrees(ang)
                    along, across = (w, 0.0) if ang == 0 else (0.0, w)
                    for rad in (1.8, 2.6, 3.4, 4.4, 5.6, 7.0):
                        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0.7, -0.7), (-0.7, -0.7), (0.7, 0.7), (-0.7, 0.7)):
                            x = px + dx * (rad + (along if dx else 0)); y = py + dy * (rad + (across if dy else 0))
                            t.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
                            if free(_box(t)):
                                ok = True
                                break
                        if ok:
                            break
                    if ok:
                        break
                if ok:
                    break
        if ok:
            board.Add(t)
            placed.append(_box(t))
        else:
            unplaced.append(f"label {text}@{key}")
    for ref in sorted(fps, key=lambda r: -fps[r].GetCourtyard(pcbnew.F_CrtYd).BBox().GetArea()
                      if fps[r].GetCourtyard(pcbnew.F_CrtYd).OutlineCount() else 0):
        fp = fps[ref]
        r = fp.Reference()
        if ref == "U1":                      # on the back: its texts stay there
            r.SetVisible(False)
            continue
        fp.Value().SetLayer(pcbnew.F_Fab)
        if ref.startswith("H"):
            r.SetVisible(False)
            continue
        r.SetVisible(True); r.SetLayer(pcbnew.F_SilkS)
        r.SetTextSize(VECTOR2I(mm(SILK_H), mm(SILK_H))); r.SetTextThickness(mm(SILK_W))
        r.SetKeepUpright(True)
        c = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False)
        x0, y0 = pcbnew.ToMM(bb.GetLeft()) - X0, pcbnew.ToMM(bb.GetTop()) - Y0
        x1, y1 = pcbnew.ToMM(bb.GetRight()) - X0, pcbnew.ToMM(bb.GetBottom()) - Y0
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if "CP_Radial" in str(fp.GetFPID().GetLibItemName()):
            # in the clear half of the can's outline, above the + pad
            inside = [(x0 + 0.3 * (x1 - x0), y0 + 2.0, 0)] if x1 - x0 > 9.0 else []
        else:
            inside = [(cx, cy, 0), (cx, cy, 90), (cx, y0 + 1.1, 0), (cx, y1 - 1.1, 0)]
        cands = inside + [(cx, y0 - 0.8, 0), (cx, y1 + 0.8, 0),
                 (x0 - 0.8, cy, 90), (x1 + 0.8, cy, 90), (x0 - 2.0, cy, 0), (x1 + 2.0, cy, 0)]
        for dx in (-2.0, 2.0, -4.0, 4.0):
            cands += [(cx + dx, y0 - 0.8, 0), (cx + dx, y1 + 0.8, 0)]
        for dy in (-2.0, 2.0, -4.0, 4.0):
            cands += [(x0 - 0.8, cy + dy, 90), (x1 + 0.8, cy + dy, 90)]
        for x, y, ang in cands:
            r.SetTextAngleDegrees(ang)
            r.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
            if free(_box(r)):
                placed.append(_box(r))
                break
        else:
            # one more round at 0.8 mm before giving up
            r.SetTextSize(VECTOR2I(mm(0.8), mm(0.8))); r.SetTextThickness(mm(0.12))
            for x, y, ang in cands:
                r.SetTextAngleDegrees(ang)
                r.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
                if free(_box(r)):
                    placed.append(_box(r))
                    break
            else:
                unplaced.append(ref)
                r.SetVisible(False)          # better no reference than one on a pad
    return unplaced


def main():
    board = pcbnew.LoadBoard(str(BOARD))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    missing = [r for r in fps if r not in PLACE and r != "U1" and r not in HOLES]
    if missing:
        sys.exit(f"no placement for {missing}")
    place(fps)
    check_pinmap(fps)
    check_tall(fps)
    left = dress_silk(board, fps)
    if left:
        print(f"WARNING no clean silk spot for {left}")
    for a, b in check_overlaps(fps):
        print(f"OVERLAP {a} / {b}")
    if "--place-only" in sys.argv:
        pcbnew.SaveBoard(str(BOARD), board)
        print("placed; not routed")
        return
    import autoroute as ar
    import octoroute as oc
    keepouts = [(UXc - 8.7, UYc - 8.0, W + 1.0, UYc + 8.0)]          # under the module
    escapes = [(UXc - 9.2, UYc - 12.5, W, UYc - 8.0),                 # north row
               (UXc - 9.2, UYc + 8.0, W, UYc + 12.5),                 # south row
               (UXc - 13.0, UYc - 7.0, UXc - 8.7, UYc + 7.0)]         # flash column
    origin = ((UXc + 8.25) % oc.G, (UYc - 8.75) % oc.G)
    r, failed, (bx, by) = ar.route_board(board, keepouts, escapes, origin, guides=GUIDES)
    ar.write_tracks(board, r, bx, by)
    ar.add_rule_areas(board, r.escape, bx, by)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for a_, b_, d in link_islands(board):
        print(f"GND link {a_} -> {b_}: {d:.1f} mm")
    pcbnew.SaveBoard(str(BOARD), board)
    print(f"routed; left for hand routing: {failed}")


if __name__ == "__main__":
    main()
