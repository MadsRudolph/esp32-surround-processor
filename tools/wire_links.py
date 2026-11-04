#!/usr/bin/env python3
"""Report every wire link the routed board needs, and refuse the ones that
must not be wires.

    python3 tools/kpy.py tools/wire_links.py hardware/surround.kicad_pcb

A link is a run of F.Cu copper: on this single-sided board that copper is not
manufactured, it is a wire the assembler solders between two through-hole pads
on the component side. This prints one line per link with its net, endpoints
and length, and exits 1 if any link lands on a net that is not allowed to be a
wire -- the I2S clocks and data, and the analog outputs.
"""
import sys
import math
import pcbnew

BANNED_PREFIX = ("DIR_BCK", "DIR_LRCK")
BANNED_EXACT = {"Net-(A2-BCKO)", "Net-(A2-LRCKO)", "Net-(A2-DOUT)",
                "Net-(U1-IO34)", "Net-(U1-IO19)", "Net-(U1-IO23)",
                "Net-(A3-DIN)", "Net-(A4-DIN)",
                "Net-(A3-OUTL)", "Net-(A3-OUTR)", "Net-(A4-OUTL)", "Net-(A4-OUTR)",
                "Net-(J5-PadT)", "Net-(J5-PadR)", "Net-(J6-PadT)", "Net-(J6-PadR)"}


def banned(net):
    return net in BANNED_EXACT or any(net.startswith(p) for p in BANNED_PREFIX)


def main(path):
    b = pcbnew.LoadBoard(path)
    top = [t for t in b.GetTracks()
           if t.GetClass() == "PCB_TRACK" and t.GetLayerName() == "F.Cu"]
    vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
    if not top:
        print("no F.Cu copper: the board needs no wire links")
        return 0
    # group top segments into runs: union-find on shared endpoints, per net
    pts = lambda t: ((t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y))
    parent = {}
    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a, c):
        ra, rc = find(a), find(c)
        if ra != rc:
            parent[ra] = rc
    for t in top:
        a, c = pts(t)
        union(a, c)
    runs = {}
    for t in top:
        runs.setdefault((t.GetNetname(), find(pts(t)[0])), []).append(t)

    pads = [(p, p.GetPosition()) for fp in b.GetFootprints() for p in fp.Pads()]
    def nearest_pad(pt, net):
        best, bd = None, 1e18
        for p, pp in pads:
            if p.GetNetname() != net:
                continue
            d = math.hypot(pp.x - pt[0], pp.y - pt[1])
            if d < bd:
                best, bd = p, d
        return (f"{best.GetParentFootprint().GetReference()}.{best.GetNumber()}"
                if best else "?"), pcbnew.ToMM(bd)

    print(f"{len(runs)} wire link(s), {len(vias)} drilled via(s)\n")
    bad = []
    for (net, _), segs in sorted(runs.items()):
        ends = {}
        for t in segs:
            for e in pts(t):
                ends[e] = ends.get(e, 0) + 1
        free = [e for e, n in ends.items() if n == 1] or list(ends)
        length = sum(pcbnew.ToMM(t.GetLength()) for t in segs)
        a, da = nearest_pad(free[0], net)
        c, dc = nearest_pad(free[-1], net)
        flag = "  <-- NOT ALLOWED ON A WIRE" if banned(net) else ""
        if banned(net):
            bad.append(net)
        print(f"  {net:24s} {a:>8s} -> {c:<8s} {length:6.1f} mm{flag}")
        if max(da, dc) > 0.6:
            print(f"      warning: an end sits {max(da, dc):.2f} mm from the nearest {net} pad")
    if bad:
        print(f"\nFAIL {len(bad)} link(s) on nets that must stay on milled copper: {sorted(set(bad))}")
        return 1
    print("\nok  every link is on a DC rail or a static/slow control line")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
