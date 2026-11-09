#!/usr/bin/env python3
"""Layout script for the ESP32 4.0 surround processor carrier board.

Regenerate the schematic with:  python3 tools/surround_layout.py
Three bands on A3: power in (top), S/PDIF -> ESP32 -> DACs -> jacks (middle),
ESP32 support and user interface (bottom). Geometry is grid-exact; connectivity is verified
in-process before the file is written.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path.home() / ".claude/skills/kicad-schematic/scripts"
sys.path.insert(0, str(SKILL))
from schdraw import Sheet          # noqa: E402
from symcache import SymCache      # noqa: E402
from idioms import gnd_rail        # noqa: E402

G = lambda n: round(n * 1.27, 2)   # noqa: E731
RFP = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"

sh = Sheet(paper="A3", title="ESP32 4.0 surround processor - carrier board",
           project="surround", project_file=ROOT / "hardware/surround.kicad_pro")
sh.src._cache = SymCache(extra_dirs=[ROOT / "lib"])

# KiCad rotates a symbol's fields with the symbol, so a rot=90 resistor gets
# vertical text that crosses the neighbouring rows. Counter-rotate the field.
import re as _re
_orig_dump = sh._dump_symbol
def _dump_rot(part):
    txt = _orig_dump(part)
    if int(part.rot) in (90, 270):
        txt = _re.sub(r'(\(property "(?:Reference|Value)" "[^"]*"\n\t\t\t\(at [-\d.]+ [-\d.]+) 0\)',
                      r"\1 90)", txt)
    if part.lib_id.endswith("ESP32-WROOM-32"):   # tall module: fields above/below, not over the pins
        bb = part.bbox
        txt = _re.sub(r'(\(property "Reference" "[^"]*"\n\t\t\t\(at) [-\d.]+ [-\d.]+ 0\)',
                      lambda m: f"{m.group(1)} {part.x:g} {bb[1] - 1.778:g} 0)", txt)
        txt = _re.sub(r'(\(property "Value" "[^"]*"\n\t\t\t\(at) [-\d.]+ [-\d.]+ 0\)',
                      lambda m: f"{m.group(1)} {part.x:g} {bb[3] + 1.778:g} 0)", txt)
    return txt
sh._dump_symbol = _dump_rot

# =============================================================== band 1: power
sh.note((G(16), G(14)), "Power in  (9 V class II adapter -> reverse-polarity Schottky -> LM7805 for the audio "
        "modules, LM317 for the ESP32. Star ground at the input.)", size=2)

RAIL_Y = G(28)
j1 = sh.place("Connector_Generic:Conn_01x02", "J1", at=(G(20), G(28)), mirror="y", value="9V IN", footprint="Surround:TerminalBlock_2P_P5.08mm")
d2 = sh.place("Device:D", "D2", at=(G(32), RAIL_Y), rot=180, value="1N5817", footprint="Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal")
sh.seg(j1.pin(1), (G(28), j1.pin(1).y)); sh.seg((G(28), j1.pin(1).y), (G(28), RAIL_Y)); sh.seg((G(28), RAIL_Y), d2.pin("A"))
sh.seg(d2.pin("K"), (G(136), RAIL_Y))            # the +9V rail
sh.label((G(40), RAIL_Y), "+9V", kind="global")
sh.power("power:PWR_FLAG", (G(42), RAIL_Y))
gnd_pts = [j1.pin(2)]
c5 = sh.place("Device:C_Polarized", "C5", at=(G(46), RAIL_Y + G(3)), value="10uF/50V", footprint="Capacitor_THT:CP_Radial_D5.0mm_P2.50mm")
c6 = sh.place("Device:C", "C6", at=(G(52), RAIL_Y + G(3)), value="100n", footprint="Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm")
for c in (c5, c6):
    sh.seg((c.pin(1).x, RAIL_Y), c.pin(1)); gnd_pts.append(c.pin(2))

# LM7805: the audio modules' 5 V, one RC branch per module
u2 = sh.place("Regulator_Linear:LM7805_TO220", "U2", at=(G(64), RAIL_Y + G(3)), value="LM7805", footprint="Surround:TO-220-3_Vertical_LaserPads")
sh.seg((G(58), RAIL_Y), (G(58), u2.pin("VI").y)); sh.seg((G(58), u2.pin("VI").y), u2.pin("VI"))
gnd_pts.append(u2.pin("GND"))
RAIL5 = u2.pin("VO").y
sh.seg(u2.pin("VO"), (G(104), RAIL5))
sh.label((G(70), RAIL5), "+5V", kind="global")
c7 = sh.place("Device:C", "C7", at=(G(74), RAIL5 + G(3)), value="100n", footprint="Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm")
c8 = sh.place("Device:C_Polarized", "C8", at=(G(78), RAIL5 + G(3)), value="10uF/50V", footprint="Capacitor_THT:CP_Radial_D5.0mm_P2.50mm")
for c in (c7, c8):
    sh.seg((c.pin(1).x, RAIL5), c.pin(1)); gnd_pts.append(c.pin(2))
RLONG = "Surround:R_Axial_DIN0207_L6.3mm_D2.5mm_P12.70mm_Horizontal"
branches = [("R17", G(84), "+5V_DAC1", "C2", RFP), ("R18", G(94), "+5V_DAC2", "C3", RFP), ("R19", G(104), "+5V_DIR", "C4", RFP)]
for rref, x, net, cref, rfp in branches:
    r = sh.place("Device:R", rref, at=(x, RAIL5 + G(3)), value="10R", footprint=rfp)
    sh.seg((x, RAIL5), r.pin(1))
    node_y = r.pin(2).y + G(2)
    sh.seg(r.pin(2), (x, node_y))
    c = sh.place("Device:C_Polarized", cref, at=(x + G(4), node_y + G(3)), value="100uF/10V", footprint="Capacitor_THT:CP_Radial_D8.0mm_P5.00mm")
    sh.seg((x, node_y), (c.pin(1).x, node_y)); sh.seg((c.pin(1).x, node_y), c.pin(1))
    sh.seg((x, node_y), (x - G(3), node_y))
    sh.label((x - G(3), node_y), net, rot=180, kind="global")
    sh.power("power:PWR_FLAG", (c.pin(1).x, node_y))
    gnd_pts.append(c.pin(2))

# LM317: 3.27 V for the ESP32, the proven supply from references/esp32.md
u3 = sh.place("Regulator_Linear:LM317_TO-220", "U3", at=(G(122), RAIL_Y + G(4)), value="LM317T", footprint="Surround:TO-220-3_Vertical_LaserPads")
sh.seg((G(116), RAIL_Y), (G(116), u3.pin("VI").y)); sh.seg((G(116), u3.pin("VI").y), u3.pin("VI"))
vo = u3.pin("VO")
sh.seg(vo, (G(140), vo.y))
sh.label((G(138), vo.y), "+3V3", kind="global")
r12 = sh.place("Device:R", "R12", at=(G(130), vo.y + G(3)), value="243R", footprint=RFP)
sh.seg((G(130), vo.y), r12.pin(1))
adj_y = r12.pin(2).y + G(1)
sh.seg(r12.pin(2), (G(130), adj_y))
adj = u3.pin("ADJ")
sh.seg(adj, (adj.x, adj_y)); sh.seg((adj.x, adj_y), (G(130), adj_y))
r13 = sh.place("Device:R", "R13", at=(adj.x, adj_y + G(3)), value="392R", footprint=RFP)
sh.seg((adj.x, adj_y), r13.pin(1))
gnd_pts.append(r13.pin(2))
d3 = sh.place("Device:D", "D3", at=(G(144), RAIL_Y + G(1)), rot=0, value="1N4003", footprint="Diode_THT:D_DO-41_SOD81_P7.62mm_Horizontal")
sh.seg(d3.pin("A"), (G(150), d3.pin("A").y)); sh.seg((G(150), d3.pin("A").y), (G(150), vo.y)); sh.seg((G(150), vo.y), (G(140), vo.y))
sh.seg(d3.pin("K"), (G(136), d3.pin("K").y)); sh.seg((G(136), d3.pin("K").y), (G(136), RAIL_Y))
GND1_Y = G(52)
gnd_rail(sh, gnd_pts, GND1_Y, x_sym=G(92))
sh.power("power:PWR_FLAG", (G(60), GND1_Y))
sh.note((G(16), G(60)), "R17-19: 10 R + 100 uF per module, ~160 Hz, 0.3 V drop at 30 mA; each module keeps its own "
        "LDO and bypass. R12/R13 sit at the LM317; C1 and C9 at U1 pin 2.", size=1.27)

# ========================================= band 2: S/PDIF -> ESP32 -> DACs -> out
sh.note((G(16), G(74)), "Signal chain  (TOSLINK -> DIR9001 clock recovery -> ESP32 I2S slave on "
        "both ports -> PCM5102A x2 in 3-wire BCK-PLL mode -> line out)", size=2)

EX, EY = G(140), G(108)                          # ESP32 origin
esp = sh.place("Surround:ESP32-WROOM-32", "U1", at=(EX, EY), value="ESP32-WROOM-32", footprint="Surround:ESP32-WROOM-32_NoVias")
DX, DY = G(40), G(101)                           # DOUT level with IO34
dirm = sh.place("Surround:DIR9001-Module", "A2", at=(DX, DY), value="DIR9001-I2S (pigtail)", footprint="Surround:DIR9001_Pigtail_1x6")

# clock/data bus: DIR9001 -> 43R2 -> ESP32, in the order the pins meet on the PCB
# (DOUT, LRCK, BCK top to bottom). Both ends are 2.54 mm pitch, so the
# bus fans out to 5.08 mm through the resistor column and the values stay clear.
RXS = {"R1": G(66), "R2": G(72), "R3": G(78)}    # staggered so ref/value texts never meet
bus = [  # (dir pin, esp pin, ref/None, label, mid-row y, jog-out x, jog-back x)
    ("DOUT",  "IO35",    "R3", None,       G(100), G(58), G(114)),
    ("LRCKO", "IO26",    "R2", "DIR_LRCK", G(104), G(56), G(116)),
    ("BCKO",  "IO14",    "R1", "DIR_BCK",  G(108), G(54), G(118)),
]
for src, dst, ref, lab, my, xo, xb in bus:
    a, b = dirm.pin(src), esp.pin(dst)
    assert abs(a.y - b.y) < 1e-6, (src, dst, a.y, b.y)
    if xo is None:
        assert abs(my - a.y) < 1e-6
        left, right = a, b
    else:
        sh.seg(a, (xo, a.y)); sh.seg((xo, a.y), (xo, my))
        sh.seg((xb, my), (xb, b.y)); sh.seg((xb, b.y), b)
        left, right = (xo, my), (xb, my)
    if ref:
        r = sh.place("Device:R", ref, at=(RXS[ref], my), rot=90, value="43R2", footprint=RFP)
        sh.seg(left, r.pin(1)); sh.seg(r.pin(2), right)
    else:
        sh.seg(left, right)
    if lab:
        sh.label((G(90), my), lab, kind="global")
sh.nc(dirm.pin("SCKO"))
sh.note((G(30), G(85)), "Series source termination for the 71 R trace over the ground plane (tools/impedance.py):", size=1.27)
sh.note((G(30), G(87)), "43R2 at every driver output (25-40 R CMOS source). Tune on a scope at the far pad.", size=1.27)

# DIR9001 module power
vcc = dirm.pin("VCC")
sh.seg(vcc, (G(20), vcc.y))
sh.label((G(20), vcc.y), "+5V_DIR", rot=180, kind="global")
dg = dirm.pin("GND")
sh.seg(dg, (G(24), dg.y)); sh.gnd((G(24), dg.y))
sh.note((G(28), G(114)), "Module DIP switches: FMT1=FMT0=H -> 24-bit I2S (DIR9001 Table 13).", size=1.27)
sh.note((G(28), G(116)), "ERROR/AUDIO not brought out: firmware watches LRCK and the data.", size=1.27)

# ESP32 supply: bulk and bypass right at pin 2, per references/esp32.md
p3 = esp.pin("3V3")
sh.seg(p3, (G(100), p3.y))
sh.label((G(100), p3.y), "+3V3", rot=180, kind="global")
c1 = sh.place("Device:C_Polarized", "C1", at=(G(104), G(82)), value="470uF/10V", footprint="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm")
c9 = sh.place("Device:C", "C9", at=(G(110), G(82)), value="100n", footprint="Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm")
for c in (c1, c9):
    sh.seg(c.pin(1), (c.pin(1).x, c.pin(1).y - G(2)))
    sh.label((c.pin(1).x, c.pin(1).y - G(2)), "+3V3", rot=90, kind="global")
sh.gnd(c1.pin(2)); sh.gnd(c9.pin(2))
g1, g15, g38 = esp.pin("1"), esp.pin("15"), esp.pin("38")
for g in (g1, g15, g38):
    sh.seg(g, (G(121), g.y))
sh.seg((G(121), g1.y), (G(121), g38.y)); sh.gnd((G(121), g38.y))
ad = esp.pin("IO33")
sh.seg(ad, (G(121), ad.y)); sh.label((G(121), ad.y), "POT", rot=180, kind="global")
en = esp.pin("EN")
sh.seg(en, (G(118), en.y)); sh.label((G(118), en.y), "EN", rot=180, kind="global")
for nm in ("IO25", "IO36/VP", "IO34", "IO32", "IO27", "IO12/MTDI", "IO19", "SD2/IO9", "SD3/IO10",
           "IO22", "NC", "IO5", "IO16", "IO23", "IO4", "IO18", "SD1/IO8", "SD0/IO7",
           "CLK/IO6", "CMD/IO11", "IO39/VN"):
    sh.nc(esp.pin(nm))
sh.note((G(122), G(134)), "IO12 must float (flash 1.8 V strap). IO2/IO15 strapping, IO6-11 flash: NC. Centre pad 39 unsoldered.", size=1.27)
sh.note((G(122), G(136)), "Wi-Fi/BT and DFS disabled in firmware; audio task in IRAM.", size=1.27)

# ESP32 -> DACs
D1X, D1Y = G(230), G(89)
dac1 = sh.place("Surround:GY-PCM5102", "A3", at=(D1X, D1Y), value="PCM5102 FRONT", footprint="Surround:PCM5102_Module_FaceDown")
D2X, D2Y = G(230), G(117)
dac2 = sh.place("Surround:GY-PCM5102", "A4", at=(D2X, D2Y), value="PCM5102 SURROUND", footprint="Surround:PCM5102_Module_FaceDown")

din1, din2, xsmt_pin = esp.pin("IO2"), esp.pin("IO13"), esp.pin("IO21")
r4 = sh.place("Device:R", "R4", at=(G(200), dac1.pin("DIN").y), rot=90, value="43R2", footprint=RFP)
sh.seg(r4.pin(2), dac1.pin("DIN"))
sh.seg(din1, (G(190), din1.y)); sh.seg((G(190), din1.y), (G(190), r4.pin(1).y))
sh.seg((G(190), r4.pin(1).y), r4.pin(1))
d2din = dac2.pin("DIN")
r5 = sh.place("Device:R", "R5", at=(G(200), d2din.y), rot=90, value="43R2", footprint=RFP)
sh.seg(r5.pin(2), d2din)
sh.seg(din2, (G(186), din2.y)); sh.seg((G(186), din2.y), (G(186), r5.pin(1).y))
sh.seg((G(186), r5.pin(1).y), r5.pin(1))
sh.seg(xsmt_pin, (G(182), xsmt_pin.y)); sh.label((G(182), xsmt_pin.y), "XSMT", kind="global")

LX = G(212)
for dac, pnet, rail_y in ((dac1, "+5V_DAC1", G(99)), (dac2, "+5V_DAC2", G(127))):
    for pn, net in (("VIN", pnet), ("LCK", "DIR_LRCK"), ("BCK", "DIR_BCK"), ("XSMT", "XSMT")):
        p = dac.pin(pn)
        sh.seg(p, (LX, p.y))
        sh.label((LX, p.y), net, rot=180, kind="global")
    sck, gnd = dac.pin("SCK"), dac.pin("GND")
    sh.seg(sck, (G(216), sck.y))
    pts = [(G(216), sck.y), gnd]
    if dac is dac1:                              # XSMT pull-down: muted through boot
        r11 = sh.place("Device:R", "R11", at=(LX, dac.pin("XSMT").y + G(3)), value="10k", footprint=RFP)
        pts.append(r11.pin(2))
    gnd_rail(sh, pts, rail_y, x_sym=G(216))
sh.note((G(224), G(104)), "SCK=GND: 3-wire BCK-PLL mode. Module pads: FMT=L, FLT=L, DEMP=L,", size=1.27)
sh.note((G(224), G(106)), "Modules face down on 1x6 + 1x9 sockets. XSMT jumper removed. VIN = 5 V via on-board LDO.", size=1.27)

# front outputs: RCA
o1l, o1r, ag1 = dac1.pin("OUTL"), dac1.pin("OUTR"), dac1.pin("AGND")
j3 = sh.place("Connector_Audio:AudioJack2", "J3", at=(G(268), o1l.y), rot=180, value="FRONT L (panel RCA)", footprint="Surround:TerminalBlock_TS_P5.08mm")
sh.seg(o1l, j3.pin("T"))
s3 = j3.pin("S"); sh.seg(s3, (G(258), s3.y)); sh.gnd((G(258), s3.y))
j4 = sh.place("Connector_Audio:AudioJack2", "J4", at=(G(268), G(95)), rot=180, value="FRONT R (panel RCA)", footprint="Surround:TerminalBlock_TS_P5.08mm")
t4 = j4.pin("T")
sh.seg(o1r, (G(254), o1r.y)); sh.seg((G(254), o1r.y), (G(254), t4.y)); sh.seg((G(254), t4.y), t4)
s4 = j4.pin("S"); sh.seg(s4, (G(258), s4.y)); sh.gnd((G(258), s4.y))
sh.seg(ag1, (G(246), ag1.y)); sh.gnd((G(246), ag1.y), drop=G(4))
sh.note((G(226), G(76)), "Fronts: panel RCA jacks on screw terminals, short cable to the Fosi amp. Module has 470 R + 2.2 nF out filter.", size=1.27)

# surround outputs: impedance-balanced TRS
o2l, o2r, ag2 = dac2.pin("OUTL"), dac2.pin("OUTR"), dac2.pin("AGND")
def trs(ref_j, ref_rt, ref_rr, src_pt, jy, gy, value):
    j = sh.place("Connector_Audio:AudioJack3", ref_j, at=(G(268), jy), rot=180, value=value, footprint="Surround:TerminalBlock_TRS_P5.08mm")
    t, r, s = j.pin("T"), j.pin("R"), j.pin("S")
    rt = sh.place("Device:R", ref_rt, at=(G(254), t.y), rot=90, value="100R", footprint=RFP)
    sh.seg(src_pt, rt.pin(1)); sh.seg(rt.pin(2), t)
    rr = sh.place("Device:R", ref_rr, at=(G(256), r.y + G(3)), value="100R", footprint=RFP)
    sh.seg(r, rr.pin(1))
    gnd_rail(sh, [rr.pin(2), s], gy, x_sym=G(260))
    return j, t
j5, _ = trs("J5", "R6", "R7", o2l, o2l.y + G(2), G(122), "SURR L (panel TRS)")
j6y = G(134)
sh.seg(o2r, (G(250), o2r.y)); sh.seg((G(250), o2r.y), (G(250), j6y - G(2)))
j6, t6 = trs("J6", "R8", "R9", (G(250), j6y - G(2)), j6y, G(143), "SURR R (panel TRS)")
sh.seg(ag2, (G(246), ag2.y)); sh.gnd((G(246), ag2.y), drop=G(4))
sh.note((G(196), G(153)), "Panel TRS jacks on screw terminals, impedance-balanced to the Eris 3.5: 100 R tip, 100 R ring to GND.", size=1.27)

# ==================================================== band 3: ESP32 support and UI
sh.note((G(16), G(146)), "ESP32 support and user interface  (no auto-reset: hold BOOT, tap RESET to flash over the UART "
        "header. Pot on ADC1, 1k in series because it lives on flying leads.)", size=2)
SUP_Y = G(160)
def stub(pin, x, net):
    """A short wire from a right-hand ESP32 pin to a global label."""
    sh.seg(pin, (x, pin.y)); sh.label((x, pin.y), net, kind="global")
stub(esp.pin("IO0/BOOT"), G(164), "BOOT")
stub(esp.pin("IO15/MTDO"), G(164), "USER")
stub(esp.pin("IO17"), G(164), "LED")
stub(esp.pin("TXD0/IO1"), G(164), "TXD0")
stub(esp.pin("RXD0/IO3"), G(164), "RXD0")

def button(ref, x, net, value):
    """Pushbutton from a labelled net to ground."""
    sw = sh.place("Switch:SW_Push", ref, at=(x, SUP_Y + G(3)), value=value, footprint="Button_Switch_THT:SW_PUSH_6mm")
    sh.seg(sw.pin(1), (x - G(6), sw.pin(1).y))
    sh.seg(sw.pin(2), (x + G(6), sw.pin(2).y)); sh.gnd((x + G(6), sw.pin(2).y))
    return (x - G(6), sw.pin(1).y)

def pullup(ref, x, node, net, fp=RFP):
    """10k from a node up to +3V3, net named on the wire."""
    r = sh.place("Device:R", ref, at=(x, SUP_Y - G(3)), value="10k", footprint=fp)
    sh.seg(r.pin(1), (x, r.pin(1).y - G(2)))
    sh.label((x, r.pin(1).y - G(2)), "+3V3", rot=90, kind="global")
    sh.seg(r.pin(2), (x, node[1]))
    sh.label((x, node[1]), net, rot=180, kind="global")

# RESET: RC delay on EN, as on every proven board
en_node = button("SW1", G(36), "EN", "RESET")
pullup("R14", en_node[0], en_node, "EN")
c11 = sh.place("Device:C_Polarized", "C11", at=(G(24), SUP_Y + G(7)), value="1uF/50V", footprint="Surround:CP_Radial_D5.0mm_P3.50mm_FormedLeads")
sh.seg(c11.pin(1), (G(24), c11.pin(1).y - G(2))); sh.label((G(24), c11.pin(1).y - G(2)), "EN", rot=90, kind="global")
sh.gnd(c11.pin(2))
# BOOT
boot_node = button("SW2", G(60), "BOOT", "BOOT")
pullup("R15", boot_node[0], boot_node, "BOOT")
# user button: internal pull-up in firmware
user_node = button("SW3", G(84), "USER", "USER")
sh.label(user_node, "USER", rot=180, kind="global")
# status LED
r10 = sh.place("Device:R", "R10", at=(G(102), SUP_Y + G(3)), rot=90, value="332R", footprint=RFP)
sh.seg(r10.pin(1), (G(98), r10.pin(1).y)); sh.label((G(98), r10.pin(1).y), "LED", rot=180, kind="global")
led = sh.place("Device:LED", "D1", at=(G(110), SUP_Y + G(3)), rot=180, value="STATUS", footprint="Surround:LED_D3.0mm_P5.08mm_LaserPads")
sh.seg(r10.pin(2), led.pin("A")); sh.seg(led.pin("K"), (G(114), led.pin("K").y)); sh.gnd((G(114), led.pin("K").y))
# power LED
r16 = sh.place("Device:R", "R16", at=(G(122), SUP_Y - G(3)), value="1k", footprint=RFP)
sh.seg(r16.pin(1), (G(122), r16.pin(1).y - G(2))); sh.label((G(122), r16.pin(1).y - G(2)), "+3V3", rot=90, kind="global")
d4 = sh.place("Device:LED", "D4", at=(G(122), SUP_Y + G(4)), rot=90, value="POWER", footprint="Surround:LED_D3.0mm_P5.08mm_LaserPads")
sh.seg(r16.pin(2), d4.pin("A")); sh.gnd(d4.pin("K"))
# UART: pin order follows the ESP32's pads so TXD0 runs dead straight
j2 = sh.place("Connector_Generic:Conn_01x03", "J2", at=(G(140), SUP_Y + G(3)), value="UART 3V3", footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
sh.seg(j2.pin(1), (G(134), j2.pin(1).y)); sh.label((G(134), j2.pin(1).y), "TXD0", rot=180, kind="global")
sh.seg(j2.pin(2), (G(134), j2.pin(2).y)); sh.label((G(134), j2.pin(2).y), "RXD0", rot=180, kind="global")
sh.seg(j2.pin(3), (G(130), j2.pin(3).y)); sh.gnd((G(130), j2.pin(3).y))
# volume pot, panel mounted on three wires
r20 = sh.place("Device:R", "R20", at=(G(158), SUP_Y + G(3)), rot=90, value="1k", footprint=RFP)
sh.seg(r20.pin(1), (G(154), r20.pin(1).y)); sh.label((G(154), r20.pin(1).y), "POT", rot=180, kind="global")
j7 = sh.place("Connector_Generic:Conn_01x03", "J7", at=(G(170), SUP_Y + G(3)), value="VOLUME POT (panel)", footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
sh.seg(j7.pin(2), r20.pin(2))
sh.seg(j7.pin(1), (G(164), j7.pin(1).y)); sh.label((G(164), j7.pin(1).y), "+3V3", rot=180, kind="global")
sh.seg(j7.pin(3), (G(166), j7.pin(3).y)); sh.gnd((G(166), j7.pin(3).y))

# scope ground either side of the clocks; a wire between them is the DIR9001's short return
for ref, x in (("TP1", G(180)), ("TP2", G(186))):
    tp = sh.place("Connector:TestPoint", ref, at=(x, SUP_Y), value="GND", footprint="TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm")
    sh.gnd(tp.pin(1))

# ------------------------------------------------------------- gates, in-process
problems = sh.check()
print("check:", problems if problems else "clean")
out = ROOT / "hardware/surround.kicad_sch"
sh.emit(str(out))
print("wrote", out)
