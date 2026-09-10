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
| `hardware/surround.kicad_pro` / `.kicad_sch` | KiCad 10 project and schematic of the carrier board. |
| `lib/Surround.kicad_sym` | Project symbols for the three modules (ESP32-DevKitC-38, DIR9001 module, GY-PCM5102). Generated. |
| `tools/make_symbols.py` | Generates `lib/Surround.kicad_sym`. |
| `tools/surround_layout.py` | Generates `hardware/surround.kicad_sch`. The schematic is code; edit the script, not the file. |

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

## Board concept

A single-sided carrier PCB with pin sockets for the three breakout modules,
plus the passives that the modules do not carry:

- 5 V barrel jack, 1.1 A PTC, 470 uF bulk, and a ferrite + 100 uF branch per module rail
- 33 R series resistors at the driver end of every clock and data line
- 10 k pull-down on XSMT so both DACs are muted through boot
- RCA outputs for the fronts, impedance-balanced TRS (100 R tip / 100 R ring) for the surrounds
- rotary encoder with push button, status LED, 4-pin header for an SSD1306 I2C OLED

Module straps (set on the modules, documented on the schematic):
DIR9001 FMT1 = FMT0 = H, CKSEL = L, XTI = GND, PSCK = LL.
PCM5102A SCK = GND, FMT = L, FLT = L, DEMP = L, XSMT bridge removed and wired to the carrier.

## Status

- [x] Design review
- [x] Schematic (ERC clean, netlist checked against the review)
- [ ] Footprints and PCB (single-sided, CNC-milled; see the `kicad-laser-pcb` skill)
- [ ] Firmware (ESP-IDF v5.3, `driver/i2s_std.h`, liba52 for AC-3)
