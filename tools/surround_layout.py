#!/usr/bin/env python3
"""Layout script for the ESP32 4.0 surround processor carrier board.

Regenerate the schematic with:  python3 tools/surround_layout.py
Three bands on A3: power in (top), S/PDIF -> ESP32 -> DACs -> jacks (middle),
user interface (bottom). Geometry is grid-exact; connectivity is verified
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
    if part.lib_id.endswith("ESP32-DevKitC-38"):   # tall module: fields above/below, not over the pins
        bb = part.bbox
        txt = _re.sub(r'(\(property "Reference" "[^"]*"\n\t\t\t\(at) [-\d.]+ [-\d.]+ 0\)',
                      lambda m: f"{m.group(1)} {part.x:g} {bb[1] - 1.778:g} 0)", txt)
        txt = _re.sub(r'(\(property "Value" "[^"]*"\n\t\t\t\(at) [-\d.]+ [-\d.]+ 0\)',
                      lambda m: f"{m.group(1)} {part.x:g} {bb[3] + 1.778:g} 0)", txt)
    return txt
sh._dump_symbol = _dump_rot

# =============================================================== band 1: power
sh.note((G(16), G(14)), "Power in  (5 V class II adapter -> PTC -> 470 uF bulk; "
        "ferrite + 100 uF per module rail. Star ground at the jack.)", size=2)

RAIL_Y = G(28)                                   # 35.56
j1 = sh.place("Connector:Barrel_Jack", "J1", at=(G(20), G(30)), value="PWR IN 5V", footprint="Connector_BarrelJack:BarrelJack_Horizontal")
f1 = sh.place("Device:Polyfuse", "F1", at=(G(34), RAIL_Y), rot=90, value="MF-R110", footprint="Fuse:Fuse_Bourns_MF-RHT100")
sh.seg(j1.pin(1), f1.pin(1))
c1 = sh.place("Device:C_Polarized", "C1", at=(G(46), RAIL_Y + G(3)), value="470uF/10V", footprint="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm")
sh.seg(f1.pin(2), (G(126), RAIL_Y))              # the +5V rail
sh.power("power:PWR_FLAG", (G(52), RAIL_Y))
sh.rail((G(58), RAIL_Y), net="+5V")

gnd_pts = [j1.pin(2), c1.pin(2)]
branches = [(G(70), "+5V_DAC1"), (G(98), "+5V_DAC2"), (G(126), "+5V_DIR")]
for i, (x, net) in enumerate(branches):
    fb = sh.place("Device:FerriteBead", f"FB{i+1}", at=(x, RAIL_Y + G(6)), value="FB axial 600R", footprint="Inductor_THT:L_Axial_L5.0mm_D3.6mm_P10.00mm_Horizontal_Murata_BL01RN1A2A2")
    sh.seg((x, RAIL_Y), fb.pin(1))
    node_y = RAIL_Y + G(12)                      # 50.8
    sh.seg(fb.pin(2), (x, node_y))
    c = sh.place("Device:C_Polarized", f"C{i+2}", at=(x + G(6), node_y + G(3)), value="100uF/10V", footprint="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm")
    sh.seg((x, node_y), c.pin(1))
    sh.seg((x, node_y), (x - G(8), node_y))
    sh.label((x - G(8), node_y), net, rot=180, kind="global")
    sh.power("power:PWR_FLAG", c.pin(1).xy)
    gnd_pts.append(c.pin(2))
GND1_Y = G(50)                                   # 63.5
gnd_rail(sh, gnd_pts, GND1_Y, x_sym=G(92))
sh.power("power:PWR_FLAG", (G(60), GND1_Y))
sh.note((G(16), G(60)), "FB1-3: axial bead on lead, ~600 R @ 100 MHz, DCR < 0.3 R. Each module keeps its own "
        "100 nF + 10 uF at the pin. Never power from a PC USB port.", size=1.27)

# ========================================= band 2: S/PDIF -> ESP32 -> DACs -> out
sh.note((G(16), G(74)), "Signal chain  (TOSLINK -> DIR9001 clock recovery -> ESP32 I2S slave on "
        "both ports -> PCM5102A x2 in 3-wire BCK-PLL mode -> line out)", size=2)

EX, EY = G(140), G(105)                          # ESP32 origin
esp = sh.place("Surround:ESP32-DevKitC-38", "A1", at=(EX, EY), value="ESP32-DevKitC V4", footprint="Surround:ESP32-DevKitC-38_Sockets")
DX, DY = G(40), G(98)
dirm = sh.place("Surround:DIR9001-Module", "A2", at=(DX, DY), value="DIR9001 + TOSLINK", footprint="Connector_PinSocket_2.54mm:PinSocket_1x10_P2.54mm_Vertical")

# clock/data bus: DIR9001 -> 33R -> ESP32, in the order the pins meet on the PCB
# (AUDIO, ERROR, DOUT, LRCK, BCK top to bottom). Both ends are 2.54 mm pitch, so the
# bus fans out to 5.08 mm through the resistor column (jog out near the DIR9001,
# jog back near the ESP32, nested so nothing crosses) and the values stay clear.
RXS = {"R1": G(66), "R2": G(72), "R3": G(78)}   # staggered so ref/value texts never meet
bus = [  # (dir pin, esp pin, ref/None, label, mid-row y, jog-out x, jog-back x)
    ("AUDIO", "IO36/VP", None, None,       G(91), G(53), G(120)),
    ("ERROR", "IO39/VN", None, None,       G(95), None,  None),
    ("DOUT",  "IO34",    "R3", None,       G(99), G(58), G(114)),
    ("LRCKO", "IO35",    "R2", "DIR_LRCK", G(103), G(56), G(116)),
    ("BCKO",  "IO32",    "R1", "DIR_BCK",  G(107), G(54), G(118)),
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
        r = sh.place("Device:R", ref, at=(RXS[ref], my), rot=90, value="33R", footprint=RFP)
        sh.seg(left, r.pin(1)); sh.seg(r.pin(2), right)
    else:
        sh.seg(left, right)
    if lab:
        sh.label((G(90), my), lab, kind="global")
sh.nc(dirm.pin("SCKO"))
sh.note((G(44), G(86)), "33 R at the driver end of every clock/data line; keep wires < 10 cm", size=1.27)

# DIR9001 module straps and power
fmt0, fmt1 = dirm.pin("FMT0"), dirm.pin("FMT1")
sh.seg(fmt0, (G(24), fmt0.y)); sh.seg(fmt1, (G(24), fmt1.y))
sh.seg((G(24), fmt0.y), (G(24), fmt1.y))
sh.rail((G(24), fmt0.y), net="+3V3")
vcc = dirm.pin("VCC")
sh.seg(vcc, (G(20), vcc.y))
sh.label((G(20), vcc.y), "+5V_DIR", rot=180, kind="global")
dg = dirm.pin("GND")
sh.seg(dg, (G(24), dg.y)); sh.gnd((G(24), dg.y))
sh.note((G(28), G(112)), "FMT1=FMT0=H -> 24-bit I2S (DIR9001 Table 13). CKSEL=L, XTI=GND,", size=1.27)
sh.note((G(28), G(114)), "PSCK=LL. Unlock: clocks free-run, DOUT mutes, ERROR=H.", size=1.27)

# ESP32 power side
p5 = esp.pin("5V")
sh.seg(p5, (G(116), p5.y)); sh.rail((G(116), p5.y), net="+5V")
p3 = esp.pin("3V3")
sh.seg(p3, (G(108), p3.y)); sh.rail((G(108), p3.y), net="+3V3")
g14, g20, g26 = esp.pin("14"), esp.pin("20"), esp.pin("26")
for g in (g14, g20, g26):
    sh.seg(g, (G(116), g.y))
sh.seg((G(116), g14.y), (G(116), g26.y))
sh.gnd((G(116), g26.y))
for nm in ("EN", "TX0/IO1", "RX0/IO3", "SD0/IO7", "SD1/IO8", "SD2/IO9", "SD3/IO10",
           "CMD/IO11", "CLK/IO6", "IO0/BOOT", "IO2", "IO4", "IO5", "IO12/MTDI", "IO13",
           "IO14", "IO15/MTDO", "IO16", "IO17"):
    sh.nc(esp.pin(nm))
sh.note((G(124), G(131)), "IO12 must float (flash 1.8 V strap). IO0/IO2/IO15 strapping, IO6-11 flash: NC.", size=1.27)
sh.note((G(124), G(133)), "Wi-Fi/BT and DFS disabled in firmware; audio task in IRAM.", size=1.27)

# ESP32 -> DACs
D1X, D1Y = G(230), G(89)
dac1 = sh.place("Surround:GY-PCM5102", "A3", at=(D1X, D1Y), value="GY-PCM5102 FRONT", footprint="Surround:GY-PCM5102_Carrier")
D2X, D2Y = G(230), G(117)
dac2 = sh.place("Surround:GY-PCM5102", "A4", at=(D2X, D2Y), value="GY-PCM5102 SURROUND", footprint="Surround:GY-PCM5102_Carrier")

din1, din2, xsmt_pin, led_pin = esp.pin("IO33"), esp.pin("IO25"), esp.pin("IO26"), esp.pin("IO27")
assert abs(din1.y - dac1.pin("DIN").y) < 1e-6
r4 = sh.place("Device:R", "R4", at=(G(200), din1.y), rot=90, value="33R", footprint=RFP)
sh.seg(din1, r4.pin(1)); sh.seg(r4.pin(2), dac1.pin("DIN"))
d2din = dac2.pin("DIN")
r5 = sh.place("Device:R", "R5", at=(G(200), d2din.y), rot=90, value="33R", footprint=RFP)
sh.seg(din2, (G(196), din2.y)); sh.seg((G(196), din2.y), (G(196), d2din.y))
sh.seg((G(196), d2din.y), r5.pin(1)); sh.seg(r5.pin(2), d2din)
sh.seg(xsmt_pin, (G(162), xsmt_pin.y)); sh.label((G(162), xsmt_pin.y), "XSMT", kind="global")

LX = G(212)
for dac, pnet, rail_y in ((dac1, "+5V_DAC1", G(98)), (dac2, "+5V_DAC2", G(126))):
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
sh.note((G(224), G(106)), "XSMT bridge removed and wired out. VIN = 5 V via on-board LDO.", size=1.27)

# status LED on IO27
r10 = sh.place("Device:R", "R10", at=(G(180), led_pin.y), rot=90, value="330R", footprint=RFP)
sh.seg(led_pin, r10.pin(1))
led = sh.place("Device:LED", "D1", at=(G(184), G(104)), rot=90, value="STATUS", footprint="Surround:LED_D3.0mm_P5.08mm_LaserPads")
sh.seg(r10.pin(2), (G(184), led_pin.y)); sh.seg((G(184), led_pin.y), led.pin("A"))
sh.gnd(led.pin("K"))

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
# OUTR routes down to the second jack
j6y = G(134)
sh.seg(o2r, (G(250), o2r.y)); sh.seg((G(250), o2r.y), (G(250), j6y - G(2)))
j6, t6 = trs("J6", "R8", "R9", (G(250), j6y - G(2)), j6y, G(143), "SURR R (panel TRS)")
sh.seg(ag2, (G(246), ag2.y)); sh.gnd((G(246), ag2.y), drop=G(4))
sh.note((G(196), G(153)), "Panel TRS jacks on screw terminals, impedance-balanced to the Eris 3.5: 100 R tip, 100 R ring to GND.", size=1.27)

# ============================================================ band 3: user interface
sh.note((G(160), G(157)), "User interface  (rotary encoder on PCNT with glitch filter, "
        "internal pull-ups; SSD1306 OLED on I2C with pull-ups on the module)", size=2)
enc = sh.place("Device:RotaryEncoder_Switch", "SW1", at=(G(200), G(170)), value="ENC (panel, 5 wires)", footprint="Surround:PinHeader_1x05_Encoder")
ea, eb, ec, s1, s2 = enc.pin("A"), enc.pin("B"), enc.pin("C"), enc.pin("S1"), enc.pin("S2")
io18, io19, io23, io22, io21 = (esp.pin(n) for n in ("IO18", "IO19", "IO23", "IO22", "IO21"))
# nested fan-out: upper pin turns down further right
sh.seg(io18, (G(176), io18.y)); sh.seg((G(176), io18.y), (G(176), ea.y)); sh.seg((G(176), ea.y), ea)
sh.seg(io19, (G(174), io19.y)); sh.seg((G(174), io19.y), (G(174), eb.y)); sh.seg((G(174), eb.y), eb)
sh.seg(io23, (G(172), io23.y)); sh.seg((G(172), io23.y), (G(172), G(180)))
sh.seg((G(172), G(180)), (G(214), G(180))); sh.seg((G(214), G(180)), (G(214), s1.y)); sh.seg((G(214), s1.y), s1)
sh.seg(ec, (G(190), ec.y)); sh.power("power:GND", (G(190), ec.y), rot=270)
sh.seg(s2, (G(210), s2.y)); sh.gnd((G(210), s2.y))
sh.seg(io22, (G(162), io22.y)); sh.label((G(162), io22.y), "SCL", kind="global")
sh.seg(io21, (G(162), io21.y)); sh.label((G(162), io21.y), "SDA", kind="global")

oled = sh.place("Connector_Generic:Conn_01x04", "J7", at=(G(248), G(170)), mirror="x", value="OLED SSD1306 I2C", footprint="Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical")
og, ov, osc, osd = oled.pin(1), oled.pin(2), oled.pin(3), oled.pin(4)
sh.seg(og, (G(232), og.y)); sh.gnd((G(232), og.y))
sh.seg(ov, (G(228), ov.y)); sh.rail((G(228), ov.y), net="+3V3")
for p, net in ((osc, "SCL"), (osd, "SDA")):
    sh.seg(p, (G(240), p.y)); sh.label((G(240), p.y), net, rot=180, kind="global")

# ------------------------------------------------------------- gates, in-process
problems = sh.check()
print("check:", problems if problems else "clean")
out = ROOT / "hardware/surround.kicad_sch"
sh.emit(str(out))
print("wrote", out)
