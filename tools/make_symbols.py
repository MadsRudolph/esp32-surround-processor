#!/usr/bin/env python3
"""Generate lib/Surround.kicad_sym: module-level symbols for the carrier board.

The carrier hosts three breakout modules on pin headers, so the schematic
wants one symbol per module with the header's pin numbers and useful names,
not the bare ICs. Pins are grouped logically (inputs left, outputs right);
the numbers are the physical header positions the footprints use.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "lib" / "Surround.kicad_sym"
PITCH = 2.54
PINLEN = 2.54
HALF_W = 17.78          # body half-width for the wide ESP32 symbol


def pin(name, number, x, y, angle, etype):
    return (f'\t\t\t(pin {etype} line\n'
            f'\t\t\t\t(at {x:g} {y:g} {angle})\n'
            f'\t\t\t\t(length {PINLEN:g})\n'
            f'\t\t\t\t(name "{name}"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n'
            f'\t\t\t\t(number "{number}"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n'
            f'\t\t\t)\n')


def prop(key, val, x, y, hide=False, rot=0):
    h = "\t\t\t(hide yes)\n" if hide else ""
    return (f'\t\t(property "{key}" "{val}"\n\t\t\t(at {x:g} {y:g} {rot})\n'
            f'\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n{h}'
            f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')


def symbol(name, refprefix, left, right, half_w, descr, keywords):
    """left/right: lists of (name, number, etype) top to bottom."""
    n = max(len(left), len(right))
    top = (n - 1) * PITCH / 2
    half_h = top + PITCH               # one pitch of margin above/below
    s = [f'\t(symbol "{name}"\n\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)\n'
         f'\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n'
         f'\t\t(in_pos_files yes)\n\t\t(duplicate_pin_numbers_are_jumpers no)\n']
    s.append(prop("Reference", refprefix, 0, half_h + 1.27))
    s.append(prop("Value", name, 0, -(half_h + 1.27)))
    s.append(prop("Footprint", "", 0, -(half_h + 3.81), hide=True))
    s.append(prop("Datasheet", "", 0, 0, hide=True))
    s.append(prop("Description", descr, 0, 0, hide=True))
    s.append(prop("ki_keywords", keywords, 0, 0, hide=True))
    s.append(f'\t\t(symbol "{name}_0_1"\n\t\t\t(rectangle\n'
             f'\t\t\t\t(start {-half_w:g} {half_h:g})\n\t\t\t\t(end {half_w:g} {-half_h:g})\n'
             f'\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n'
             f'\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')
    s.append(f'\t\t(symbol "{name}_1_1"\n')
    for i, (nm, num, et) in enumerate(left):
        s.append(pin(nm, num, -(half_w + PINLEN), top - i * PITCH, 0, et))
    for i, (nm, num, et) in enumerate(right):
        s.append(pin(nm, num, half_w + PINLEN, top - i * PITCH, 180, et))
    s.append('\t\t)\n\t)\n')
    return "".join(s)


# ---------------------------------------------------------------- ESP32
# Pin numbers are the physical 38-pin DevKitC V4 header positions:
# left header 1-19 top to bottom (3V3 ... 5V), right header 20-38 (GND ... CLK).
esp_left = [
    ("5V", "19", "power_in"), ("3V3", "1", "power_out"), ("EN", "2", "input"),
    ("IO34", "5", "input"), ("IO35", "6", "input"), ("IO32", "7", "bidirectional"),
    ("IO36/VP", "3", "input"), ("IO39/VN", "4", "input"),
    ("TX0/IO1", "23", "output"), ("RX0/IO3", "24", "input"),
    ("SD0/IO7", "37", "bidirectional"), ("SD1/IO8", "36", "bidirectional"),
    ("SD2/IO9", "16", "bidirectional"), ("SD3/IO10", "17", "bidirectional"),
    ("CMD/IO11", "18", "bidirectional"), ("CLK/IO6", "38", "bidirectional"),
    ("GND", "14", "power_in"), ("GND", "20", "passive"), ("GND", "26", "passive"),
]
esp_right = [
    ("IO25", "9", "bidirectional"), ("IO26", "10", "bidirectional"),
    ("IO27", "11", "bidirectional"), ("IO33", "8", "bidirectional"),
    ("IO18", "28", "bidirectional"), ("IO19", "27", "bidirectional"),
    ("IO23", "21", "bidirectional"), ("IO22", "22", "bidirectional"),
    ("IO21", "25", "bidirectional"),
    ("IO0/BOOT", "33", "bidirectional"), ("IO2", "34", "bidirectional"),
    ("IO4", "32", "bidirectional"), ("IO5", "29", "bidirectional"),
    ("IO12/MTDI", "13", "bidirectional"), ("IO13", "15", "bidirectional"),
    ("IO14", "12", "bidirectional"), ("IO15/MTDO", "35", "bidirectional"),
    ("IO16", "31", "bidirectional"), ("IO17", "30", "bidirectional"),
]

# ---------------------------------------------------------------- DIR9001 module
dir_left = [
    ("FMT0", "9", "input"), ("FMT1", "10", "input"),
    ("VCC", "1", "power_in"), ("GND", "2", "power_in"),
]
dir_right = [
    ("SCKO", "3", "output"), ("BCKO", "4", "output"), ("LRCKO", "5", "output"),
    ("DOUT", "6", "output"), ("ERROR", "7", "output"), ("AUDIO", "8", "output"),
]

# ---------------------------------------------------------------- GY-PCM5102
dac_left = [
    ("VIN", "1", "power_in"), ("LCK", "3", "input"), ("DIN", "4", "input"),
    ("BCK", "5", "input"), ("XSMT", "7", "input"), ("SCK", "6", "input"),
    ("GND", "2", "power_in"),
]
dac_right = [
    ("OUTL", "8", "output"), ("OUTR", "9", "output"), ("AGND", "10", "passive"),
]

body = [symbol("ESP32-DevKitC-38", "A", esp_left, esp_right, HALF_W,
               "ESP32-DevKitC V4, 38-pin, on two 1x19 sockets", "esp32 devkit module"),
        symbol("DIR9001-Module", "A", dir_left, dir_right, 12.7,
               "DIR9001 S/PDIF receiver breakout with TOSLINK", "spdif toslink dir9001"),
        symbol("GY-PCM5102", "A", dac_left, dac_right, 12.7,
               "PCM5102A DAC breakout (GY-PCM5102), 3-wire mode", "dac pcm5102 i2s")]

OUT.write_text('(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "kicad_symbol_editor")\n'
               '\t(generator_version "10.0")\n' + "".join(body) + ')\n', encoding="utf-8")
print("wrote", OUT)
