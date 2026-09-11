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
| `hardware/surround.kicad_pro` / `.kicad_sch` / `.kicad_pcb` / `.kicad_dru` | KiCad 10 project, schematic, board and the mill DRC exceptions. |
| `lib/Surround.kicad_sym` | Project symbols for the three modules (ESP32-DevKitC-38, DIR9001 module, GY-PCM5102). Generated. |
| `lib/Surround.pretty` | Project footprints: module carriers, panel-part terminals, mill-safe LED pads. Generated. |
| `tools/make_symbols.py` / `make_footprints.py` | Generate the two libraries. |
| `tools/surround_layout.py` | Generates `hardware/surround.kicad_sch`. The schematic is code; edit the script, not the file. |
| `tools/pcb_bootstrap.py` | Netlist JSON -> board with footprints, nets, outline, mounting holes, GND pour, cnc netclass. |
| `tools/surround.placement.json` / `apply_placement.py` | The hand floorplan (anchor x, y, rot per part) and the script that applies it. |
| `tools/netclasses.py` | Stamps the track widths and net-class assignments into the project. |
| `tools/impedance.py` | Coplanar-waveguide impedance of the traces, and the series termination it implies. |
| `tools/route.sh` | The routing pipeline: FreeRouting best-of-three, then a pre-routed retry, then the wire-link check. |
| `tools/dsn_export.py` / `dsn_restrict.py` / `ses_import.py` | Specctra round trip, with the fast nets pinned to the bottom layer. |
| `tools/finish_route.py` | A* finisher for links FreeRouting cannot reach. |
| `tools/gnd_stitch.py` | Finds the ground-pour islands and routes wire links to rejoin them. |
| `tools/wire_links.py` | Lists every wire link and fails if one lands on a net that may not be a wire. |
| `tools/build_notes.py` | Generates `hardware/BUILD-NOTES.md` from the routed board. |
| `tools/finalize_pcb.py` / `kpy.py` | Pour refill; launcher that patches this KiCad build's pcbnew iterator bug. |

## Regenerating the schematic

Close KiCad first (Eeschema does not reload a file changed underneath it), then:

```bash
python3 tools/make_symbols.py
python3 tools/surround_layout.py
cd hardware
kicad-cli sch erc --severity-all -o surround.erc surround.kicad_sch
kicad-cli sch export pdf -o surround.pdf surround.kicad_sch
```

The layout script uses the `kicad-schematic` skill's drawing DSL
(`~/.claude/skills/kicad-schematic/scripts`).

## Rebuilding the board

```bash
python3 tools/make_symbols.py && python3 tools/make_footprints.py
python3 tools/netclasses.py
python3 tools/surround_layout.py                 # schematic
cd hardware
kicad-cli sch erc --severity-all -o surround.erc surround.kicad_sch
kicad-cli sch export netlist --format kicadsexpr -o surround.net surround.kicad_sch
python3 ~/.claude/skills/kicad-laser-pcb/scripts/pcb_netlist_json.py surround.net surround.json
cd ..
python3 tools/pcb_bootstrap.py 140x110           # board, outline, pour, netclasses
python3 tools/apply_placement.py                 # the floorplan
./tools/route.sh                                 # FreeRouting + checks
python3 tools/kpy.py tools/gnd_stitch.py hardware/surround.routed.kicad_pcb \
        --write hardware/surround.routed.kicad_pcb
python3 tools/kpy.py tools/build_notes.py hardware/surround.routed.kicad_pcb
kicad-cli pcb drc --severity-all hardware/surround.routed.kicad_pcb
```

Routing needs `~/.freerouting/freerouting-2.4.1.jar`. FreeRouting is not
deterministic on this board, so the script routes three times and keeps the best.

## Fabrication and the rules that follow from it

Copper is isolation-milled on the bottom layer with an **0.8 mm flat end mill**,
through-hole parts on top, silkscreen by fiber laser.

The limit the process imposes is on the copper **gap**, which is what the mill
cuts. It is not a limit on track width. That distinction sets most of the numbers:

| | value | why |
|---|---|---|
| clearance | 0.85 mm | 0.8 mm cutter plus margin for runout |
| signal track | 0.8 mm | pitch is width + clearance, and 0.8 mm is what makes the corridor beside the DAC headers take two tracks instead of one |
| power track | 1.5 mm | 25 mV of drop at 0.5 A over 150 mm |
| minimum hole | 0.8 mm | |
| annular ring | ≥ 0.4 mm | the stock barrel-jack footprint gave 0.25 mm and was replaced |

Every footprint was audited against the 0.8 mm floor. The 2.54 mm socket rows come
out at 0.84 mm pad to pad, which the mill still clears in one pass; those carry
documented exceptions in `surround.kicad_dru`.

## Wire links, and what is not allowed to be one

The top side has no milled copper, so anything the router puts on the top layer
is a wire soldered between two through-hole pads. No vias are drilled for them.

The I2S clocks and data and the DAC outputs are **pinned to the bottom layer for
the whole route**: a wire standing off the board is an uncontrolled-impedance stub
with a large loop area, which is the wrong thing to hang a 3 MHz clock or a
line-level output on. DC rails, ground and slow control lines may be links.
`tools/wire_links.py` fails the build if a link appears on a net that may not
carry one, and `hardware/BUILD-NOTES.md` lists every wire to solder.

## Board concept

A 140 x 110 mm single-sided carrier PCB with pin sockets for the three breakout
modules, plus the passives that the modules do not carry:

- 5 V barrel jack, 1.1 A PTC, 470 uF bulk, and a ferrite + 100 uF branch per module rail
- 33 R series resistors at the driver end of every clock and data line
- 10 k pull-down on XSMT so both DACs are muted through boot
- RCA outputs for the fronts, impedance-balanced TRS (100 R tip / 100 R ring) for the surrounds
- 5-pin header for a panel-mount rotary encoder, status LED, 4-pin socket for an SSD1306 I2C OLED

The audio jacks and the encoder are panel-mount parts on flying leads: every
PCB-mount RCA/TRS jack and the EC11 encoder have pad gaps under the 0.8 mm the
end mill needs. The ESP32 footprint assumes the official DevKitC V4 with 25.4 mm
between socket rows; 38-pin clones use 22.86 mm, so measure the board in hand
and change `ROW` in `tools/make_footprints.py` if needed. The GY-PCM5102 body
size (22 x 32 mm) and the DIR9001 module pinout are also assumptions to verify
against the real modules before cutting copper.

Module straps (set on the modules, documented on the schematic):
DIR9001 FMT1 = FMT0 = H, CKSEL = L, XTI = GND, PSCK = LL.
PCM5102A SCK = GND, FMT = L, FLT = L, DEMP = L, XSMT bridge removed and wired to the carrier.

## Status

- [x] Design review
- [x] Schematic (ERC clean, netlist checked against the review)
- [x] Footprints, all audited against the 0.8 mm end mill
- [x] Placement
- [x] Routing: 47 of 48 nets, zero clearance violations, no vias, every wire link on a permitted net
- [ ] Two items to close in the KiCad board editor, listed at the end of `hardware/BUILD-NOTES.md`:
      one data link (A3 pad 4 to R4 pad 2) and one ground-island pair
- [ ] Production files (Gerber + Excellon for CAM, silkscreen DXF for the laser)
- [ ] Firmware (ESP-IDF v5.3, `driver/i2s_std.h`, liba52 for AC-3)
