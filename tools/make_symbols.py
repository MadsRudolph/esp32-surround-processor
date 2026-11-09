#!/usr/bin/env python3
"""Generate lib/Surround.kicad_sym: module-level symbols for the carrier board.

The DIR9001 and DAC breakouts sit on pin sockets, so the schematic wants one
symbol per module with the header's pin numbers and useful names, not the bare
ICs. Pins are grouped logically; the numbers are the physical positions the
footprints use.
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
# Pin numbers are the WROOM-32 castellations. Grouped by what the carrier does
# with them, not by position; the unused ones are at the bottom of each side.
# The GPIO choice follows the board: each signal is on the castellation that
# faces where its copper goes (tools/surround_board.py, FLOORPLAN): the DIR9001
# lines on alternate pins of the south row, the two DAC data lines on the two
# free pins of the west column (the USER button on IO15 beside them), XSMT, BOOT,
# the status LED and the UART on the north row.
esp_left = [
    ("3V3", "2", "power_in"), ("EN", "3", "input"),
    ("IO33", "9", "bidirectional"), ("IO39/VN", "5", "input"),
    ("IO35", "7", "input"), ("IO26", "11", "bidirectional"), ("IO14", "13", "bidirectional"),
    ("IO32", "8", "bidirectional"),
    ("GND", "1", "power_in"), ("GND", "15", "passive"), ("GND", "38", "passive"),
    ("IO25", "10", "bidirectional"), ("IO36/VP", "4", "input"),
    ("IO34", "6", "input"), ("IO27", "12", "bidirectional"),
    ("IO12/MTDI", "14", "bidirectional"), ("IO19", "31", "bidirectional"),
    ("SD2/IO9", "17", "bidirectional"), ("SD3/IO10", "18", "bidirectional"),
]
esp_right = [
    ("IO13", "16", "bidirectional"), ("IO2", "24", "bidirectional"),
    ("IO21", "33", "bidirectional"), ("TXD0/IO1", "35", "output"),
    ("RXD0/IO3", "34", "input"), ("IO15/MTDO", "23", "bidirectional"),
    ("IO17", "28", "bidirectional"), ("IO0/BOOT", "25", "bidirectional"),
    ("IO22", "36", "bidirectional"), ("NC", "32", "no_connect"),
    ("IO5", "29", "bidirectional"), ("IO16", "27", "bidirectional"),
    ("IO23", "37", "bidirectional"), ("IO4", "26", "bidirectional"),
    ("IO18", "30", "bidirectional"), ("SD1/IO8", "22", "bidirectional"),
    ("SD0/IO7", "21", "bidirectional"), ("CLK/IO6", "20", "bidirectional"),
    ("CMD/IO11", "19", "bidirectional"),
]

# ---------------------------------------------------------------- DIR9001 module
# LHY AUDIO DIR9001-I2S board (64 x 48 mm), off the carrier on its own standoffs.
# Its 6-pin JST-XH I2S-OUT pigtail lands on six carrier pads. FMT and PSCK are DIP
# switches on the module; ERROR and AUDIO are not brought out (firmware detects
# unlock from LRCK and IEC 61937 from the data). SCKO is the board's MCLK.
dir_left = [
    ("VCC", "1", "power_in"), ("GND", "2", "power_in"),
]
dir_right = [
    ("DOUT", "6", "output"), ("LRCKO", "5", "output"), ("BCKO", "4", "output"),
    ("SCKO", "3", "output"),
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

body = [symbol("ESP32-WROOM-32", "U", esp_left, esp_right, HALF_W,
               "ESP32-WROOM-32 module, soldered to the milled copper", "esp32 wroom module"),
        symbol("DIR9001-Module", "A", dir_left, dir_right, 12.7,
               "LHY AUDIO DIR9001-I2S board on its 6-wire pigtail", "spdif toslink dir9001"),
        symbol("GY-PCM5102", "A", dac_left, dac_right, 12.7,
               "PCM5102A DAC breakout (GY-PCM5102), 3-wire mode", "dac pcm5102 i2s")]

OUT.write_text('(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "kicad_symbol_editor")\n'
               '\t(generator_version "10.0")\n' + "".join(body) + ')\n', encoding="utf-8")
print("wrote", OUT)
