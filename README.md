# ESP32 4.0 surround processor

A low-cost 4.0 surround processor: TV optical out (2-ch PCM or Dolby Digital
AC-3) in, front L/R line out to a Fosi stereo amp and JBL 4412s, surround L/R
line out to PreSonus Eris 3.5 monitors.

Signal chain: TOSLINK -> DIR9001 (clock recovery) -> ESP32 as I2S **slave** on
both ports -> 2x PCM5102A in 3-wire BCK-PLL mode -> line out.

## Layout

| Path | What |
|---|---|
| `design-review.md` | Engineering review: clocking, pinout, wiring, power, grounding, firmware and buffer sizing. Read this first. |
| `hardware/surround.kicad_pro` / `.kicad_sch` / `.kicad_pcb` / `.kicad_dru` | KiCad 10 project, schematic, board and the DRC exceptions. |
| `hardware/BUILD-NOTES.md` | Generated from the board: what to check before cutting, the milling order, the leads soldered on both faces, assembly order, module straps. |
| `hardware/production` | Gerber (both faces) and Excellon for SRM-CAM, silkscreen DXF for the laser. |
| `hardware/coupon` | WROOM-32 land-pattern test coupon. Cut this first. |
| `lib/Surround.kicad_sym` / `lib/Surround.pretty` | Project symbols and footprints. Generated. |
| `tools/build.sh` | Rebuilds everything below in order and runs every check. |
| `tools/make_symbols.py` / `make_footprints.py` | Generate the two libraries. |
| `tools/surround_layout.py` | Generates `hardware/surround.kicad_sch`. The schematic is code; edit the script, not the file. |
| `tools/netlist_json.py` / `pcb_bootstrap.py` | Netlist -> board with footprints, nets, outline, mounting holes and the cnc-fine netclass. |
| `tools/surround_board.py` | The floorplan, the routing lanes on both faces and the silkscreen text, as code. Its header explains the topology. |
| `tools/octoroute.py` / `route2.py` | Octilinear router (45-degree runs, no turn over 45 degrees, exact clearance), run once per face. |
| `tools/silk.py` | Lays the silkscreen out for the laser: nothing on a pad, every pin named. |
| `tools/check_board.py` | Proves the board is connected with bare holes, using only leads that can be soldered from the top. |
| `tools/preview.sh` | Renders the board to a PNG. |
| `tools/netclasses.py` | Stamps the track widths and net-class assignments into the project. |
| `tools/impedance.py` | Impedance of the traces over the ground plane, and the series termination it implies. |
| `tools/build_notes.py` | Generates `hardware/BUILD-NOTES.md`. |
| `tools/make_coupon.py` / `export_production.sh` | The coupon, and the production files. |
| `tools/bench_server.py` / `bench_page.html` / `bench.py` | Bench page (AD3 scope, rail watch, UART, test procedure) and its terminal fallback. See Bench. |
| `tools/kpy.py` | Launcher that patches this KiCad build's pcbnew iterator bug. |

## Rebuilding

Close KiCad first (Eeschema does not reload a file changed underneath it), then:

```bash
python3 tools/make_footprints.py     # only after a footprint change
tools/build.sh                       # schematic, ERC, board, DRC, connectivity, notes, production
```

**The board file now carries hand edits** made in the PCB editor after the scripted
build: rounded outline, chamfered track corners, C9 turned. `tools/build.sh` rebuilds
the board from code and would discard them. After a hand change, re-export and
re-check without rebuilding:

```bash
tools/export_production.sh hardware/surround.kicad_pcb hardware/production
python3 tools/kpy.py tools/check_board.py hardware/surround.kicad_pcb
python3 tools/kpy.py tools/build_notes.py hardware/surround.kicad_pcb
```

The layout script uses the `kicad-schematic` skill's drawing DSL
(`~/.claude/skills/kicad-schematic/scripts`).

## Bench

Bring-up runs from a local page that is both the test procedure and the Analog
Discovery 3's display: live scope on both rails (DC and a high-resolution ripple view),
rail check, ripple, a rail watch for brown-outs, and a UART console on J2 TX. Start it
and open <http://127.0.0.1:8791/>:

```bash
python3 tools/bench_server.py
```

The server owns the AD3 (close WaveForms first, or press *Release AD3* on the page to
hand it back). Results are saved to `hardware/bench/results.json`; *Reset run* archives
them in `hardware/bench/runs/`. The steps are one array, `STEPS`, at the top of the
script in `tools/bench_page.html`. `tools/bench.py` still does the same checks from the
terminal when the server is not running.

## Fabrication and the rules that follow from it

Both faces are isolation-milled with an **0.8 mm ball mill** at 0.08 mm deep, SRM-CAM
profile `SRM-20 0.8 mm ball mill`, double-sided on dowel pins. Through-hole parts go on
top, the WROOM-32 on the bottom, silkscreen by fiber laser on the top.

| | value | why |
|---|---|---|
| clearance | 0.50 mm | the measured 0.44 mm channel plus margin (`cnc-fine`) |
| ESP32 track | 0.90 mm | the width of its pads; 71 ohm over the plane |
| other signal track | 0.50 mm | short links past the series resistors, audio, EN |
| power track | 1.0 mm | 37 mV at 0.5 A over 150 mm |
| WROOM pad gap | 0.37 mm | fixed by the module. Documented exception, one middle cut trims both sides |
| minimum hole | 0.8 mm | the bit's own diameter |

**Not proven:** these are the first 0.50/0.50 rules on a real routed board, the first
board cut on both faces with them, and no WROOM-32 has been cut on this bit. Cut
`hardware/coupon` first.

## Two faces, bare holes

The holes are not plated and there are no vias, so the board is designed around where
the two faces can really meet:

- **Bottom:** every clock, data and audio track, the supplies, and the WROOM-32.
- **Top:** a ground plane. The mill cuts only a 0.5 mm ring round each hole that is not
  ground, plus two supply runs: +5V to the DAC feed resistors and +3V3 to the BOOT
  pull-up and the power LED.
- **The faces meet at 19 leads soldered on both sides**, all of them parts the iron
  reaches from the top: resistors, disc capacitors, LEDs, the 7805 and two wire loops
  that double as scope grounds. `hardware/BUILD-NOTES.md` lists them.

KiCad treats every through hole as plated, so its DRC cannot see an open circuit here.
`tools/check_board.py` rebuilds the connectivity from the copper, face by face, and
fails the build if any net needs a joint that cannot be made.

Wherever the tracks fence off a patch of bottom-face ground, a part with a
top-solderable ground lead stands in it: R11 between the DAC sockets, C7 where LRCK and
BCK close a loop, the power LED between the two data lines, C9 under module pin 1.

## Routing rules

`tools/octoroute.py` builds them into every run it lays:

- every segment is horizontal, vertical or exactly 45 degrees;
- no run turns by more than 45 degrees;
- every net with a pad on the ESP32 is 0.9 mm, the width of its pads (EN is 0.5 mm);
- used module pins alternate with free ones wherever the pinout allows, so their tracks
  leave 1.6 mm apart instead of 0.37 mm.

## Board concept

A 101.9 x 73.3 mm double-sided board, parts on a 1.27 mm grid:

- west edge: RCA and TRS outputs on screw terminals, the first terminal of each DAC
  level with that DAC's output row
- two PCM5102 modules face down on sockets, 25.4 mm apart, as two identical blocks: data
  resistor, 100 uF and 10 R feed all straddle the BCK trunk, which runs dead straight
- ESP32-WROOM-32 on the bottom at the east edge, antenna off the board, centred so the
  two DAC data lines leave it as mirror images
- under the module: 43.2 R series resistors on alternate pins for the DIR9001 lines,
  the pigtail holes below them; reset parts and the 470 uF down the east edge
- 9 V in on a screw terminal, 1N5817, LM7805 for the audio modules with 10 R + 100 uF
  per module, LM317T at 3.27 V for the ESP32; both regulators on the south edge, tabs out,
  on one +9V rail
- BOOT, status LED and UART along the north edge; USER and the power LED west of the
  module; 3-pin header for a panel volume pot

Module straps are in `hardware/BUILD-NOTES.md`.

## Firmware

ESP-IDF v5.5, in `firmware/`. Three projects share the components in `firmware/components/`.

| Path | What |
|---|---|
| `firmware/surround/` | **The firmware.** Dolby Digital 5.1 and stereo matrix decoding to four outputs. |
| `firmware/passthrough/` | Bring-up: the DIR9001's stereo straight to both DACs. |
| `firmware/boardtest/` | Bring-up without the DIR9001: the ESP32 makes the clocks and plays a 1 kHz tone on one output at a time. |
| `firmware/components/netota/` | Wi-Fi, over-the-air update with rollback, `/status` and `/set` over HTTP. |
| `firmware/components/dolby/` | Finds IEC 61937 bursts in the S/PDIF data and maps decoded 5.1 to four speakers. Plain C, also built on a PC by `tools/dolby_test.sh`. |
| `firmware/components/liba52/` | liba52 0.7.4, the AC-3 decoder. **GPL-2.0-or-later** (see `COPYING` there), so firmware built with it is GPL. One change from the original, noted in its `CMakeLists.txt`. |
| `firmware/components/esp_driver_i2s/` | ESP-IDF's I2S driver with one fix (below). Overrides the IDF copy. |

What `firmware/surround` does:

- **Dolby Digital (AC-3) bitstream:** decoded on the ESP32. Centre is folded into the fronts, the
  LFE channel is added to both fronts (the subwoofer is fed from them), surround left and right go
  straight to the rear outputs. About 5 ms of decode per 32 ms frame at 240 MHz.
- **Stereo PCM:** fronts untouched; rear = 0.5 x (L - R), high-pass 100 Hz, low-pass 7 kHz, 20 ms
  delay, the same signal to both rears.
- **DTS, Dolby Digital Plus:** recognised and kept silent.
- Volume on the pot (J7), mute on USER, mode on BOOT. It starts muted.

```bash
cp firmware/wifi_secrets.h.example firmware/wifi_secrets.h   # then fill it in; it is not in git
. ~/esp/esp-idf/export.sh
idf.py -C firmware/surround build
tools/ota.sh surround            # build and flash over Wi-Fi (the first flash goes over J2)
tools/dolby_test.sh film.mkv     # run the parser and decoder on a PC against any AC-3 track
```

Two faults found during bring-up, both heard as loud clicks:

- **Data lines driven too hard.** At the ESP32's default drive strength the two I2S data outputs
  disturbed the shared clock lines whenever both switched together, and the DACs misread bits.
  The firmware sets `GPIO_DRIVE_CAP_0` on both; clicks start at `CAP_2` and are severe at `CAP_3`.
- **A lost-interrupt bug in ESP-IDF's I2S driver** (v5.5, classic ESP32, full duplex): the RX and
  TX handlers share one interrupt and each cleared every pending flag, so one erased the other's
  event and a 5 ms buffer went missing. Fixed in `firmware/components/esp_driver_i2s`.

And one in liba52: its FFT kept temporaries in `double`, which the ESP32 computes in software. As
`float` the decode time fell from 21 ms to under 5 ms per frame.

The debug page (`tools/debug_page.html`, served by the bench server at `/debug`) shows the input
format, levels and decoder health live, and has a per-speaker test (chime or sine sweep).

## Status

- [x] Design review
- [x] Schematic (ERC clean)
- [x] Footprints, audited against the ball mill
- [x] Double-sided placement and routing: DRC clean, nothing unconnected, no vias, no links
- [x] Connectivity proven with bare holes (`tools/check_board.py`)
- [x] Laser silkscreen
- [x] Production files; SRM-CAM builds the double-sided job from them (about 1 h 40 min)
- [x] DAC modules measured; DIR9001 pinout from the seller's drawing
- [x] Board cut, soldered and brought up: rails, all four outputs, DIR9001 input (`hardware/bench/results.json`)
- [x] Firmware: stereo matrix and Dolby Digital 5.1, tested with the TV on four speakers
- [ ] The XSMT mute line does not mute the DAC modules (their own strap is probably still fitted); mute is done in the data
- [ ] Own AC-3 decoder in place of liba52
