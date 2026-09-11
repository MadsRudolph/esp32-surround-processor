#!/usr/bin/env python3
"""Generate hardware/BUILD-NOTES.md from the routed board.

    python3 tools/kpy.py tools/build_notes.py hardware/surround.routed.kicad_pcb

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
        "Generated from `hardware/surround.routed.kicad_pcb` by `tools/build_notes.py`.",
        "Do not edit by hand; re-run the tool after any change to the board.",
        "",
        "## Wire links",
        "",
        "The board is single sided: the only copper the mill cuts is on the bottom.",
        "Every link below is a **wire soldered on the component side between two",
        "through-hole pads**. No via is drilled for any of them, because a through-hole",
        "pad already exists on both sides of the board.",
        "",
        "Only DC rails, ground, and slow control lines are allowed to be links. The I2S",
        "clock and data nets and the DAC outputs are pinned to milled copper for the",
        "whole route, because a wire standing off the board is an uncontrolled-impedance",
        "stub with a large loop area, which is the wrong thing to hang a 3 MHz clock or a",
        "line-level audio output on. `tools/wire_links.py` fails the build if one appears",
        "on a net that is not allowed to carry it.",
        "",
        "Use insulated solid core, 0.4 to 0.5 mm. Keep each wire flat against the board.",
        "",
        f"{len(L)} links, {tot:.0f} mm of wire in total.",
        "",
        "| Net | From | To | Length |",
        "|---|---|---|---:|",
    ]
    for net, a, c, ln in L:
        lines.append(f"| `{net}` | {a} | {c} | {ln:.1f} mm |")
    lines += [
        "",
        "The ground links are not optional. On a single-sided board every track is a slot",
        "cut through the ground pour, and without these wires the pour fills as nine",
        "separate islands with no return path between them.",
        "",
        "## Module straps",
        "",
        "Set these on the modules before fitting them.",
        "",
        "| Module | Strap | Value |",
        "|---|---|---|",
        "| DIR9001 | FMT1, FMT0 | both HIGH: 24-bit I2S |",
        "| DIR9001 | CKSEL | LOW: always the recovered PLL clock |",
        "| DIR9001 | XTI | to DGND, no crystal fitted |",
        "| DIR9001 | PSCK1, PSCK0 | both LOW: SCKO at 128 fs, unused |",
        "| GY-PCM5102 (both) | SCK | to GND: 3-wire BCK-PLL mode |",
        "| GY-PCM5102 (both) | FMT | LOW: I2S |",
        "| GY-PCM5102 (both) | FLT | LOW: normal latency filter |",
        "| GY-PCM5102 (both) | DEMP | LOW: de-emphasis off |",
        "| GY-PCM5102 (both) | XSMT | bridge removed, wired to the carrier |",
        "",
        "## Panel parts",
        "",
        "The audio jacks and the encoder are panel mounted and wired to the board, because",
        "every PCB-mount RCA, TRS and EC11 footprint has pad gaps under the 0.8 mm the end",
        "mill needs. J3 and J4 are the front outputs on 2-pin terminals, J5 and J6 the",
        "surrounds on 3-pin terminals, SW1 a 5-pin header for the encoder.",
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
