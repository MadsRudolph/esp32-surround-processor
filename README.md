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
| `hardware/BUILD-NOTES.md` | Generated from the board: what to check before cutting, the wire link, assembly order, module straps. |
| `hardware/production` | Gerber and Excellon for SRM-CAM, silkscreen DXF for the laser. |
| `hardware/coupon` | WROOM-32 land-pattern test coupon. Cut this first. |
| `lib/Surround.kicad_sym` / `lib/Surround.pretty` | Project symbols and footprints. Generated. |
| `tools/make_symbols.py` / `make_footprints.py` | Generate the two libraries. |
| `tools/surround_layout.py` | Generates `hardware/surround.kicad_sch`. The schematic is code; edit the script, not the file. |
| `tools/pcb_bootstrap.py` | Netlist JSON -> board with footprints, nets, outline, mounting holes, GND pour, cnc-fine netclass. |
| `tools/surround_board.py` | The floorplan, routing lanes and silkscreen, as code. Its header explains the topology. |
| `tools/octoroute.py` / `autoroute.py` | Single-layer octilinear router: 45-degree runs, no turn over 45 degrees, exact clearance. Follows the lanes in `surround_board.py`, then routes the rest. |
| `tools/preview.sh` | Renders the board (copper + laser silk) to a PNG for a live preview. |
| `tools/netclasses.py` | Stamps the track widths and net-class assignments into the project. |
| `tools/impedance.py` | Coplanar-waveguide impedance of the traces, and the series termination it implies. |
| `tools/wire_links.py` | Lists every wire link and fails if one lands on a net that may not be a wire. |
| `tools/build_notes.py` | Generates `hardware/BUILD-NOTES.md`. |
| `tools/make_coupon.py` / `export_production.sh` | The coupon, and the production files. |
| `tools/kpy.py` | Launcher that patches this KiCad build's pcbnew iterator bug. |

## Rebuilding

Close KiCad first (Eeschema does not reload a file changed underneath it), then:

```bash
python3 tools/make_symbols.py && python3 tools/make_footprints.py
python3 tools/netclasses.py
python3 tools/surround_layout.py                 # schematic
cd hardware
kicad-cli sch erc --severity-all -o surround.erc surround.kicad_sch
kicad-cli sch export pdf -o surround.pdf surround.kicad_sch
kicad-cli sch export netlist --format kicadsexpr -o surround.net surround.kicad_sch
python3 ~/.claude/skills/kicad-laser-pcb/scripts/pcb_netlist_json.py surround.net surround.json
cd ..
python3 tools/pcb_bootstrap.py 103x69
python3 tools/kpy.py tools/surround_board.py     # placement, copper, pour, GND links, silk
kicad-cli pcb drc --severity-all hardware/surround.kicad_pcb
python3 tools/kpy.py tools/wire_links.py hardware/surround.kicad_pcb
python3 tools/kpy.py tools/build_notes.py hardware/surround.kicad_pcb
tools/export_production.sh hardware/surround.kicad_pcb hardware/production
python3 tools/kpy.py tools/make_coupon.py
tools/export_production.sh hardware/coupon/wroom_coupon.kicad_pcb hardware/coupon/production
```

The layout script uses the `kicad-schematic` skill's drawing DSL
(`~/.claude/skills/kicad-schematic/scripts`).

## Fabrication and the rules that follow from it

Copper is isolation-milled on the bottom layer with an **0.8 mm ball mill** at
0.08 mm deep, SRM-CAM profile `SRM-20 0.8 mm ball mill`. Through-hole parts go on
top, the WROOM-32 on the milled side, silkscreen by fiber laser.

| | value | why |
|---|---|---|
| clearance | 0.50 mm | the measured 0.44 mm channel plus margin (`cnc-fine`) |
| ESP32 track | 0.90 mm | the width of its pads; 76 ohm against the pour |
| other signal track | 0.50 mm | short links past the series resistors, audio |
| power track | 1.0 mm | 37 mV at 0.5 A over 150 mm |
| WROOM pad gap | 0.37 mm | fixed by the module; tracks keep it until they fan out. Documented exception, one middle cut trims both sides |
| minimum hole | 0.8 mm | the bit's own diameter |

**Not proven:** these are the first 0.50/0.50 rules on a real routed board, and no
WROOM-32 has been cut on this bit. Cut `hardware/coupon` first.

## Routing rules

`tools/octoroute.py` builds them into every run it lays:

- every segment is horizontal, vertical or exactly 45 degrees;
- no run turns by more than 45 degrees;
- every net with a pad on the ESP32 is 0.9 mm, the width of its pads.

Where one trace branches off another it can still leave at a right angle, and two
runs may meet at any angle on a pad.

## Wires and hand routing

The clocks, the I2S data and the DAC outputs are all milled copper. The ground
pour is split by the module-to-DAC bundle and the clock runs, so a few short
ground links join its islands; the pocket between the DAC sockets is one of them.
The router leaves a handful of power and slow nets for hand routing. Both lists
are generated into `hardware/BUILD-NOTES.md`. There are no vias.

A second copper layer as a ground plane would replace those wires. It would need
isolation around every non-ground hole on top, ground pins soldered on both sides
where a socket body does not block the iron, double-sided stock, and a re-derived
trace impedance, because the plane changes it.

## Board concept

A 103 x 69 mm single-sided board:

- 9 V adapter on a screw terminal, 1N5817 reverse protection
- LM7805 for the audio modules, with 10 R + 100 uF per module
- LM317T at 3.27 V for the ESP32, 470 uF + 100 nF at pin 2, 1N4003 protection
- ESP32-WROOM-32 on the milled side at the east edge, antenna pointing off the board, its keep-out starting exactly at the edge
- DIR9001-I2S board off the carrier on its pigtail; two PCM5102 modules face down on a 1x6 and a 1x9 socket, so XSMT and the outputs are socketed too
- 43.2 R series resistors at the driver end of every clock and data line
- 10 k pull-down on XSMT so both DACs are muted through boot
- RCA outputs for the fronts, impedance-balanced TRS (100 R tip / 100 R ring) for the surrounds, all panel-mount on screw terminals
- RESET, BOOT and USER buttons, status and power LEDs, UART header, 3-pin header for a panel volume pot

Module straps are in `hardware/BUILD-NOTES.md`.

## Status

- [x] Design review
- [x] Schematic (ERC clean, netlist checked)
- [x] Footprints, audited against the ball mill
- [x] Compact placement (103 x 69 mm), antenna off the edge, laser silkscreen
- [ ] Finish hand routing (open nets in `hardware/BUILD-NOTES.md`)
- [ ] Production files for this layout
- [x] DAC modules measured; DIR9001 pinout from the seller's drawing
- [ ] Cut and meter the WROOM coupon
- [ ] Firmware (ESP-IDF v5.3, `driver/i2s_std.h`, liba52 for AC-3)
