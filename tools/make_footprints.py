#!/usr/bin/env python3
"""Generate lib/Surround.pretty: the footprints the stock libraries cannot give us.

Every pad gap here is audited against the 0.8 mm end mill (see design notes):
  * 2.54 mm socket rows come out at 0.84 mm pad-to-pad (fixed by the pin pitch;
    documented .kicad_dru exception, the tool still clears it in one pass),
  * everything else is >= 1.9 mm.
Panel-mount parts (encoder, RCA/TRS jacks) are brought to the board on a 5-pin
header and 5.08 mm screw terminals whose pad NUMBERS match the schematic
symbols' pin names (A B C S1 S2 / T S / T R S), so KiCad links them directly.
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


# ---------------------------------------------------------------- ESP32-DevKitC V4
# Two 1x19 socket rows, 25.4 mm apart (official Espressif DevKitC V4; clones
# with 22.86 mm rows exist -- measure yours and change ROW). Pad numbers are the
# symbol's: 1-19 left row top to bottom (3V3 ... 5V), 20-38 right row (GND ... CLK).
ROW = 25.4
pitch = 2.54
top = -9 * pitch
body = []
for i in range(19):
    y = top + i * pitch
    body.append(pad(str(1 + i), -ROW / 2, y, shape="rect" if i == 0 else "oval", size=(1.7, 1.7)))
    body.append(pad(str(20 + i), ROW / 2, y, shape="oval", size=(1.7, 1.7)))
extra = text("USB", 0, 29.5, size=1.2) + text("3V3", -ROW / 2 - 4.5, top) + text("GND", ROW / 2 + 4.5, top)
footprint("ESP32-DevKitC-38_Sockets",
          "ESP32-DevKitC V4 (38 pin) on two 1x19 2.54 mm sockets, 25.4 mm row spacing; USB end at +y",
          "".join(body), -30.5, 30.5, (-15.0, -28.5, 15.0, 28.5), (-13.95, -27.2, 13.95, 27.2), extra)

# ---------------------------------------------------------------- GY-PCM5102 carrier
# Module lying along x. West column: the 1x6 socket for the module header
# (VIN GND LCK DIN BCK SCK = pads 1-6) plus one wire pad in line for the flying
# lead from the module's XSMT pad (pad 7). East column: wire pads for the
# module's L / R / GND output pads (8-10) at 5.08 mm. Every input therefore faces
# the ESP32 and every output faces the jack terminals. Body ~32 x 22 mm --
# verify against the board in hand.
body = []
for i in range(6):
    body.append(pad(str(1 + i), -13.0, -6.35 + i * pitch, shape="rect" if i == 0 else "oval"))
# XSMT deliberately OFF the header column: three nets (BCK, LRCK, XSMT) touching the
# same three pad rows (ESP32 row, both DAC headers) is a K3,3 that forces a wire
# bridge on one layer; a lone pad breaks it (place_floor.py: floor 1 -> 0).
body.append(pad("7", -7.0, 10.0, size=(2.0, 2.0), drill=1.0))
for i, n in enumerate(("8", "9", "10")):
    body.append(pad(n, 13.0, -5.08 + i * 5.08, size=(2.2, 2.2), drill=1.1))
extra = text("VIN", -13.0, -8.6, size=0.7) + text("SCK", -13.0, 8.3, size=0.7) + text("XSMT", -7.0, 12.4, size=0.7)
extra += "".join(text(t, 15.6, -5.08 + i * 5.08, size=0.7) for i, t in enumerate(["L", "R", "AGND"]))
footprint("GY-PCM5102_Carrier",
          "GY-PCM5102 DAC module on a 1x6 socket plus wire pads (XSMT west; OUTL, OUTR, AGND east)",
          "".join(body), -13.5, 13.5, (-17.0, -12.5, 17.0, 14.0), (-16.0, -11.5, 16.0, 11.5), extra)

# ---------------------------------------------------------------- encoder header
# Pads named A B C S1 S2 to match Device:RotaryEncoder_Switch; panel encoder on 5 wires.
names = ["A", "B", "C", "S1", "S2"]
body = "".join(pad(n, -5.08 + i * pitch, 0, shape="rect" if i == 0 else "oval") for i, n in enumerate(names))
extra = "".join(text(n, -5.08 + i * pitch, -2.9, size=0.7) for i, n in enumerate(names))
footprint("PinHeader_1x05_Encoder", "1x05 2.54 mm header, pads A B C S1 S2, for a panel-mount encoder",
          body, -4.5, 4.5, (-6.85, -1.8, 6.85, 1.8), (-6.35, -1.27, 6.35, 1.27), extra)

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

vendored("TerminalBlock_bornier-2_P5.08mm", "TerminalBlock_TS_P5.08mm", {"1": "T", "2": "S"},
         "2-pin 5.08 mm screw terminal, pads T/S, for a panel-mount RCA jack (vendored bornier-2)")
vendored("TerminalBlock_bornier-3_P5.08mm", "TerminalBlock_TRS_P5.08mm", {"1": "T", "2": "R", "3": "S"},
         "3-pin 5.08 mm screw terminal, pads T/R/S, for a panel-mount TRS jack (vendored bornier-3)")

# ---------------------------------------------------------------- barrel jack, milled
# The stock BarrelJack_Horizontal puts 3.5 mm square pads over 1.0 x 3.0 mm slots,
# so the ring across the slot is 0.25 mm: too thin to survive an isolation pass with
# any registration error, and KiCad's annular_width check rejects it. Same body and
# the same slots, but each pad becomes an oval grown along the slot's SHORT axis, so
# the thinnest ring is 0.8 mm. The limit is pad 3, which sits 4.7 mm from pad 1 and
# must still leave the 0.8 mm the end mill needs between them.
STOCK_BJ = Path("/usr/share/kicad/footprints/Connector_BarrelJack.pretty/BarrelJack_Horizontal.kicad_mod")
SIZES = {"1": (3.0, 4.6), "2": (3.0, 4.6), "3": (4.6, 3.0)}
out, num = [], None
for line in STOCK_BJ.read_text(encoding="utf-8").splitlines(keepends=True):
    m = re.match(r'\s*\(pad "(\d+)"', line)
    if m:
        num = m.group(1)
    if num in SIZES and re.match(r"\s*\(size ", line):
        w, h = SIZES[num]
        line = re.sub(r"\(size [\d.]+ [\d.]+\)", f"(size {w} {h})", line)
        num = None
    out.append(line)
bj = "".join(out)
bj = bj.replace('(footprint "BarrelJack_Horizontal"', '(footprint "BarrelJack_Horizontal_MilledPads"')
bj = re.sub(r'\(property "Value" "[^"]*"', '(property "Value" "BarrelJack_Horizontal_MilledPads"', bj)
bj = bj.replace("thru_hole rect", "thru_hole oval")
(LIB / "BarrelJack_Horizontal_MilledPads.kicad_mod").write_text(bj, encoding="utf-8")
print("wrote BarrelJack_Horizontal_MilledPads")

# ---------------------------------------------------------------- PTC fuse, 0.8 mm drill
# Stock Fuse_Bourns_MF-RHT100 drills 0.71 mm, under the process minimum hole.
body = pad("1", 0, 0, size=(1.9, 1.9), drill=0.9, shape="rect") + pad("2", 5.1, 1.2, size=(1.9, 1.9), drill=0.9)
footprint("Fuse_Bourns_MF-R110_P5.1mm", "Bourns MF-R110 radial PTC, 5.1 mm lead spacing, 0.9 mm drill",
          body, -2.6, 4.5, (-2.7, -1.5, 7.8, 2.9), (-2.0, -0.8, 7.1, 2.0))

# ---------------------------------------------------------------- LED with mill-safe pads
(LIB / "LED_D3.0mm_P5.08mm_LaserPads.kicad_mod").write_text(
    (SKILL_LIB / "LED_D3.0mm_P5.08mm_LaserPads.kicad_mod").read_text(encoding="utf-8"), encoding="utf-8")
print("wrote LED_D3.0mm_P5.08mm_LaserPads (copied)")
