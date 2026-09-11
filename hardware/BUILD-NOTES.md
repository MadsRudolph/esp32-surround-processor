# Build notes

Generated from `hardware/surround.routed.kicad_pcb` by `tools/build_notes.py`.
Do not edit by hand; re-run the tool after any change to the board.

## Wire links

The board is single sided: the only copper the mill cuts is on the bottom.
Every link below is a **wire soldered on the component side between two
through-hole pads**. No via is drilled for any of them, because a through-hole
pad already exists on both sides of the board.

Only DC rails, ground, and slow control lines are allowed to be links. The I2S
clock and data nets and the DAC outputs are pinned to milled copper for the
whole route, because a wire standing off the board is an uncontrolled-impedance
stub with a large loop area, which is the wrong thing to hang a 3 MHz clock or a
line-level audio output on. `tools/wire_links.py` fails the build if one appears
on a net that is not allowed to carry it.

Use insulated solid core, 0.4 to 0.5 mm. Keep each wire flat against the board.

19 links, 737 mm of wire in total.

| Net | From | To | Length |
|---|---|---|---:|
| `+3V3` | A2.10 | A1.1 | 26.9 mm |
| `+5V` | FB3.1 | FB1.1 | 63.3 mm |
| `+5V` | C1.1 | F1.2 | 9.2 mm |
| `+5V_DAC1` | A3.1 | C2.1 | 61.0 mm |
| `+5V_DAC2` | C3.1 | A4.1 | 30.5 mm |
| `+5V_DIR` | FB3.2 | C4.1 | 5.3 mm |
| `GND` | R10.2 | A1.14 | 94.8 mm |
| `GND` | C1.2 | A3.6 | 40.0 mm |
| `GND` | A1.20 | A2.2 | 29.0 mm |
| `GND` | SW1.C | C3.2 | 24.6 mm |
| `GND` | J6.S | R9.2 | 16.1 mm |
| `GND` | R11.2 | D1.1 | 5.7 mm |
| `Net-(A1-IO36{slash}VP)` | A2.8 | A1.3 | 32.8 mm |
| `Net-(A1-IO39{slash}VN)` | A1.4 | A2.7 | 35.7 mm |
| `Net-(F1-Pad1)` | F1.1 | J1.1 | 7.7 mm |
| `SCL` | A1.22 | J7.3 | 73.9 mm |
| `SDA` | J7.4 | A1.25 | 78.1 mm |
| `XSMT` | A4.7 | R11.1 | 53.9 mm |
| `XSMT` | A1.10 | A3.7 | 48.9 mm |

The ground links are not optional. On a single-sided board every track is a slot
cut through the ground pour, and without these wires the pour fills as nine
separate islands with no return path between them.

## Module straps

Set these on the modules before fitting them.

| Module | Strap | Value |
|---|---|---|
| DIR9001 | FMT1, FMT0 | both HIGH: 24-bit I2S |
| DIR9001 | CKSEL | LOW: always the recovered PLL clock |
| DIR9001 | XTI | to DGND, no crystal fitted |
| DIR9001 | PSCK1, PSCK0 | both LOW: SCKO at 128 fs, unused |
| GY-PCM5102 (both) | SCK | to GND: 3-wire BCK-PLL mode |
| GY-PCM5102 (both) | FMT | LOW: I2S |
| GY-PCM5102 (both) | FLT | LOW: normal latency filter |
| GY-PCM5102 (both) | DEMP | LOW: de-emphasis off |
| GY-PCM5102 (both) | XSMT | bridge removed, wired to the carrier |

## Panel parts

The audio jacks and the encoder are panel mounted and wired to the board, because
every PCB-mount RCA, TRS and EC11 footprint has pad gaps under the 0.8 mm the end
mill needs. J3 and J4 are the front outputs on 2-pin terminals, J5 and J6 the
surrounds on 3-pin terminals, SW1 a 5-pin header for the encoder.

## Still open

These are **not finished** and must be completed in the KiCad board editor
before the board is cut:

- Zone 'GND_pour' [GND] on B.Cu, priority 0 to Zone 'GND_pour' [GND] on B.Cu, priority 0
- PTH pad 4 [Net-(A3-DIN)] of A3 to PTH pad 2 [Net-(A3-DIN)] of R4
