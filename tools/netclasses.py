#!/usr/bin/env python3
"""Stamp the netclasses into hardware/surround.kicad_pro.

    python3 tools/netclasses.py

Track widths are chosen for the process, not copied from a default:

  I2S     0.8 mm   the clock and data lines. With the pour beside them at the
                   0.85 mm mill gap this is a 92 ohm coplanar line
                   (tools/impedance.py), which is what the 56 R series
                   terminators are sized for.
  ANALOG  0.8 mm   the DAC outputs. Impedance is irrelevant at audio, but these
                   share the I2S width so the pour gap stays uniform.
  POWER   1.5 mm   25 mV of drop at 0.5 A over 150 mm, and a wider trace is a
                   smaller cut through the ground pour per unit of current.
  Default 0.8 mm   everything slow.

WHY 0.8 AND NOT 1.0. The limit this process imposes is on the copper GAP, which
is what the 0.8 mm end mill physically cuts; the track itself can be anything the
laminate will hold. Track pitch is width + clearance, so going 1.0 -> 0.8 mm
takes the pitch from 1.85 to 1.65 mm, and the corridor between the DAC header
columns and the ESP32 from one track to two. That corridor is the constraint on
this board, so the narrower track is not a cosmetic choice. 0.8 mm of milled
copper is still mechanically sound; below about 0.5 mm a trace starts lifting
when it is soldered and reworked, so that is the floor to respect, not 1.0.
"""
import json
from pathlib import Path

PRO = Path(__file__).resolve().parents[1] / "hardware/surround.kicad_pro"

I2S = ["DIR_BCK", "DIR_LRCK", "Net-(A2-BCKO)", "Net-(A2-LRCKO)", "Net-(A2-DOUT)",
       "Net-(A1-IO34)", "Net-(A1-IO19)", "Net-(A1-IO23)", "Net-(A3-DIN)", "Net-(A4-DIN)"]
ANALOG = ["Net-(A3-OUTL)", "Net-(A3-OUTR)", "Net-(A4-OUTL)", "Net-(A4-OUTR)",
          "Net-(J5-PadT)", "Net-(J5-PadR)", "Net-(J6-PadT)", "Net-(J6-PadR)"]
POWER = ["+5V", "+5V_DAC1", "+5V_DAC2", "+5V_DIR", "+3V3", "Net-(F1-Pad1)"]
WIDTH = {"Default": 0.8, "I2S": 0.8, "ANALOG": 0.8, "POWER": 1.5}
COLOR = {"I2S": "rgb(255, 80, 80)", "ANALOG": "rgb(80, 200, 120)", "POWER": "rgb(255, 200, 0)"}


def main():
    d = json.loads(PRO.read_text(encoding="utf-8"))
    ns = d["net_settings"]
    base = next(c for c in ns["classes"] if c["name"] == "Default")
    classes = []
    for name, w in WIDTH.items():
        c = dict(base)
        c.update(name=name, track_width=w, clearance=0.85,
                 via_diameter=1.6, via_drill=0.8,
                 priority=-1 if name == "Default" else 0,
                 pcb_color=COLOR.get(name, "rgba(0, 0, 0, 0.000)"))
        classes.append(c)
    ns["classes"] = classes
    ns["netclass_patterns"] = ([{"netclass": "I2S", "pattern": n} for n in I2S]
                               + [{"netclass": "ANALOG", "pattern": n} for n in ANALOG]
                               + [{"netclass": "POWER", "pattern": n} for n in POWER])
    r = d["board"]["design_settings"]["rules"]
    r.update(min_track_width=1.0, min_clearance=0.85, min_through_hole_diameter=0.8,
             min_via_diameter=1.6, min_via_annular_width=0.3)
    PRO.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print("netclasses: " + ", ".join(f"{n} {w} mm" for n, w in WIDTH.items())
          + f"; {len(ns['netclass_patterns'])} net assignments")


if __name__ == "__main__":
    main()
