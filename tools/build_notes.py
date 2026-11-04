#!/usr/bin/env python3
"""Generate hardware/BUILD-NOTES.md from the routed board.

    python3 tools/kpy.py tools/build_notes.py hardware/surround.kicad_pcb

Everything in it is read off the board, so it cannot drift from the artwork:
the wire links the assembler has to solder, the module straps, and whatever is
still open.
"""
import json
import re
import subprocess
import sys
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "hardware/BUILD-NOTES.md"


def links(b):
    top = [t for t in b.GetTracks()
           if t.GetClass() == "PCB_TRACK" and t.GetLayerName() == "F.Cu"]
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, c):
        ra, rc = find(a), find(c)
        if ra != rc:
            parent[ra] = rc

    pts = lambda t: ((t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y))
    for t in top:
        union(*pts(t))
    runs = {}
    for t in top:
        runs.setdefault((t.GetNetname(), find(pts(t)[0])), []).append(t)
    pads = [(p, p.GetPosition()) for fp in b.GetFootprints() for p in fp.Pads()]
    out = []
    for (net, _), segs in runs.items():
        ends = {}
        for t in segs:
            for e in pts(t):
                ends[e] = ends.get(e, 0) + 1
        free = [e for e, n in ends.items() if n == 1] or list(ends)
        def near(pt):
            best, bd = None, 1e18
            for p, pp in pads:
                if p.GetNetname() != net:
                    continue
                d = (pp.x - pt[0]) ** 2 + (pp.y - pt[1]) ** 2
                if d < bd:
                    best, bd = p, d
            return f"{best.GetParentFootprint().GetReference()}.{best.GetNumber()}" if best else "?"
        length = sum(pcbnew.ToMM(t.GetLength()) for t in segs)
        out.append((net, near(free[0]), near(free[-1]), length))
    return sorted(out, key=lambda r: (r[0], -r[3]))


def main(path):
    b = pcbnew.LoadBoard(path)
    rep = "/tmp/_bn_drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json",
                    "-o", rep, path], capture_output=True)
    d = json.load(open(rep))
    open_items = [u for u in d["unconnected_items"]]

    L = links(b)
    tot = sum(r[3] for r in L)
    lines = [
        "# Build notes",
        "",
        "Generated from `hardware/surround.kicad_pcb` by `tools/build_notes.py`.",
        "Do not edit by hand; re-run the tool after any change to the board.",
        "",
        "## Before cutting",
        "",
        "Three things are assumed, not measured. Check each against the part in hand:",
        "",
        "- **DAC modules (AYWHP PCM5102).** Sellers quote sizes from 29 x 16 to 32 x 24 mm.",
        "  The board reserves 32 x 24 mm with the 6-pin header 3 mm inside one end. Measure",
        "  the module, its pin order, and where the jack and the XSMT pad are.",
        "- **DIR9001 module.** The 1x10 pinout of A2 is unverified: VCC, GND, SCKO, BCKO,",
        "  LRCKO, DOUT, ERROR, AUDIO, FMT0, FMT1. Its body is assumed to overhang the east edge.",
        "- **WROOM-32 castellations on the ball mill.** Never cut before. Cut",
        "  `hardware/coupon` first and meter every neighbouring pad pair.",
        "",
        "## Wire links",
        "",
        "The board is single sided: the only copper the mill cuts is on the bottom. A link",
        "is an insulated solid-core wire, 0.4 to 0.5 mm. Lap it onto the two pads on the",
        "copper side, since socket pins fill the holes. The I2S clocks and data and the DAC",
        "outputs may not be links; `tools/wire_links.py` fails the build if one appears.",
        "",
        f"{len(L)} link(s), {tot:.0f} mm of wire in total.",
        "",
        "| Net | From | To | Length |",
        "|---|---|---|---:|",
    ]
    for net, a, c, ln in L:
        lines.append(f"| `{net}` | {a} | {c} | {ln:.1f} mm |")
    lines += [
        "",
        "Neither is optional. A3.6, A4.2 and C3 sit between the two clock runs, and the",
        "A3 wire is their only DC path to the rest of the pour. TP1 to TP2 is the DIR9001's",
        "short return across the clocks; without it the return runs about 150 mm round the board.",
        "",
        "## Assembly order",
        "",
        "1. U1 first, flat on the milled side. Tack two opposite corners, then drag-solder the",
        "   castellations. Leave the centre pad unsoldered.",
        "2. Meter neighbouring pins for bridges, especially 1/2/3, 34/35 and 25/26.",
        "3. The ground links, then the low through-hole parts, the sockets, and the regulators last.",
        "4. Power only: 5.0 V at U2, and 3.2 to 3.3 V at U1 pin 2, before any module goes in.",
        "   C11 has its leads formed out to the 3.5 mm footprint.",
        "5. Leave room for the heatsink south of U3. U2 runs without one.",
        "",
        "Flashing: 3.3 V UART cable on J2 (pin 1 TXD0, pin 2 RXD0, pin 3 GND; cable RX to TXD0). Hold BOOT, tap",
        "RESET, release.",
        "",
        "## Module straps",
        "",
        "Set these on the modules before fitting them.",
        "",
        "| Module | Strap | Value |",
        "|---|---|---|",
        "| DIR9001 | FMT1, FMT0 | both HIGH via the socket: 24-bit I2S |",
        "| DIR9001 | CKSEL | LOW: always the recovered PLL clock |",
        "| DIR9001 | XTI | to DGND, no crystal fitted |",
        "| DIR9001 | PSCK1, PSCK0 | both LOW: SCKO at 128 fs, unused |",
        "| PCM5102 (both) | SCK | to GND via the socket: 3-wire BCK-PLL mode |",
        "| PCM5102 (both) | FMT | LOW: I2S |",
        "| PCM5102 (both) | FLT | LOW: normal latency filter |",
        "| PCM5102 (both) | DEMP | LOW: de-emphasis off |",
        "| PCM5102 (both) | XSMT | bridge removed, flying lead to pad 7 of its footprint |",
        "| PCM5102 (both) | L, R, AGND | flying leads to pads 8, 9, 10 |",
        "",
        "## Parts",
        "",
        "| Part | Qty | Source |",
        "|---|---:|---|",
        "| ESP32-WROOM-32 | 1 | shop: EKB basement stock, ask for it |",
        "| DIR9001 module with TOSLINK | 1 | buy |",
        "| PCM5102 module (AYWHP) | 2 | buy: bought, 3 in hand with one spare |",
        "| RCA panel jack, TRS panel jack | 2 + 2 | buy: order list |",
        "| 9 V 1 A adapter, centre positive | 1 | buy: order list |",
        "| 10K potentiometer | 1 | shop |",
        "| LM7805, LM317T, TO-220 heatsink | 1 + 1 + 1 | shop |",
        "| 1N5817, 1N4003 | 1 + 1 | shop |",
        "| 43R2 (R1-R5) | 5 | shop |",
        "| 100R (R6-R9) | 4 | shop, 1 at home |",
        "| 10k (R11, R14, R15) | 3 | home |",
        "| 10R (R17-R19) | 3 | home 2, shop 1 |",
        "| 1k (R16, R20) | 2 | home 1, shop 1 |",
        "| 332R, 243R, 392R | 1 each | shop |",
        "| 470 uF (C1) | 1 | home: 16 V, fine on 3V3 |",
        "| 100 uF (C2-C4) | 3 | shop |",
        "| 10 uF 50 V (C5, C8) | 2 | home |",
        "| 100 nF (C6, C7, C9) | 3 | shop |",
        "| 1 uF 50 V (C11) | 1 | shop |",
        "| 3 mm LED | 2 | shop |",
        "| 6 mm pushbutton | 3 | shop |",
        "| 2-pole, 3-pole screw terminal | 3 + 2 | shop |",
        "| Female header 1x10, 1x6 | 1 + 2 | shop |",
        "| Male header 1x3 | 2 | shop |",
        "| TP1, TP2 | 2 | bare pads, nothing to fit |",
        "",
        "## Panel parts",
        "",
        "J1 takes the 9 V adapter (centre positive; pad 1 is +). J3 and J4 are the RCA fronts,",
        "J5 and J6 the TRS surrounds. J7 is the volume pot: 3V3, wiper, GND.",
        "",
    ]
    if open_items:
        lines += ["## Still open", "",
                  "These are **not finished** and must be completed in the KiCad board editor",
                  "before the board is cut:", ""]
        for u in open_items:
            lines.append("- " + " to ".join(re.sub(r"\s*@\(.*", "", i["description"])
                                            for i in u["items"]))
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(L)} links, {tot:.0f} mm, "
          f"{len(open_items)} item(s) still open")


if __name__ == "__main__":
    main(sys.argv[1])
