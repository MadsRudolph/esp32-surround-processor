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


def footprint(name, descr, body, ref_y, val_y, crt, fab, extra=""):
    (x1, y1, x2, y2) = crt
    s = [f'(footprint "{name}"\n\t(version 20260206)\n\t(generator "make_footprints")\n\t(layer "F.Cu")\n'
         f'\t(descr "{descr}")\n\t(attr through_hole)\n']
    s.append(prop("Reference", "REF**", 0, ref_y, "F.SilkS"))
    s.append(prop("Value", name, 0, val_y, "F.Fab"))
    s.append(prop("Datasheet", "", 0, 0, "F.Fab", hide=True))
    s.append(prop("Description", descr, 0, 0, "F.Fab", hide=True))
    s.append(rect(x1, y1, x2, y2, "F.CrtYd"))
    s.append(rect(*fab, "F.Fab", 0.1))
    s.append(rect(*fab, "F.SilkS", 0.12))
    s.append(extra)
    s.append(body)
    s.append(")\n")
    (LIB / f"{name}.kicad_mod").write_text("".join(s), encoding="utf-8")
    print("wrote", name)


# ---------------------------------------------------------------- GY-PCM5102 carrier
# Module lying along x, header column at the local west edge. Column: the 1x6
# socket for the module header (VIN GND LCK DIN BCK SCK = pads 1-6). East column:
# wire pads for the module's L / R / GND output pads (8-10) at 5.08 mm. Pad 7 is
# the flying lead from the module's XSMT pad; it sits well clear of the column,
# 10 mm beyond it on the routing side, so XSMT does not have to enter the column
# with the clocks, and its position differs between the two DACs so both land in
# the same pocket of copper.
#
# The 32 x 24 mm outline on F.Fab is a RESERVATION, not a measurement: the largest
# figure sellers quote for this board, with the header 3 mm inside one end. Nobody
# has measured the AYWHP module yet. Check against the module before cutting. The
# courtyard covers only the socket, because low parts sit under the module on its
# 8.5 mm socket; tools/surround_board.py checks tall parts against the outline.
def dac_footprint(name, xsmt_y):
    body = []
    for i in range(6):
        body.append(pad(str(1 + i), -13.0, -6.35 + i * pitch, shape="rect" if i == 0 else "oval"))
    body.append(pad("7", -23.0, xsmt_y, size=(2.0, 2.0), drill=1.0))
    for i, n in enumerate(("8", "9", "10")):
        body.append(pad(n, 13.0, -5.08 + i * 5.08, size=(2.2, 2.2), drill=1.1))
    extra = text("VIN", -13.0, -8.6, size=0.7) + text("SCK", -13.0, 8.3, size=0.7) + text("XSMT", -23.0, xsmt_y + 2.4, size=0.7)
    extra += "".join(text(t, 15.6, -5.08 + i * 5.08, size=0.7) for i, t in enumerate(["L", "R", "AGND"]))
    footprint(name, "PCM5102 DAC module on a 1x6 socket plus wire pads (XSMT; OUTL, OUTR, AGND); 32 x 24 mm reserved, unmeasured",
              "".join(body), -13.5, 13.5, (-14.35, -7.9, -11.65, 7.9), (-16.0, -12.0, 16.0, 12.0), extra)

pitch = 2.54
dac_footprint("GY-PCM5102_Carrier_XSMT_S", 10.0)     # lower DAC: rotated, pad lands north of it
dac_footprint("GY-PCM5102_Carrier_XSMT_N", -10.0)    # upper DAC: rotated, pad lands south of it

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
