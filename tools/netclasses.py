#!/usr/bin/env python3
"""Stamp the netclasses into hardware/surround.kicad_pro.

    python3 tools/netclasses.py

Track widths are chosen for the process, not copied from a default. Copper is
isolation-milled with an 0.8 mm ball mill at 0.08 mm deep, which cuts a 0.44 mm
channel at the copper top (the `cnc-fine` profile: clearance 0.50, track 0.50).

  ESP     0.9 mm   every net with a pad on the ESP32, including both clocks: the
                   same width as the module's pads. With the pour beside it at
                   0.50 mm and the plane on the far face this is a 71 ohm line (tools/impedance.py), which
                   is what the 43R2 series resistors are sized for.
  I2S     0.5 mm   the short links on the far side of the series resistors.
  ANALOG  0.5 mm   the DAC outputs. Impedance is irrelevant at audio, but these
                   share the I2S width so the pour gap stays uniform.
  POWER   1.0 mm   37 mV of drop at 0.5 A over 150 mm, and the board draws less
                   than that with Wi-Fi off. Narrower than the old 1.5 mm because
                   every track is a slot through the single-layer ground pour.
  Default 0.5 mm   everything slow.
"""
import json
from pathlib import Path

PRO = Path(__file__).resolve().parents[1] / "hardware/surround.kicad_pro"

ESP = ["DIR_BCK", "DIR_LRCK", "Net-(U1-IO35)",
       "Net-(U1-IO2)", "Net-(U1-IO13)", "XSMT", "POT", "EN", "BOOT", "USER", "LED",
       "TXD0", "RXD0", "+3V3"]
I2S = ["Net-(A2-BCKO)", "Net-(A2-LRCKO)", "Net-(A2-DOUT)", "Net-(A3-DIN)", "Net-(A4-DIN)"]
ANALOG = ["Net-(A3-OUTL)", "Net-(A3-OUTR)", "Net-(A4-OUTL)", "Net-(A4-OUTR)",
          "Net-(J5-PadT)", "Net-(J5-PadR)", "Net-(J6-PadT)", "Net-(J6-PadR)"]
POWER = ["+9V", "+5V", "+5V_DAC1", "+5V_DAC2", "+5V_DIR", "Net-(D2-A)"]
CLEARANCE = 0.50
WIDTH = {"Default": 0.5, "ESP": 0.9, "I2S": 0.5, "ANALOG": 0.5, "POWER": 1.0}
COLOR = {"ESP": "rgb(120, 160, 255)", "I2S": "rgb(255, 80, 80)", "ANALOG": "rgb(80, 200, 120)", "POWER": "rgb(255, 200, 0)"}


def main():
    d = json.loads(PRO.read_text(encoding="utf-8"))
    ns = d["net_settings"]
    base = next(c for c in ns["classes"] if c["name"] == "Default")
    classes = []
    for name, w in WIDTH.items():
        c = dict(base)
        c.update(name=name, track_width=w, clearance=CLEARANCE,
                 via_diameter=1.6, via_drill=0.8,
                 priority=-1 if name == "Default" else 0,
                 pcb_color=COLOR.get(name, "rgba(0, 0, 0, 0.000)"))
        classes.append(c)
    ns["classes"] = classes
    ns["netclass_patterns"] = ([{"netclass": "ESP", "pattern": n} for n in ESP]
                               + [{"netclass": "I2S", "pattern": n} for n in I2S]
                               + [{"netclass": "ANALOG", "pattern": n} for n in ANALOG]
                               + [{"netclass": "POWER", "pattern": n} for n in POWER])
    r = d["board"]["design_settings"]["rules"]
    r.update(min_track_width=0.5, min_clearance=CLEARANCE, min_through_hole_diameter=0.8,
             min_via_diameter=1.6, min_via_annular_width=0.3)
    PRO.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print("netclasses: " + ", ".join(f"{n} {w} mm" for n, w in WIDTH.items())
          + f"; {len(ns['netclass_patterns'])} net assignments")


if __name__ == "__main__":
    main()
