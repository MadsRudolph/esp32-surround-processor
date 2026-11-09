# Build notes

Generated from `hardware/surround.kicad_pcb` by `tools/build_notes.py`.
Do not edit by hand; re-run the tool after any change to the board.

## Before cutting

One thing is not yet proven on the part in hand:

- **DAC modules: measured** under the microscope, 31.0 x 17.1 mm, 1x6 and 1x9 rows.
  Only the 3.5 mm jack's overhang (5.5 mm assumed) is a guess; nothing tall sits there.
- **DIR9001 board: from the seller's drawing** (LHY AUDIO DIR9001-I2S, 64 x 48 mm).
  It mounts off the carrier; its XH pigtail lands on A2. Check wire order against the
  board's I2S-OUT silk: DATA BCLK LRCK MCLK +5V GND.
- **WROOM-32 castellations on the ball mill.** Never cut before. Cut
  `hardware/coupon` first and meter every neighbouring pad pair.

## Wire links

The board is single sided: the only copper the mill cuts is on the bottom. A link
is an insulated solid-core wire, 0.4 to 0.5 mm. Lap it onto the two pads on the
copper side, since socket pins fill the holes. The I2S clocks and data and the DAC
outputs may not be links; `tools/wire_links.py` fails the build if one appears.

4 link(s), 55 mm of wire in total.

| Net | From | To | Length |
|---|---|---|---:|
| `GND` | A2.2 | D4.1 | 16.9 mm |
| `GND` | C11.2 | R13.2 | 16.0 mm |
| `GND` | C1.2 | C4.2 | 11.0 mm |
| `GND` | SW3.2 | C3.2 | 11.0 mm |

Every link is a ground link between pour islands that the single copper layer
cannot join: the module-to-DAC bundle and the clock runs cut the pour. The pocket
between the DAC sockets (A4.2, A3.6, C3) is the island the DAC column traps; its
link is not optional.

## Left for hand routing

17 unconnected item(s) after the router (`tools/octoroute.py`). In KiCad
these show as ratsnest lines; route them, or add links, before cutting:

- `+5V` (5 gap(s))
- `+9V` (5 gap(s))
- `EN` (4 gap(s))
- `GND` (2 gap(s))
- `USER` (1 gap(s))

## Pin map

The GPIOs follow the board: each signal leaves the castellation that faces its copper.

| Signal | GPIO (pin) | Signal | GPIO (pin) |
|---|---|---|---|
| DIR DATA in | IO34 (6) | DIN front DAC | IO17 (28) |
| DIR LRCK in | IO33 (9) | DIN surround DAC | IO18 (30) |
| DIR BCK in | IO27 (12) | XSMT both DACs | IO19 (31) |
| Pot (ADC1_CH0) | IO36 (4) | USER button | IO16 (27) |
| BOOT button | IO0 (25) | Status LED | IO4 (26) |

## Assembly order

1. U1 first, flat on the milled side. Tack two opposite corners, then drag-solder the
   castellations. Leave the centre pad unsoldered.
2. Meter neighbouring pins for bridges, especially 1/2/3, 34/35 and 25/26.
3. The ground links, then the low through-hole parts, the sockets, and the regulators last.
   The DAC modules float over parts under them: fit R6-R9, R11 and C3 before their sockets.
4. Power only: 5.0 V at U2, and 3.2 to 3.3 V at U1 pin 2, before any module goes in.
   C11 has its leads formed out to the 3.5 mm footprint.
5. U2 and U3 stand on the south edge with their tabs outward: a heatsink on U3 may
   overhang the edge. U2 runs without one.
6. DIR9001 pigtail on A2: BCLK and LRCK land swapped against the cable's order
   (the silk names each hole). The other four go straight across.

Flashing: 3.3 V UART cable on J2 (pin 1 TXD0, pin 2 RXD0, pin 3 GND; cable RX to TXD0). Hold BOOT, tap
RESET, release.

## Module straps

Set these on the modules before fitting them.

| Module | Strap | Value |
|---|---|---|
| DIR9001 | FMT DIP switch (FMT0, FMT1) | both H: 24-bit I2S |
| DIR9001 | PSCK DIP switch | any: MCLK is not used |
| DIR9001 | input toggle | optical or coax, as wired to the panel |
| DIR9001 | pigtail to A2 | DATA->DATA, BCLK->BCLK, LRCK->LRCK, MCLK->MCLK, +5V->+5V, GND->GND; trim it short |
| PCM5102 (both) | SCK | to GND via the socket: 3-wire BCK-PLL mode |
| PCM5102 (both) | FMT | LOW: I2S |
| PCM5102 (both) | FLT | LOW: normal latency filter |
| PCM5102 (both) | DEMP | LOW: de-emphasis off |
| PCM5102 (both) | XSMT | its H jumper removed: meter which one beeps to the XSMT hole |
| PCM5102 (both) | headers | male 1x6 + 1x9 soldered from the COMPONENT side, spacer on that side: the module mounts face down |

## Parts

| Part | Qty | Source |
|---|---:|---|
| ESP32-WROOM-32 | 1 | shop: EKB basement stock, ask for it |
| DIR9001-I2S board (LHY AUDIO / Lobamop), with XH pigtail | 1 | bought: Amazon B0HDT4M8QX |
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
| 100 nF (C6, C7, C9) | 3 | shop |
| 1 uF 50 V (C11) | 1 | shop |
| 3 mm LED | 2 | shop |
| 6 mm pushbutton | 3 | shop |
| 2-pole, 3-pole screw terminal | 3 + 2 | shop |
| Female header 1x6, 1x9 | 2 + 2 | shop (1x9 cut from a longer strip) |
| Male header 1x6, 1x9 | 2 + 2 | shop, for the DAC modules |
| Male header 1x3 | 2 | shop |
| TP1, TP2 | 2 | bare pads, nothing to fit |

## Panel parts

J1 takes the 9 V adapter (centre positive; pad 1 is +). J3 and J4 are the RCA fronts,
J5 and J6 the TRS surrounds. J7 is the volume pot: 3V3, wiper, GND.

## Still open

These are **not finished** and must be completed in the KiCad board editor
before the board is cut:

- PTH pad 3 [+5V] of U2 to PTH pad 1 [+5V] of C7
- PTH pad 1 [+5V] of R18 to PTH pad 1 [+5V] of R17
- PTH pad 1 [+5V] of R17 to PTH pad 1 [+5V] of C7
- PTH pad 1 [+5V] of C7 to PTH pad 1 [+5V] of C8
- PTH pad 1 [+5V] of C8 to PTH pad 1 [+5V] of R19
- Zone 'GND_pour' [GND] on B.Cu, priority 0 to PTH pad 3 [GND] of J2
- Zone 'GND_pour' [GND] on B.Cu, priority 0 to Zone 'GND_pour' [GND] on B.Cu, priority 0
- PTH pad 1 [+9V] of D2 to PTH pad 1 [+9V] of C5
- PTH pad 1 [+9V] of C6 to PTH pad 1 [+9V] of C5
- PTH pad 1 [+9V] of U2 to PTH pad 1 [+9V] of C6
- PTH pad 1 [+9V] of U2 to PTH pad 3 [+9V] of U3
- PTH pad 3 [+9V] of U3 to PTH pad 1 [+9V] of D3
- PTH pad 1 [EN] of C11 to PTH pad 2 [EN] of R14
- PTH pad 1 [EN] of SW1 to PTH pad 2 [EN] of R14
- PTH pad 1 [EN] of SW1 to PTH pad 1 [EN] of SW1
- PTH pad 1 [EN] of SW1 to Pad 3 [EN] of U1 on B.Cu
- PTH pad 1 [USER] of SW3 to PTH pad 1 [USER] of SW3
