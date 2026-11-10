# Build notes

Generated from `hardware/surround.kicad_pcb` by `tools/build_notes.py`.
Do not edit by hand; re-run the tool after any change to the board.

The board is 101.9 x 73.2 mm, copper on both faces, no vias and no wire links.

## Before cutting

- **WROOM-32 castellations on the ball mill.** Never cut before. Cut
  `hardware/coupon` first and meter every neighbouring pad pair.
- **First double-sided board on these rules.** The top face is cut after the flip, so
  it depends on the dowel registration. The smallest top-face feature is the 0.5 mm
  ring round a hole, and every ring is cut round a 1.6 mm or larger pad.
- **DAC modules: measured**, 31.0 x 17.1 mm, 1x6 and 1x9 rows. Only the 3.5 mm jack's
  overhang (5.5 mm assumed) is a guess; the modules now sit 25.4 mm apart, which leaves
  8.3 mm for it.
- **DIR9001 board: from the seller's drawing** (LHY AUDIO DIR9001-I2S). Check the wire
  order against the board's I2S-OUT silk before soldering the pigtail.

## Milling

SRM-CAM, profile `SRM-20 0.8 mm ball mill`, **Double-sided**, dowel pins. Load
`hardware/production/gerbers`; do not mirror anything yourself.

1. Air pass, then the two dowel holes.
2. Bottom face: holes, then traces. This face has the WROOM-32 pads and every signal.
3. Flip left to right onto the pins, re-zero Z.
4. Top face: traces. It is a ground plane; the mill cuts a ring round each hole that is
   not ground, and the supply runs below.
5. Cut-out last. Then the silkscreen on the laser from
   `hardware/production/surround_silk_top.dxf`, top face, not mirrored.

## Leads soldered on both faces

The holes are not plated. The two faces meet only where a lead is soldered on the top
as well as the bottom, so **these joints are the board's vias**. Every other lead is
soldered on the bottom only. All of them are parts the iron reaches from the top:
resistors, disc capacitors, LEDs, the 7805 and two wire loops.

| Net | Lead | What it does |
|---|---|---|
| `+3V3` | C9 pad 1 | carries +3V3 between the faces |
| `+3V3` | R15 pad 1 | carries +3V3 between the faces |
| `+3V3` | R16 pad 1 | carries +3V3 between the faces |
| `+5V` | C7 pad 1 | carries +5V between the faces |
| `+5V` | R17 pad 1 | carries +5V between the faces |
| `+5V` | R18 pad 1 | carries +5V between the faces |
| `+5V` | R19 pad 1 | carries +5V between the faces |
| `GND` | C6 pad 2 | 7805 input cap |
| `GND` | C7 pad 2 | +5V cap: ties the copper LRCK and BCK fence in |
| `GND` | C9 pad 2 | ESP32 bypass: its ground lead is module pin 1's way to the plane |
| `GND` | D1 pad 1 | status LED cathode |
| `GND` | D4 pad 1 | power LED cathode: ties the copper between the two data lines |
| `GND` | R11 pad 2 | XSMT pull-down: ties the copper between the two sockets |
| `GND` | R13 pad 2 | LM317 divider |
| `GND` | R7 pad 2 | surround left ring resistor |
| `GND` | R9 pad 2 | surround right ring resistor |
| `GND` | TP1 pad 1 | wire loop: ties the reset parts' ground |
| `GND` | TP2 pad 1 | wire loop: ties module pin 38 |
| `GND` | U2 pad 2 | 7805 centre leg |

19 joints in all. Solder each one on the top, let it flow round the lead, and
meter it to the plane (ground leads) or to the far end of its run (supply leads).
TP1 and TP2 are bare holes: fit a U of solid wire through each as a scope ground loop
and solder it on both faces.

## Top-face copper

| Net | Length | Route |
|---|---:|---|
| `+3V3` | 64 mm | from C9 over the module to R16, then up to R15 |
| `+5V` | 39 mm | from R19 up the east side of the DAC parts to C7, R18 and R17 |

Everything else on the top is ground. No clock, data or audio net leaves the bottom face.

## Pin map

The GPIOs follow the board: each signal leaves the castellation that faces its copper.

| Signal | GPIO | Module pin |
|---|---|---:|
| RESET | EN | 3 |
| DIR9001 DATA in | IO35 | 7 |
| Pot wiper (ADC1) | IO33 | 9 |
| DIR9001 LRCK in (and both DACs) | IO26 | 11 |
| DIR9001 BCK in (and both DACs) | IO14 | 13 |
| DIN surround DAC | IO13 | 16 |
| USER button | IO15 | 23 |
| DIN front DAC | IO2 | 24 |
| BOOT button | IO0 | 25 |
| Status LED | IO17 | 28 |
| XSMT both DACs | IO21 | 33 |
| UART RX | IO3 (RXD0) | 34 |
| UART TX | IO1 (TXD0) | 35 |

IO2 and IO15 are strapping pins. IO2 drives only a DAC input, which leaves it low at
reset as download mode needs. IO15 has only the USER button: do not hold it during
reset or the ROM boot log is silenced. IO14 (BCK) is JTAG TMS until the firmware
starts, which is harmless without a clock on IO13.

## Assembly order

1. U1 first, flat on the bottom face. Tack two opposite corners, then drag-solder the
   castellations. Leave the centre pad unsoldered.
2. Meter neighbouring pins for bridges, especially 1/2/3, 23/24 and 34/35.
3. The parts in the table above next, soldered on both faces, while nothing is in the way:
   R7, R9 and R11 sit under the DAC modules.
4. Then the low parts, the sockets, the cans and the regulators last. C2, C3 and C4 have
   their leads formed out to 5 mm; C11 to 3.5 mm.
5. Power only: 5.0 V at U2, and 3.2 to 3.3 V at U1 pin 2, before any module goes in.
6. U2 and U3 stand on the south edge with their tabs outward: a heatsink on U3 may
   overhang the edge. U2 runs without one.
7. DIR9001 pigtail on A2. Two pairs cross against the cable's order: BCLK with LRCK, and
   +5V with GND. The silk names each hole; go by the names, not the order.

Flashing: 3.3 V UART cable on J2 (TX, RX, GND as marked; cable RX to TX). Hold BOOT, tap
RESET, release.

## Module straps

Set these on the modules before fitting them.

| Module | Strap | Value |
|---|---|---|
| DIR9001 | FMT DIP switch (FMT0, FMT1) | both H: 24-bit I2S |
| DIR9001 | PSCK DIP switch | any: MCLK is not used |
| DIR9001 | input toggle | optical or coax, as wired to the panel |
| DIR9001 | pigtail to A2 | DATA, BCLK, LRCK, +5V, GND to the holes of the same name; MCLK may stay loose; trim it short |
| PCM5102 (both) | SCK | to GND via the socket: 3-wire BCK-PLL mode |
| PCM5102 (both) | FMT | LOW: I2S |
| PCM5102 (both) | FLT | LOW: normal latency filter |
| PCM5102 (both) | DEMP | LOW: de-emphasis off |
| PCM5102 (both) | XSMT | its H jumper removed: meter which one beeps to the XSMT hole |
| PCM5102 (both) | headers | male 1x6 + 1x9 soldered from the COMPONENT side, spacer on that side: the module mounts face down |

## Parts

Same parts as the single-sided board; only footprints and positions changed.

| Part | Qty | Source |
|---|---:|---|
| ESP32-WROOM-32 | 1 | shop: EKB basement stock, ask for it |
| DIR9001-I2S board (LHY AUDIO / Lobamop), with XH pigtail | 1 | buy: bought, Amazon B0HDT4M8QX |
| M3 standoffs for the DIR9001 board | 4 | shop |
| PCM5102 module (AYWHP) | 2 | buy: bought, 3 in hand with one spare |
| RCA panel jack, TRS panel jack | 2 + 2 | buy: order list |
| 9 V 1 A adapter, centre positive | 1 | buy: order list |
| 10K potentiometer | 1 | shop |
| LM7805, LM317T, TO-220 heatsink | 1 + 1 + 1 | shop |
| 1N5817, 1N4003 | 1 + 1 | shop |
| 43R2 (R1-R5) | 5 | shop |
| 100R (R6-R9) | 4 | shop, 1 at home |
| 10k (R11, R14, R15) | 3 | home |
| 10R (R17-R19) | 3 | home 2, shop 1 |
| 1k (R16, R20) | 2 | home 1, shop 1 |
| 332R, 243R, 392R | 1 each | shop |
| 470 uF (C1) | 1 | home: 16 V, fine on 3V3 |
| 100 uF (C2-C4) | 3 | shop |
| 10 uF 50 V (C5, C8) | 2 | home |
| 100 nF disc (C6, C7, C9) | 3 | shop |
| 1 uF 50 V (C11) | 1 | shop |
| 3 mm LED | 2 | shop |
| 6 mm pushbutton | 3 | shop |
| 2-pole, 3-pole screw terminal | 3 + 2 | shop |
| Female header 1x6, 1x9 | 2 + 2 | shop (1x9 cut from a longer strip) |
| Male header 1x6, 1x9 | 2 + 2 | shop, for the DAC modules |
| Male header 1x3 | 2 | shop |
| Solid wire for TP1, TP2 | 2 loops | home |
| Double-sided copper-clad, 1.6 mm | about 115 x 85 mm | shop: ask; the dowels need 11 mm of waste beyond the outline |

## Panel parts

J1 takes the 9 V adapter (centre positive; `+9V` and `GND` are marked). J3 and J4 are the
RCA fronts, J5 and J6 the TRS surrounds. J7 is the volume pot: 3V3, wiper, GND.
