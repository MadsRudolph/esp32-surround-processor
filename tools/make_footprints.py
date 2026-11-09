#!/usr/bin/env python3
"""Generate lib/Surround.pretty: the footprints the stock libraries cannot give us.

Every pad gap here clears the 0.50 mm clearance of the ball-mill rules: the
2.54 mm socket rows come out at 0.84 mm pad-to-pad, everything else is wider.
Only the WROOM-32 castellations (0.37 mm, from the skill's esp32 library) need a
.kicad_dru exception. Panel jacks are brought to the board on 5.08 mm screw
terminals whose pad NUMBERS match the schematic symbols' pin names (T S / T R S),
so KiCad links them directly.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib" / "Surround.pretty"
LIB.mkdir(parents=True, exist_ok=True)
VENDOR = Path("/home/mads/Projects/62755-power-electronics/hardware/kicad/lib/TerminalBlock.pretty")
SKILL_LIB = Path.home() / ".claude/skills/kicad-laser-pcb/lib/energy_system.pretty"

FONT = '(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)'


def prop(name, val, x, y, layer, hide=False):
    h = "\n\t\t(hide yes)" if hide else ""
    return (f'\t(property "{name}" "{val}"\n\t\t(at {x:g} {y:g} 0)\n\t\t(layer "{layer}"){h}\n'
            f'\t\t(uuid "00000000-0000-0000-0000-000000000000")\n\t\t{FONT}\n\t)\n')


def rect(x1, y1, x2, y2, layer, w=0.05):
    return (f'\t(fp_rect\n\t\t(start {x1:g} {y1:g})\n\t\t(end {x2:g} {y2:g})\n'
            f'\t\t(stroke\n\t\t\t(width {w})\n\t\t\t(type default)\n\t\t)\n\t\t(fill no)\n\t\t(layer "{layer}")\n\t)\n')


def text(s, x, y, layer="F.Fab", size=1.0):
    return (f'\t(fp_text user "{s}"\n\t\t(at {x:g} {y:g} 0)\n\t\t(layer "{layer}")\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')


def pad(num, x, y, size=(1.7, 1.7), drill=1.0, shape="circle"):
    sx, sy = size
    return (f'\t(pad "{num}" thru_hole {shape}\n\t\t(at {x:g} {y:g})\n\t\t(size {sx:g} {sy:g})\n'
            f'\t\t(drill {drill:g})\n\t\t(layers "*.Cu" "*.Mask")\n\t\t(remove_unused_layers no)\n\t)\n')


def footprint(name, descr, body, ref_y, val_y, crt, fab, extra="", silk_box=True):
    (x1, y1, x2, y2) = crt
    s = [f'(footprint "{name}"\n\t(version 20260206)\n\t(generator "make_footprints")\n\t(layer "F.Cu")\n'
         f'\t(descr "{descr}")\n\t(attr through_hole)\n']
    s.append(prop("Reference", "REF**", 0, ref_y, "F.SilkS"))
    s.append(prop("Value", name, 0, val_y, "F.Fab"))
    s.append(prop("Datasheet", "", 0, 0, "F.Fab", hide=True))
    s.append(prop("Description", descr, 0, 0, "F.Fab", hide=True))
    s.append(rect(x1, y1, x2, y2, "F.CrtYd"))
    s.append(rect(*fab, "F.Fab", 0.1))
    if silk_box:
        s.append(rect(*fab, "F.SilkS", 0.12))
    s.append(extra)
    s.append(body)
    s.append(")\n")
    (LIB / f"{name}.kicad_mod").write_text("".join(s), encoding="utf-8")
    print("wrote", name)


# ---------------------------------------------------------------- PCM5102A module
# The purple PCM5102A board, measured under the microscope (2026-11-09): 31.0 x
# 17.1 mm. A 1x6 column on one short edge, pin centres 0.88 mm in (VIN GND LCK DIN
# BCK SCK), and a 1x9 row along one long edge, 1.9 mm in, starting 6.49 mm from the
# column: FLT DEMP XSMT FMT A3V3 AGND ROUT AGND LOUT. Both rows are 2.54 mm
# sockets, so nothing is wired by hand.
#
# The module sits FACE DOWN, components towards the carrier: that is the hand that
# keeps VIN north of SCK as drawn here, which the clock routing is built around.
# Seen from above, column at local west, VIN north, the 1x9 row runs along the
# south edge and the 3.5 mm jack overhangs the north edge at the far end.
# On 8.5 mm sockets plus the header's 2.5 mm spacer the jack bottom is ~5 mm up;
# tools/surround_board.py keeps the tall parts out from under body and jack.
# FLT, DEMP, FMT and A3V3 are left open: the module's own H1-H4 jumpers set them.
# The XSMT jumper is removed so the ESP32 drives it.
DAC_ROW = ("FLT", "DEMP", "7", "FMT", "A3V3", "10", "9", "10", "8")
DAC_COL_X, DAC_ROW_Y, DAC_ROW_X0 = -13.0, 6.74, -13.0 + 6.49
DAC_BODY = (-13.88, -8.62, 17.08, 8.49)
DAC_JACK = (7.67, -14.1, 17.08, -8.62)       # overhang assumed 5.5 mm: not measured


def dac_footprint(name):
    body = [pad(str(1 + i), DAC_COL_X, -6.35 + i * pitch, shape="rect" if i == 0 else "oval")
            for i in range(6)]
    body += [pad(n, DAC_ROW_X0 + k * pitch, DAC_ROW_Y, shape="oval")
             for k, n in enumerate(DAC_ROW)]
    extra = text("VIN", DAC_COL_X + 1.9, -6.35, size=0.7) + text("SCK", DAC_COL_X + 1.9, 6.35, size=0.7)
    extra += "".join(text(t, DAC_ROW_X0 + k * pitch, DAC_ROW_Y - 1.7, size=0.6)
                     for k, t in enumerate(["FLT", "DMP", "XSMT", "FMT", "3V3", "AG", "R", "AG", "L"]))
    extra += text("FACE DOWN", 3.0, 0.0, size=1.0)
    extra += rect(*DAC_JACK, "F.Fab", 0.1) + text("jack", 12.4, -11.4, size=0.8)
    # courtyard: the two socket strips; the module itself floats over low parts
    extra += rect(DAC_ROW_X0 - 1.1, DAC_ROW_Y - 1.1, DAC_ROW_X0 + 8 * pitch + 1.1, DAC_ROW_Y + 1.1, "F.CrtYd")
    # silk: the module's outline on the three sides away from the socket column, so
    # the laser never marks a pad
    x0, y0, x1, y1 = DAC_BODY
    for (ax, ay, bx, by) in ((x0 + 1.4, y0, x1, y0), (x0 + 1.4, y1, x1, y1), (x1, y0, x1, y1)):
        extra += (f'\t(fp_line\n\t\t(start {ax:g} {ay:g})\n\t\t(end {bx:g} {by:g})\n'
                  f'\t\t(stroke\n\t\t\t(width 0.15)\n\t\t\t(type default)\n\t\t)\n\t\t(layer "F.SilkS")\n\t)\n')
    footprint(name, "PCM5102A module, face down on a 1x6 and a 1x9 socket; measured 31.0 x 17.1 mm",
              "".join(body), -10.0, 10.0, (-14.35, -7.9, -11.65, 7.9), DAC_BODY, extra, silk_box=False)

pitch = 2.54
dac_footprint("PCM5102_Module_FaceDown")


# ---------------------------------------------------------------- DIR9001 pigtail
# The LHY AUDIO DIR9001-I2S board sits off the carrier; its 6-wire JST-XH pigtail
# (bare tinned ends) is soldered into these holes. Pad numbers keep the old 1x10
# socket's 1-6 so the routing is unchanged; silk names the wire, as the module's
# I2S-OUT labels it.
# Nearly the order of the module's I2S-OUT connector and its pigtail (DATA BCLK LRCK
# MCLK +5V GND): only BCLK and LRCK swap, so the clocks reach the carrier in the
# order the DAC column needs them. Cross those two wires.
DIR_PADS = [("6", "DATA"), ("5", "LRCK"), ("4", "BCLK"), ("3", "MCLK"), ("1", "+5V"), ("2", "GND")]
body = "".join(pad(n, 0.0, i * pitch, shape="rect" if n == "1" else "circle") for i, (n, _) in enumerate(DIR_PADS))
extra = "".join(text(t, -2.6, i * pitch, layer="F.SilkS", size=0.8) for i, (_, t) in enumerate(DIR_PADS))
footprint("DIR9001_Pigtail_1x6", "Six solder holes for the DIR9001-I2S board's XH pigtail: +5V GND MCLK BCLK LRCK DATA",
          body, -2.2, 15.0, (-1.15, -1.15, 1.15, 13.85), (-1.0, -1.0, 1.0, 13.7), extra)

# ---------------------------------------------------------------- terminal blocks
# Vendored bornier-2 / -3 (KiCad 10 dropped them) with pad numbers renamed to
# the audio-jack symbols' pin names.
def vendored(src_name, dst_name, mapping, descr):
    src = (VENDOR / f"{src_name}.kicad_mod").read_text(encoding="utf-8")
    s = src.replace(f'(footprint "{src_name}"', f'(footprint "{dst_name}"')
    s = re.sub(r'\(property "Value" "[^"]*"', f'(property "Value" "{dst_name}"', s)
    s = re.sub(r'\(descr "[^"]*"\)', f'(descr "{descr}")', s)
    for old, new in mapping.items():
        s = s.replace(f'(pad "{old}" ', f'(pad "{new}" ')
    (LIB / f"{dst_name}.kicad_mod").write_text(s, encoding="utf-8")
    print("wrote", dst_name)

vendored("TerminalBlock_bornier-2_P5.08mm", "TerminalBlock_2P_P5.08mm", {},
         "2-pin 5.08 mm screw terminal, pads 1/2, for the supply (vendored bornier-2)")
vendored("TerminalBlock_bornier-2_P5.08mm", "TerminalBlock_TS_P5.08mm", {"1": "T", "2": "S"},
         "2-pin 5.08 mm screw terminal, pads T/S, for a panel-mount RCA jack (vendored bornier-2)")
vendored("TerminalBlock_bornier-3_P5.08mm", "TerminalBlock_TRS_P5.08mm", {"1": "T", "2": "R", "3": "S"},
         "3-pin 5.08 mm screw terminal, pads T/R/S, for a panel-mount TRS jack (vendored bornier-3)")

# ---------------------------------------------------------------- long resistor
# P12.70: KiCad stops at 10.16 then jumps to 15.24 for this body. Long enough to
# carry +5V_DAC2 over both clocks and the DAC1 data stub, see tools/surround_board.py.
STOCK_R = Path("/usr/share/kicad/footprints/Resistor_THT.pretty/R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal.kicad_mod")
r = STOCK_R.read_text(encoding="utf-8")
r = r.replace('R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P12.70mm_Horizontal')
r = r.replace('(at 10.16 0)', '(at 12.7 0)').replace('(at 5.08 ', '(at 6.35 ')
r = re.sub(r'\(fp_rect\s+\(start -1\.05 -1\.5\)\s+\(end 11\.21 1\.5\)', '(fp_rect\n\t\t(start -1.05 -1.5)\n\t\t(end 13.75 1.5)', r)
(LIB / "R_Axial_DIN0207_L6.3mm_D2.5mm_P12.70mm_Horizontal.kicad_mod").write_text(r, encoding="utf-8")
print("wrote R_Axial_P12.70")

# ---------------------------------------------------------------- electrolytic, formed leads
# A 1 uF 50 V can is 5 mm across on 2 mm leads. Formed out to 3.5 mm, a track fits
# between them, which is what lets C11 span the 3V3 line. Pads of the stock D8 part.
c = (Path("/usr/share/kicad/footprints/Capacitor_THT.pretty/CP_Radial_D8.0mm_P3.50mm.kicad_mod")).read_text(encoding="utf-8")
c = c.replace("CP_Radial_D8.0mm_P3.50mm", "CP_Radial_D5.0mm_P3.50mm_FormedLeads")
c = re.sub(r"\(fp_(?:circle|line|arc|poly|rect)\s.*?\n\t\)\n", "", c, flags=re.S)
c = c.replace("\t(pad ", rect(-1.05, -2.7, 4.55, 2.7, "F.CrtYd") + "\t(pad ", 1)
(LIB / "CP_Radial_D5.0mm_P3.50mm_FormedLeads.kicad_mod").write_text(c, encoding="utf-8")
print("wrote CP_Radial_D5.0mm_P3.50mm_FormedLeads")

# ---------------------------------------------------------------- WROOM-32
# The skill's no-via footprint. Its antenna keep-out spans +/-24 mm and 21 mm north,
# sized for a board-edge antenna with RF in use. Wi-Fi and Bluetooth are off in this
# design, so it shrinks to the module's own width: no copper under the antenna, and
# the corner beside it is free for the 3V3 bulk cap and the UART.
e = (Path.home() / ".claude/skills/kicad-laser-pcb/lib/esp32.pretty/ESP32-WROOM-32_NoVias.kicad_mod").read_text(encoding="utf-8")
e = e.replace("-30.74", "-16.0")
e = re.sub(r"\(start -24 ", "(start -10 ", e); e = re.sub(r"\(end -24 ", "(end -10 ", e)
e = re.sub(r"\(start 24 ", "(start 10 ", e); e = re.sub(r"\(end 24 ", "(end 10 ", e)
e = re.sub(r"\(xy -24 ", "(xy -10 ", e); e = re.sub(r"\(xy 24 ", "(xy 10 ", e)
(LIB / "ESP32-WROOM-32_NoVias.kicad_mod").write_text(e, encoding="utf-8")
print("wrote ESP32-WROOM-32_NoVias")

# ---------------------------------------------------------------- TO-220, mill pads
(LIB / "TO-220-3_Vertical_LaserPads.kicad_mod").write_text(
    (SKILL_LIB / "TO-220-3_Vertical_LaserPads.kicad_mod").read_text(encoding="utf-8"), encoding="utf-8")
print("wrote TO-220-3_Vertical_LaserPads (copied)")

# ---------------------------------------------------------------- LED with mill-safe pads
(LIB / "LED_D3.0mm_P5.08mm_LaserPads.kicad_mod").write_text(
    (SKILL_LIB / "LED_D3.0mm_P5.08mm_LaserPads.kicad_mod").read_text(encoding="utf-8"), encoding="utf-8")
print("wrote LED_D3.0mm_P5.08mm_LaserPads (copied)")
