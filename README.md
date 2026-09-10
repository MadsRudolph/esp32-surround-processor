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
| `tools/finalize_pcb.py` / `kpy.py` | Pour refill after routing; launcher that patches this KiCad build's pcbnew iterator bug. |

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
cd hardware
kicad-cli sch export netlist --format kicadsexpr -o surround.net surround.kicad_sch
python3 ~/.claude/skills/kicad-laser-pcb/scripts/pcb_netlist_json.py surround.net surround.json
cd ..
python3 tools/pcb_bootstrap.py 140x110          # fresh board, parts on a grid
python3 tools/apply_placement.py                # the floorplan
python3 ~/.claude/skills/kicad-place/scripts/place_score.py hardware/surround.kicad_pcb
python3 ~/.claude/skills/kicad-place/scripts/place_floor.py --pours hardware/surround.kicad_pcb
python3 ~/.claude/skills/kicad-place/scripts/place_router.py route hardware/surround.kicad_pcb \
        --out hardware/surround.routed.kicad_pcb --pour-mode plane --orders 1
python3 tools/kpy.py tools/finalize_pcb.py hardware/surround.routed.kicad_pcb
kicad-cli pcb drc --severity-all hardware/surround.routed.kicad_pcb
```

Fabrication is the DTU single-sided process: copper isolation-milled on B.Cu
with an 0.8 mm end mill (track 1.0 mm, clearance 0.85 mm), through-hole parts
on top, silkscreen by fiber laser. The 2.54 mm socket rows sit at 0.84 mm
pad-to-pad and carry documented exceptions in `surround.kicad_dru`.

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
- [x] Placement (scores 4/4, topology floor 0 bridges with the GND pour)
- [ ] Routing signed off (single-sided, B.Cu only, DRC clean)
- [ ] Production files (Gerber + Excellon for CAM, silkscreen DXF for the laser)
- [ ] Firmware (ESP-IDF v5.3, `driver/i2s_std.h`, liba52 for AC-3)
