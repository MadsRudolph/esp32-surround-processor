"""Enclosure for the ESP32 4.0 surround processor. Run: python3 enclosure/design.py

Parametric FreeCAD model driven from the KiCad board (cad/board_data.json and
cad/board.step, both written by board_export.py). Two printed parts, Base and
User_Button, and a flat lid laser cut from 4 mm clear acrylic (lasercut/).

Frame: millimetres, origin at the board's south-west corner, X east, Y north,
Z up, Z = 0 at the bottom face of the board. The board keeps the orientation it
has in KiCad. West wall = rear panel (all connectors), east wall = front (the
antenna sits behind it, the volume knob at its south end), lid = LEDs and buttons.

The DIR9001 module is stacked over the west end of the carrier, as in the built
unit, but TURNED 180 DEGREES AND MOVED WEST so its sockets and toggle reach the
rear wall. On the bench it sits with the sockets pointing east over the board,
where no panel can reach them. Mads has agreed to re-mount it this way.

The module's outline, holes and sockets come from the seller's dimension drawing.
The photos of the built board had no ruler in frame; values marked "photo
estimate" were scaled from them and are good to a few millimetres at best.
Every dimension that is not taken from the KiCad board is in the block below,
marked with where it comes from.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, '/usr/lib/freecad/lib')
import FreeCAD as A
import Part, MeshPart

ROOT = Path(__file__).resolve().parent
V = A.Vector
BOARD = json.loads((ROOT / 'cad' / 'board_data.json').read_text())
P, HOLES = BOARD['parts'], BOARD['holes']
BOARD_X, BOARD_Y = BOARD['size_mm']
NAMES = ['Base', 'Lid_Plate', 'User_Button']   # the lid plate is laser cut, not printed
PRINTED = ['Base', 'User_Button']

# =============================================================================
# PRINT AND FIT. Design choices, safe to change.
# =============================================================================
WALL = 2.4               # side walls, 6 perimeters of a 0.4 mm nozzle
FLOOR = 2.4
CORNER_R = 4.0           # outer vertical corner radius
HEADROOM = 2.0           # air between the tallest part and the lid
BOARD_GAP_N = 2.5        # board north edge to wall
ANTENNA_GAP = 2.5        # antenna tip to the inside of the front wall
ANTENNA_WALL = 1.2       # wall and floor thickness in front of and under the antenna
ANTENNA_MARGIN = 4.0     # the thin patch extends this far past the module on each side
POST = 9.0               # square boss in each corner for a lid insert: 2.4 mm of plastic round the pilot
FLOOR_PAD_D, FLOOR_PAD_H = 11.0, 1.6   # thicker floor under each carrier standoff, for the countersunk screw
SOUTH_BAY = 29.5         # board south edge to the wall: heatsink overhang, 9 V jack, pot
PILLAR_D, PILLAR_BASE_D = 8.0, 12.0    # printed pillars under the DIR9001 module
VENT_W, VENT_PITCH = 3.0, 6.0   # slots in the floor and in the acrylic; 3 mm of acrylic between slots
# --- laser-cut lid
PLATE_T = 4.0            # clear acrylic sheet, per Mads. Cast sheet varies by a few tenths
PLATE_INSET = 0.5        # plate edge inside the outline of the base, all round
LASER_KERF = 0.20        # CO2 laser on 4 mm acrylic, typical 0.15 to 0.25. CHECK WITH A TEST CUT.
                         # The cut file is drawn compensated: holes and slots smaller, outline larger, by half of this per side.
                         # Set to 0 if the laser software does its own kerf offset.
PLATE_SCREW_D = 3.4      # M3 clearance holes in the plate
PIN_HOLE_D = 2.2         # BOOT and RESET: a straight 2 mm pin or a paperclip, 32 mm down to the switch
LED_HOLE_D = 3.2         # optional layer only: holes over the LEDs for an OPAQUE plate. Not for clear acrylic
ENGRAVE_H, ENGRAVE_TITLE_H = 2.6, 4.0   # label and product-name letter height
PRODUCT_NAME = 'SURROUND 4.0'
# --- USER button cap: a loose printed part held by the switch below and the plate above
BTN_D = 6.0              # stem
BTN_HOLE_D = 6.6         # hole in the plate
BTN_SKIRT_OD = 10.5      # skirt that slips over the switch body; too wide to pass the plate hole
BTN_SKIRT_FIT = 0.4      # skirt to switch body, in total
BTN_SKIRT_OVERLAP = 1.5  # how far the skirt reaches down the switch body
BTN_PROUD = 1.5          # stem above the plate
BTN_COLLAR_D = 9.0       # collar on the stem just under the plate
BTN_LIFT = 1.0           # how far the cap can lift before the collar meets the plate; less than the skirt overlap
INSERT_LEADIN = 0.6      # chamfer at the mouth of every insert pocket

# =============================================================================
# NOT FROM KICAD. Nothing below has been measured on the real parts.
# ASSUMED = a guess, a catalogue value or a photo estimate. "seller drawing" =
# the DIR9001 module's dimension drawing. Replace the assumed ones with caliper
# values, then re-run design.py and validate.py.
# =============================================================================
# --- the carrier board as built
BOARD_T = 1.6                 # ASSUMED: copper-clad stock from the build notes, not measured
CARRIER_STANDOFF_LEN = 10.0   # ASSUMED (photo estimate): the four black hex standoffs already under H1 to H4. Must exceed 3.2 (WROOM-32)
CARRIER_STANDOFF_AF = 5.5     # ASSUMED: across flats
LEAD_TRIM = 2.5               # ASSUMED: longest lead or solder cone under the board
HS_TOP_ABOVE_BOARD = 26.0     # ASSUMED: top of an LM317 heatsink above the board top. None is fitted in the photos. The TO-220 itself is 18.9 in the KiCad model
DAC_TOP_ABOVE_BOARD = 14.0    # ASSUMED: PCM5102 module on its socket (8.5 socket + 2.5 header spacer + 1.6 board + margin)
TERMINAL_H = 10.5             # ASSUMED: screw terminal height (no 3D model on this machine)
CAP_C1_H, CAP_SMALL_H = 16.0, 12.0   # ASSUMED: real can heights; KiCad models are 11.6 and 9.6 with the board
LED_TOP_ABOVE_BOARD = 6.0     # ASSUMED: top of the 3 mm LED domes
TACT_TOP_ABOVE_BOARD = 4.3    # ASSUMED: tact switch plunger top, from the KiCad SW_PUSH_6mm model. Tall-stem switches differ
TACT_BODY, TACT_BODY_H = 6.2, 3.5   # ASSUMED: 6 mm tact switch body, square, and its height above the board
# --- LM317 heatsink (bolted to the tab, hanging over the south edge)
HS_W, HS_D = 22.0, 14.0       # ASSUMED: width along the board edge, depth out from the tab
HS_BOTTOM_ABOVE_BOARD = 3.0   # ASSUMED

# --- DIR9001 MODULE (LHY AUDIO DIR9001-I2S) -----------------------------------
# "seller drawing" = read off the seller's dimension drawing of this module.
# "scaled" = not dimensioned on that drawing, measured from its proportions.
# Neither has been checked with calipers on the real module. The rest is ASSUMED.
# TOSLINK, toggle and coax RCA are on one 64 mm edge, I2S-OUT on the opposite edge.
DIR_W = 64.0                  # seller drawing: the edge that carries TOSLINK, toggle and RCA
DIR_L = 48.0                  # seller drawing: board depth without connector overhang
DIR_T = 1.6                   # seller drawing
DIR_HOLE_PITCH_W = 56.0       # seller drawing: hole spacing along the connector edge, 4.0 in from each end
DIR_HOLE_PITCH_L = 24.5       # seller drawing: hole spacing front to back
DIR_HOLE_FROM_EDGE = 19.5     # seller drawing: connector edge to the nearer hole row (48.0 - 4.0 - 24.5)
# positions along the connector edge are measured from the corner at the TOSLINK end
DIR_OPT_U = 9.0               # scaled: TOSLINK centre. The drawing gives only the 23.0 spacings
DIR_TOGGLE_U = DIR_OPT_U + 23.0   # seller drawing: 23.0 from the TOSLINK; lands on the middle of the edge
DIR_RCA_U = DIR_TOGGLE_U + 23.0   # seller drawing: 23.0 from the toggle
DIR_OPT_BODY_W, DIR_OPT_BODY_H = 10.8, 10.8   # seller drawing: TOSLINK receiver body
DIR_OPT_ZC = 5.6              # seller drawing: taken as the height of the optical axis above the module's top face
                              # (the "0.56 cm" arrow ends at mid-height of the body)
DIR_TOGGLE_BUSH_D = 5.5       # seller drawing: toggle bushing
DIR_TOGGLE_ZC = 3.0           # seller drawing: toggle axis above the module's top face
DIR_RCA_BARREL_D = 9.0        # seller drawing
DIR_RCA_ZC = 6.3              # seller drawing: RCA centre above the module's top face
DIR_OPT_OVERHANG = 2.5        # scaled: TOSLINK front past the board edge
DIR_TOGGLE_BUSH_OVERHANG = 2.5   # scaled: bushing end past the board edge
DIR_TOGGLE_TIP_OVERHANG = 8.0    # scaled: lever tip past the board edge
DIR_CONN_OVERHANG = 9.6       # scaled: RCA barrel past the board edge
DIR_I2S_U = 33.0              # scaled: centre of the I2S-OUT connector along its edge, from the TOSLINK end
DIR_COMP_H = 12.9             # ASSUMED (reseller listing): tallest part above its board (14.5 overall less the board)
DIR_ABOVE_BOARD = 20.0        # ASSUMED (photo estimate): underside of the module above the carrier's top face,
                              # which is the length of the standoff on top of H3
DIR_STANDOFF_AF = 5.5         # ASSUMED: across flats
# openings in the rear wall (design choices that follow from the values above)
DIR_EDGE_GAP = 1.0            # connector edge of the board to the inside of the rear wall
DIR_OPT_W, DIR_OPT_H = 11.8, 11.6   # TOSLINK window: the receiver body stands 1.5 mm into it
DIR_TOGGLE_HOLE_D = 6.5       # round the toggle bushing; the lever swings sideways
DIR_RCA_HOLE_D = 10.5         # round the RCA barrel
PANEL_RECESS_D, PANEL_RECESS = 16.0, 1.2   # shallow outside recess round the toggle and the RCA, for fingers and the plug shell
# -------------------------------------------------------------------------------

# --- panel parts (none bought or measured yet)
RCA_HOLE_D = 6.4              # ASSUMED: gold RCA panel jack, 1/4 inch thread. Insulated types need 8 to 10 mm
TRS_HOLE_D = 9.5              # ASSUMED: 6.35 mm jack, 3/8 inch thread. Use 6.2 for a 3.5 mm jack
DC_HOLE_D = 8.2               # ASSUMED: 5.5/2.1 mm panel jack with an M8 thread. Some need 11 or 12 mm
POT_HOLE_D = 7.2              # ASSUMED: M7 bushing (16 mm pot). 9 mm pots with M9 or 3/8 inch bushings exist
POT_TAB = None                # ASSUMED none: set to (offset_mm, diameter) for the anti-rotation tab, or snap the tab off
JACK_PITCH = 15.5             # ASSUMED: centre spacing of neighbouring audio jacks; must clear the nuts
JACK_BODY_D = 15.0            # ASSUMED: envelope of a jack body behind the panel
JACK_BODY_DEPTH = 22.0        # ASSUMED: jack body and solder lugs behind the panel
DC_BODY_D, DC_BODY_DEPTH = 11.0, 14.0   # ASSUMED
POT_BODY_D, POT_BODY_DEPTH = 17.0, 11.0  # ASSUMED: 16 mm pot
POT_SHAFT_D, POT_SHAFT_LEN = 6.0, 15.0   # ASSUMED, drawn only
KNOB_D, KNOB_H = 20.0, 14.0              # ASSUMED, drawn only

# --- fasteners
# Standard M3 brass heat-set insert, per Mads: the widely sold short type, 4.6 mm
# outer diameter x 5.7 mm long. Measure one before printing if it looks different.
INSERT_OD, INSERT_LEN = 4.6, 5.7
INSERT_PILOT_D = 4.2          # pocket for that insert in a printed part (printed holes come out a little small)
INSERT_PILOT_DEPTH = 6.7      # insert length plus 1 mm for displaced plastic
SCREW_CLEAR_D = 3.4           # M3 clearance
CSK_D, CSK_H = 6.5, 1.7       # ASSUMED: M3 countersunk screws from below into the carrier standoffs (DIN 7991)
# =============================================================================

# Derived levels
Z_FLOOR = -(CARRIER_STANDOFF_LEN + FLOOR_PAD_H)   # top of the floor
Z_BOT = Z_FLOOR - FLOOR
Z_BOARD = BOARD_T                         # top face of the board
DIR_Z0 = Z_BOARD + DIR_ABOVE_BOARD        # underside of the module
TALLEST_ABOVE_BOARD = max(HS_TOP_ABOVE_BOARD, DIR_ABOVE_BOARD + DIR_T + DIR_COMP_H)
Z_LID = Z_BOARD + TALLEST_ABOVE_BOARD + HEADROOM   # underside of the lid, top of the walls
Z_TOP = Z_LID + PLATE_T
# Derived plan (inside faces of the walls)
ANTENNA_TIP = P['U1']['bbox'][2] - 0.28   # footprint outline is 0.28 outside the 25.5 mm module
# The module's far hole row stands over the carrier's H3, which already carries a
# standoff. That fixes the module, and the rear wall follows from its connector edge.
H3X, H3Y = HOLES['H3']['xy']
DIR_X1 = H3X - DIR_HOLE_FROM_EDGE - DIR_HOLE_PITCH_L + DIR_L   # I2S-OUT edge, east
DIR_X0 = DIR_X1 - DIR_L                   # connector edge, west
DIR_Y0 = H3Y - (DIR_W - DIR_HOLE_PITCH_W) / 2   # TOSLINK end, south
DIR_Y1 = DIR_Y0 + DIR_W
XW = DIR_X0 - DIR_EDGE_GAP
REAR_BAY = -XW                            # board west edge to the rear wall
XE = ANTENNA_TIP + ANTENNA_GAP
YN = max(BOARD_Y + BOARD_GAP_N, DIR_Y1 + 1.0 + POST)   # the north-west lid post stands clear of the module
YS = -SOUTH_BAY
# Rear panel, lower row: jack centres along Y, north to south in the order of the
# terminals. They stand between and beside the two module pillars (Y = 12.5 and 68.5).
Z_JACK = Z_FLOOR + 11.0
JACKS = [('FRONT_L', 'rca', 56.5), ('FRONT_R', 'rca', 56.5 - JACK_PITCH),
         ('SURR_L', 'trs', 56.5 - 2 * JACK_PITCH), ('SURR_R', 'trs', 0.5),
         ('DC_9V', 'dc', -13.5)]
JACK_HOLE = {'rca': RCA_HOLE_D, 'trs': TRS_HOLE_D, 'dc': DC_HOLE_D}
POT_Y = -11.0                             # front wall, south of the board, 40 mm from the antenna
Z_POT = (Z_FLOOR + Z_LID) / 2
LID_POSTS = [(XW + POST / 2, YS + POST / 2), (XE - POST / 2, YS + POST / 2),
             (XW + POST / 2, YN - POST / 2), (XE - POST / 2, YN - POST / 2)]
REG_X0, REG_X1 = P['U2']['bbox'][0] - 4, P['U3']['bbox'][2] + 4   # vents span both regulators
VENT_Y0, VENT_Y1 = -HS_D - 6.0, 11.0

AX = {'X': V(1, 0, 0), 'Y': V(0, 1, 0), 'Z': V(0, 0, 1)}

def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))

def cyl(x, y, z, d, length, axis='Z'):
    return Part.makeCylinder(d / 2, length, V(x, y, z), AX[axis])

def rbox(x0, y0, z0, x1, y1, z1, r):
    """Box with its four vertical edges rounded."""
    s = box(x0, y0, z0, x1, y1, z1)
    return s.makeFillet(r, [e for e in s.Edges if e.BoundBox.ZLength > 1e-6])

def chamfer_level(s, z, c):
    """Chamfer every edge lying at height z; return s unchanged if OCC refuses."""
    edges = [e for e in s.Edges if abs(e.BoundBox.ZMin - z) < 1e-6 and abs(e.BoundBox.ZMax - z) < 1e-6]
    try:
        f = s.makeChamfer(c, edges)
        return f if f.isValid() and len(f.Solids) == 1 else s
    except Exception:
        return s

def union(shapes):
    s = shapes[0]
    for b in shapes[1:]:
        s = s.fuse(b)
    return s.removeSplitter()

def vent_xs():
    n = int((REG_X1 - REG_X0) // VENT_PITCH)
    x0 = (REG_X0 + REG_X1) / 2 - n * VENT_PITCH / 2
    return [x0 + i * VENT_PITCH for i in range(n + 1)]

def dir_holes():
    """The module's four holes in the enclosure frame: [pillar S, pillar N, H3, free]."""
    xs = [DIR_X0 + DIR_HOLE_FROM_EDGE, DIR_X0 + DIR_HOLE_FROM_EDGE + DIR_HOLE_PITCH_L]
    ys = [(DIR_Y0 + DIR_Y1) / 2 - DIR_HOLE_PITCH_W / 2, (DIR_Y0 + DIR_Y1) / 2 + DIR_HOLE_PITCH_W / 2]
    return [(xs[0], ys[0]), (xs[0], ys[1]), (xs[1], ys[0]), (xs[1], ys[1])]

def dir_pillars():
    """The two holes of the connector row, which stand over the rear bay."""
    return dir_holes()[:2]

def antenna_span():
    y0, y1 = P['U1']['bbox'][1] + 0.28, P['U1']['bbox'][3] - 0.28
    return y0 - ANTENNA_MARGIN, y1 + ANTENNA_MARGIN

def insert_pocket(x, y, z_top):
    """Pilot for a heat-set insert, opening upward at z_top, with a chamfered lead-in."""
    r = INSERT_PILOT_D / 2
    return cyl(x, y, z_top - INSERT_PILOT_DEPTH, INSERT_PILOT_D, INSERT_PILOT_DEPTH + 1).fuse(
        Part.makeCone(r, r + INSERT_LEADIN, INSERT_LEADIN, V(x, y, z_top - INSERT_LEADIN)))

def base():
    shell = rbox(XW - WALL, YS - WALL, Z_BOT, XE + WALL, YN + WALL, Z_LID, CORNER_R)
    shell = chamfer_level(shell, Z_BOT, 0.8)
    s = shell.cut(rbox(XW, YS, Z_FLOOR, XE, YN, Z_LID + 1, CORNER_R - WALL))
    add = []
    for x, y in LID_POSTS:                       # corner posts, run 1 mm into the walls
        sx, sy = (-1 if x < 0 else 1), (-1 if y < 0 else 1)
        add.append(box(min(x - POST / 2, x + sx * (POST / 2 + 1)), min(y - POST / 2, y + sy * (POST / 2 + 1)), Z_FLOOR - .1,
                       max(x + POST / 2, x + sx * (POST / 2 + 1)), max(y + POST / 2, y + sy * (POST / 2 + 1)), Z_LID))
    for h in HOLES.values():                     # pads under the carrier's own standoffs
        x, y = h['xy']
        add.append(cyl(x, y, Z_FLOOR - .1, FLOOR_PAD_D, FLOOR_PAD_H + .1))
    for x, y in dir_pillars():                   # pillars for the DIR9001's connector row
        add.append(cyl(x, y, Z_FLOOR - .1, PILLAR_D, DIR_Z0 - Z_FLOOR + .1))
        add.append(Part.makeCone(PILLAR_BASE_D / 2, PILLAR_D / 2, 3.0, V(x, y, Z_FLOOR - .1)))
    s = union([s] + add)
    cut = []
    for x, y in LID_POSTS:
        cut.append(insert_pocket(x, y, Z_LID))
    for h in HOLES.values():                     # M3 from below into the carrier standoffs
        x, y = h['xy']
        cut.append(cyl(x, y, Z_BOT - 1, SCREW_CLEAR_D, FLOOR + FLOOR_PAD_H + 2))
        cut.append(Part.makeCone(CSK_D / 2, SCREW_CLEAR_D / 2, CSK_H, V(x, y, Z_BOT)))
        cut.append(cyl(x, y, Z_BOT - 1, CSK_D, 1.01))
    for x, y in dir_pillars():
        cut.append(insert_pocket(x, y, DIR_Z0))
    for _, kind, y in JACKS:                     # rear panel
        cut.append(cyl(XW - WALL - 1, y, Z_JACK, JACK_HOLE[kind], WALL + 2, 'X'))
    zt = DIR_Z0 + DIR_T                          # DIR9001 inputs and toggle, upper row
    yo, yr, yt = DIR_Y0 + DIR_OPT_U, DIR_Y0 + DIR_RCA_U, DIR_Y0 + DIR_TOGGLE_U
    cut.append(cyl(XW - WALL - 1, yt, zt + DIR_TOGGLE_ZC, DIR_TOGGLE_HOLE_D, WALL + 2, 'X'))
    for y, zc in [(yt, DIR_TOGGLE_ZC), (yr, DIR_RCA_ZC)]:
        cut.append(cyl(XW - WALL - 1, y, zt + zc, PANEL_RECESS_D, PANEL_RECESS + 1, 'X'))
    cut.append(box(XW - WALL - 1, yo - DIR_OPT_W / 2, zt - 0.4, XW + 1, yo + DIR_OPT_W / 2, zt - 0.4 + DIR_OPT_H))
    cut.append(cyl(XW - WALL - 1, yr, zt + DIR_RCA_ZC, DIR_RCA_HOLE_D, WALL + 2, 'X'))
    cut.append(cyl(XE - 1, POT_Y, Z_POT, POT_HOLE_D, WALL + 2, 'X'))      # volume pot, front
    if POT_TAB:
        cut.append(cyl(XE - 1, POT_Y, Z_POT + POT_TAB[0], POT_TAB[1], WALL + 2, 'X'))
    a0, a1 = antenna_span()                      # thin plastic in front of and under the antenna
    cut.append(box(XE - .1, a0, Z_FLOOR, XE + WALL - ANTENNA_WALL, a1, Z_LID + 1))
    cut.append(box(BOARD_X - 1, a0, Z_FLOOR - (FLOOR - ANTENNA_WALL), XE + .1, a1, Z_FLOOR + .1))
    for x in vent_xs():                          # floor intake under the regulators
        cut.append(box(x - VENT_W / 2, VENT_Y0, Z_BOT - 1, x + VENT_W / 2, -3.0, Z_FLOOR + 1))
    for c in cut:
        s = s.cut(c)
    return s.removeSplitter()

# ------------------------------------------------------------------ lid plate
def plate_outline():
    """(x0, y0, x1, y1, corner radius) of the acrylic plate, nominal."""
    i = PLATE_INSET
    return XW - WALL + i, YS - WALL + i, XE + WALL - i, YN + WALL - i, CORNER_R - i

def plate_openings():
    """Nominal openings in the plate: (layer, kind, ...). Layers: cut, led_optional."""
    rows = [('cut', 'circle', x, y, PLATE_SCREW_D) for x, y in LID_POSTS]
    x, y = P['SW3']['centre']
    rows.append(('cut', 'circle', x, y, BTN_HOLE_D))
    for ref in ['SW1', 'SW2']:
        x, y = P[ref]['centre']
        rows.append(('cut', 'circle', x, y, PIN_HOLE_D))
    for x in vent_xs():
        rows.append(('cut', 'slot', x, VENT_Y0, VENT_Y1, VENT_W))
    for ref in ['D1', 'D4']:
        x, y = P[ref]['centre']
        rows.append(('led_optional', 'circle', x, y, LED_HOLE_D))
    return rows

def plate_labels():
    """(text, x of the letter tops' far side, y centre, letter height). Text reads from the front (east)."""
    rows = []
    for ref, text in [('SW3', 'USER'), ('SW2', 'BOOT'), ('SW1', 'RESET')]:
        x, y = P[ref]['centre']
        rows.append((text, x + 4.5 + ENGRAVE_H, y, ENGRAVE_H))
    rows.append((PRODUCT_NAME, -3.0, (YS + YN) / 2, ENGRAVE_TITLE_H))
    return rows

def lid_plate():
    """The acrylic plate as a solid, nominal size, without the optional LED holes."""
    x0, y0, x1, y1, r = plate_outline()
    s = rbox(x0, y0, Z_LID, x1, y1, Z_TOP, r)
    for layer, kind, *a in plate_openings():
        if layer != 'cut':
            continue
        if kind == 'circle':
            s = s.cut(cyl(a[0], a[1], Z_LID - 1, a[2], PLATE_T + 2))
        else:
            x, ya, yb, w = a
            s = s.cut(box(x - w / 2, ya + w / 2, Z_LID - 1, x + w / 2, yb - w / 2, Z_TOP + 1))
            for y in (ya + w / 2, yb - w / 2):
                s = s.cut(cyl(x, y, Z_LID - 1, w, PLATE_T + 2))
    return s.removeSplitter()

def user_button():
    """Cap for the USER switch. Its skirt slips over the 6 mm switch body, which
    centres it; its stem runs in the hole in the plate. A collar just under the
    plate stops it lifting off the switch when the box is turned over."""
    x, y = P['SW3']['centre']
    z_press = Z_BOARD + TACT_TOP_ABOVE_BOARD             # underside of the cap's crown, on the plunger
    z_skirt = Z_BOARD + TACT_BODY_H - BTN_SKIRT_OVERLAP
    half = (TACT_BODY + BTN_SKIRT_FIT) / 2
    s = cyl(x, y, z_skirt, BTN_SKIRT_OD, z_press + 1.6 - z_skirt)
    s = s.cut(box(x - half, y - half, z_skirt - 1, x + half, y + half, z_press))
    s = s.fuse(cyl(x, y, z_press + 1.0, BTN_D, Z_TOP + BTN_PROUD - z_press - 1.0))
    zc = Z_LID - BTN_LIFT                                # top of the collar; its underside is a 45 degree cone
    rise = (BTN_COLLAR_D - BTN_D) / 2
    s = s.fuse(Part.makeCone(BTN_D / 2, BTN_COLLAR_D / 2, rise, V(x, y, zc - 1.0 - rise))).fuse(cyl(x, y, zc - 1.0, BTN_COLLAR_D, 1.0))
    return s.removeSplitter()

def shapes():
    out = [base(), lid_plate(), user_button()]
    for n, s in zip(NAMES, out):
        assert s.isValid() and len(s.Solids) == 1, (n, s.isValid(), len(s.Solids))
    return out

def print_pose(name, s):
    """Copy of a part as it lies on the print bed, resting on Z = 0."""
    p = s.copy()
    b = p.BoundBox
    p.translate(V(-b.XMin, -b.YMin, -b.ZMin))
    return p

# ------------------------------------------------------------------ reference
def board_solids():
    """Solids of the KiCad STEP export. Leads are cut off LEAD_TRIM below the
    board: the KiCad TO-220 model has untrimmed 8 mm legs."""
    step = Part.read(str(ROOT / 'cad' / 'board.step'))
    keep = box(-50, -50, -LEAD_TRIM, 200, 200, 100)
    rows = []
    for i, so in enumerate(step.Solids):
        b = so.BoundBox
        if b.XLength > BOARD_X - 1 and b.YLength > BOARD_Y - 1:
            name, group = 'Board', 'pcb'
        elif b.ZMax < 0.5:
            name, group = 'WROOM32', 'metal'
        else:
            name, group = f'Part_{i}', 'part'
        if b.ZMin < -LEAD_TRIM:
            so = so.common(keep)
        rows.append((name, so, group))
    return rows

def envelopes():
    """Stand-ins for everything the STEP export lacks. Sizes are ASSUMED."""
    rows = []
    zt = Z_BOARD
    for ref in ['A3', 'A4']:
        b = P[ref]['bbox']
        rows.append((f'{ref}_PCM5102_envelope', box(b[0], b[1], zt, b[2], b[3], zt + DAC_TOP_ABOVE_BOARD), 'module'))
    for ref in ['J1', 'J3', 'J4', 'J5', 'J6']:
        b = P[ref]['bbox']
        rows.append((f'{ref}_terminal_envelope', box(b[0], b[1], zt, b[2], b[3], zt + TERMINAL_H), 'terminal'))
    for ref, h in [('C11', CAP_SMALL_H), ('C1', CAP_C1_H), ('C2', CAP_SMALL_H), ('C3', CAP_SMALL_H), ('C4', CAP_SMALL_H)]:
        b = P[ref]['bbox']
        d = min(b[2] - b[0], b[3] - b[1]) - 0.5
        rows.append((f'{ref}_can_envelope', cyl((b[0] + b[2]) / 2 if ref != 'C1' else b[0] + d / 2 + .25, (b[1] + b[3]) / 2, zt, d, h), 'part'))
    for ref in ['D1', 'D4']:
        x, y = P[ref]['centre']
        rows.append((f'{ref}_LED_envelope', cyl(x, y, zt, 3.0, LED_TOP_ABOVE_BOARD), 'led'))
    b = P['U3']['bbox']
    xc = (b[0] + b[2]) / 2
    rows.append(('U3_heatsink_envelope', box(xc - HS_W / 2, b[1] - HS_D, zt + HS_BOTTOM_ABOVE_BOARD, xc + HS_W / 2, b[1], zt + HS_TOP_ABOVE_BOARD), 'ghost_metal'))
    return rows

def dir_module():
    rows = [('DIR9001_board', box(DIR_X0, DIR_Y0, DIR_Z0, DIR_X1, DIR_Y1, DIR_Z0 + DIR_T), 'module_pcb'),
            ('DIR9001_parts_envelope', box(DIR_X0, DIR_Y0, DIR_Z0 + DIR_T, DIR_X1, DIR_Y1, DIR_Z0 + DIR_T + DIR_COMP_H), 'ghost')]
    zt = DIR_Z0 + DIR_T
    yo, yr, yt = DIR_Y0 + DIR_OPT_U, DIR_Y0 + DIR_RCA_U, DIR_Y0 + DIR_TOGGLE_U
    rows.append(('DIR9001_toslink', box(DIR_X0 - DIR_OPT_OVERHANG, yo - DIR_OPT_BODY_W / 2, zt, DIR_X0 + 11, yo + DIR_OPT_BODY_W / 2, zt + DIR_OPT_BODY_H), 'black'))
    rows.append(('DIR9001_rca', cyl(DIR_X0 - DIR_CONN_OVERHANG, yr, zt + DIR_RCA_ZC, DIR_RCA_BARREL_D, DIR_CONN_OVERHANG, 'X').fuse(
        box(DIR_X0, yr - 5, zt, DIR_X0 + 10, yr + 5, zt + 11)), 'red'))
    rows.append(('DIR9001_toggle', box(DIR_X0 + 3, yt - 4.2, zt, DIR_X0 + 11.5, yt + 4.2, zt + 7).fuse(
        cyl(DIR_X0 - DIR_TOGGLE_BUSH_OVERHANG, yt, zt + DIR_TOGGLE_ZC, DIR_TOGGLE_BUSH_D, DIR_TOGGLE_BUSH_OVERHANG + 3, 'X')).fuse(
        cyl(DIR_X0 - DIR_TOGGLE_TIP_OVERHANG, yt, zt + DIR_TOGGLE_ZC, 2.6, DIR_TOGGLE_TIP_OVERHANG, 'X')), 'metal'))
    x, y = dir_holes()[2]
    rows.append(('DIR9001_standoff_on_H3', cyl(x, y, Z_BOARD, DIR_STANDOFF_AF, DIR_ABOVE_BOARD), 'black'))
    return rows

def carrier_standoffs():
    """The hex standoffs already fitted under H1 to H4."""
    return [(f'{ref}_standoff', cyl(h['xy'][0], h['xy'][1], -CARRIER_STANDOFF_LEN, CARRIER_STANDOFF_AF, CARRIER_STANDOFF_LEN), 'black')
            for ref, h in sorted(HOLES.items())]

def panel_parts():
    """Jack, pot and knob envelopes. Sizes are ASSUMED; nothing is bought yet."""
    rows = []
    xo = XW - WALL
    for name, kind, y in JACKS:
        d = JACK_HOLE[kind] - 0.3
        if kind == 'dc':
            s = cyl(xo - 2, y, Z_JACK, DC_BODY_D, 2, 'X').fuse(cyl(xo, y, Z_JACK, d, WALL, 'X')).fuse(cyl(XW, y, Z_JACK, DC_BODY_D, DC_BODY_DEPTH, 'X'))
            rows.append((name + '_jack', s, 'black'))
        elif kind == 'rca':
            s = cyl(xo - 9, y, Z_JACK, 8.3, 9, 'X').fuse(cyl(xo - 2, y, Z_JACK, 11, 2, 'X')).fuse(cyl(xo, y, Z_JACK, d, WALL, 'X'))
            s = s.fuse(cyl(XW, y, Z_JACK, 11, 3, 'X')).fuse(cyl(XW, y, Z_JACK, 5, 14, 'X'))
            rows.append((name + '_jack', s, 'gold'))
        else:
            s = cyl(xo - 2.5, y, Z_JACK, 13, 2.5, 'X').fuse(cyl(xo - 5, y, Z_JACK, d, 5 + WALL, 'X'))
            s = s.fuse(cyl(XW, y, Z_JACK, JACK_BODY_D, JACK_BODY_DEPTH, 'X'))
            rows.append((name + '_jack', s, 'black'))
    xi, xo = XE, XE + WALL
    s = cyl(xi - POT_BODY_DEPTH, POT_Y, Z_POT, POT_BODY_D, POT_BODY_DEPTH, 'X').fuse(box(xi - 6, POT_Y - 7, Z_POT - POT_BODY_D / 2 - 6, xi - 2, POT_Y + 7, Z_POT))
    s = s.fuse(cyl(xi, POT_Y, Z_POT, POT_HOLE_D - .3, WALL + 6, 'X')).fuse(cyl(xo, POT_Y, Z_POT, POT_SHAFT_D, POT_SHAFT_LEN, 'X'))
    rows.append(('Volume_pot', s, 'metal'))
    rows.append(('Volume_knob', cyl(xo + 1.5, POT_Y, Z_POT, KNOB_D, KNOB_H, 'X'), 'black'))
    return rows

def references():
    return board_solids() + envelopes() + carrier_standoffs() + dir_module() + panel_parts()

# ---------------------------------------------------------------------- build
def build():
    for folder in ['cad', 'print']:
        (ROOT / folder).mkdir(exist_ok=True)
    doc = A.newDocument('Surround_Enclosure')
    ss = shapes(); report = {}; features = []
    for name, s in zip(NAMES, ss):
        o = doc.addObject('PartDesign::Body', name)
        f = o.newObject('PartDesign::Feature', name + '_Solid'); f.Shape = s
        f.addProperty('App::PropertyString', 'DesignNote').DesignNote = 'Regenerate with enclosure/design.py; first version, dimensions of the real parts not yet measured.'
        features.append(f)
        Part.export([f], str(ROOT / 'cad' / f'{name}.step'))
        p = print_pose(name, s)
        b = p.BoundBox
        report[name] = {'valid': s.isValid(), 'solids': len(s.Solids), 'volume_cm3': round(s.Volume / 1000, 2),
                        'dimensions_mm': [round(b.XLength, 2), round(b.YLength, 2), round(b.ZLength, 2)]}
        if name in PRINTED:
            MeshPart.meshFromShape(Shape=p, LinearDeflection=.05, AngularDeflection=.12, Relative=False).write(str(ROOT / 'print' / f'{name}.stl'))
    import lasercut
    report['lasercut'] = lasercut.export(sys.modules[__name__])
    for name, s, _ in references():
        doc.addObject('Part::Feature', 'Ref_' + name).Shape = s
    doc.recompute(); doc.saveAs(str(ROOT / 'cad' / 'surround_enclosure.FCStd'))
    Part.export(features, str(ROOT / 'cad' / 'surround_enclosure.step'))
    report['rear_bay_mm'] = round(REAR_BAY, 2)
    report['outside_mm'] = [round(XE - XW + 2 * WALL, 2), round(YN - YS + 2 * WALL, 2), round(Z_TOP - Z_BOT, 2)]
    report['inside_mm'] = [round(XE - XW, 2), round(YN - YS, 2), round(Z_LID - Z_FLOOR, 2)]
    (ROOT / 'cad' / 'geometry_validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)

if __name__ == '__main__':
    build()
