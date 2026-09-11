#!/usr/bin/env python3
"""Reconnect the ground pour with wire links, and prove the result is whole.

    python3 tools/kpy.py tools/gnd_stitch.py <board.kicad_pcb> [--write out.kicad_pcb]

WHY THIS IS NEEDED, AND WHY A WIRE IS THE RIGHT ANSWER HERE.

On a two-layer board the ground pour is a plane and a signal trace passes under
it. On a single-sided board the pour shares the layer with every trace, so each
trace is a SLOT cut through the ground, and a trace that reaches from one edge
of a region to the other severs it. The pour then fills as several islands that
are electrically separate, and the return current for anything sitting on a
stranded island has to find its way around -- or cannot.

This is not cosmetic. Ott measured the voltage between two points an inch apart
on a ground plane under a clock trace: 15 mV with no slot, 75 mV with a 1.5 inch
slot, a factor of five. The same measurement with fifteen drilled holes across
that inch showed no increase at all, which is why a through-hole pin field costs
nothing and a continuous cut costs a great deal.

The fix on a single-sided board is a wire soldered across the cut, and ground is
the one net where a wire is not a compromise: it carries no signal of its own,
its inductance is in parallel with the surviving copper rather than in series
with a signal, and the alternative is a genuinely open return path.

This tool fills the pour, walks the filled polygons to find the islands, groups
the GND pads by which island they land in, and joins the islands with a minimum
spanning tree over pad-to-pad distance, writing each edge as an F.Cu track --
a wire link between two existing through-hole pads, so no extra drilling.
"""
import importlib.util
import math
import sys
from pathlib import Path
import pcbnew

_spec = importlib.util.spec_from_file_location(
    "finish_route", Path(__file__).resolve().parent / "finish_route.py")
_fr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fr)


def fill(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def islands(board, net):
    """[SHAPE_POLY_SET outlines] of the filled GND copper, one per island."""
    out = []
    for z in board.Zones():
        if z.GetNetname() != net:
            continue
        poly = z.GetFilledPolysList(pcbnew.B_Cu)
        for i in range(poly.OutlineCount()):
            out.append(poly.Outline(i))
    return out


def pad_island(board, net, outlines):
    """{island index: [(pad, position)]} for every pad on `net`."""
    groups = {}
    loose = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != net:
                continue
            pos = p.GetPosition()
            for i, o in enumerate(outlines):
                if o.PointInside(pcbnew.VECTOR2I(pos.x, pos.y)):
                    groups.setdefault(i, []).append((p, pos))
                    break
            else:
                loose.append((p, pos))
    return groups, loose


def label(p):
    return f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}"


def main():
    path = sys.argv[1]
    out = None
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
    b = pcbnew.LoadBoard(path)
    fill(b)
    net = "GND"
    outlines = islands(b, net)
    groups, loose = pad_island(b, net, outlines)
    print(f"GND pour fills as {len(outlines)} island(s); "
          f"{sum(len(v) for v in groups.values())} GND pads land on {len(groups)} of them")
    for i, pads in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        area = abs(outlines[i].Area()) / 1e12
        print(f"  island {i}: {area:7.1f} mm2  {len(pads):2d} pad(s)  "
              + " ".join(label(p) for p, _ in pads[:8]) + (" ..." if len(pads) > 8 else ""))
    if loose:
        print(f"  {len(loose)} GND pad(s) on NO island: " + " ".join(label(p) for p, _ in loose))

    if len(groups) <= 1 and not loose:
        print("\nok  the ground pour is already one piece; no links needed")
        return 0

    # minimum spanning tree over islands, weighted by closest GND pad pair
    keys = sorted(groups)
    best = {}
    for a in range(len(keys)):
        for c in range(a + 1, len(keys)):
            pa, pc, bd = None, None, 1e18
            for p1, q1 in groups[keys[a]]:
                for p2, q2 in groups[keys[c]]:
                    # Never wire two pads of the SAME part together: the nearest
                    # pair is often two pins of one connector, and a wire between
                    # them has to run along a 2.54 mm pad column where nothing
                    # can legally go. Going out to a different part is longer and
                    # is the only route that actually clears.
                    if (p1.GetParentFootprint().GetReference()
                            == p2.GetParentFootprint().GetReference()):
                        continue
                    d = math.hypot(q1.x - q2.x, q1.y - q2.y)
                    if d < bd:
                        pa, pc, bd = (p1, q1), (p2, q2), d
            if pa is None:
                continue
            best[(a, c)] = (bd, pa, pc)
    best = {k: v for k, v in best.items() if v[1] is not None}
    seen, edges = {0}, []
    while len(seen) < len(keys):
        cand = min(((v[0], k) for k, v in best.items()
                    if (k[0] in seen) != (k[1] in seen)), default=None)
        if cand is None:
            break
        _, k = cand
        edges.append(best[k])
        seen |= {k[0], k[1]}

    total = 0.0
    print(f"\n{len(edges)} ground link(s) needed to make the pour one piece:")
    netcode = next(p.GetNetCode() for fp in b.GetFootprints() for p in fp.Pads()
                   if p.GetNetname() == net)
    # Each link is routed, not drawn as a straight line between the two pads: a
    # wire soldered on the component side still has to clear every pad and every
    # other link it passes, and a naive straight line crosses several.
    ras = _fr.Raster(b, 0.2)
    failed = 0
    for d, (p1, q1), (p2, q2) in edges:
        # A little over the 0.85 mm rule so the grid's own rounding cannot land a
        # wire inside it; much more than this and the crowded pads stop escaping.
        blocked, _t = _fr.obstacles(b, ras, net, 1.0, 0.85, layer="F.Cu")
        s0 = ras.cell(pcbnew.ToMM(q1.x), pcbnew.ToMM(q1.y))
        g0 = ras.cell(pcbnew.ToMM(q2.x), pcbnew.ToMM(q2.y))
        # Unblock the endpoint cell only. Clearing a wider disc lets the search
        # start out along a 2.54 mm pad column, where no wire can legally run,
        # and the violation only shows up in DRC afterwards.
        for rr, cc in (s0, g0):
            blocked[rr, cc] = False
        path = _fr.astar(blocked, [s0], [g0])
        if path is None:
            print(f"  {label(p1):>9s} -> {label(p2):<9s}   NO PATH on F.Cu")
            failed += 1
            continue
        pts = [ras.mm(r, c) for r, c in _fr.simplify(path)]
        pts[0] = (pcbnew.ToMM(q1.x), pcbnew.ToMM(q1.y))
        pts[-1] = (pcbnew.ToMM(q2.x), pcbnew.ToMM(q2.y))
        mm = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                 for i in range(len(pts) - 1))
        total += mm
        print(f"  {label(p1):>9s} -> {label(p2):<9s} {mm:6.1f} mm, {len(pts) - 1} segment(s)")
        if out:
            for i in range(len(pts) - 1):
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(pts[i][0]), pcbnew.FromMM(pts[i][1])))
                t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(pts[i + 1][0]), pcbnew.FromMM(pts[i + 1][1])))
                t.SetWidth(pcbnew.FromMM(1.0))
                t.SetLayer(pcbnew.F_Cu)
                t.SetNetCode(netcode)
                b.Add(t)
    print(f"  total {total:.1f} mm of wire" + (f", {failed} could not be routed" if failed else ""))

    if out:
        fill(b)
        pcbnew.SaveBoard(out, b)
        left = len(islands(b, net))
        print(f"\nwrote {out}; pour now fills as {left} island(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
