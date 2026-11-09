#!/usr/bin/env python3
"""Prove the double-sided board is connected as it will really be built.

    python3 tools/kpy.py tools/check_board.py hardware/surround.kicad_pcb

KiCad assumes every through hole is plated, so its DRC joins the two faces at
every pad whatever the pad's layers say. These holes are bare: the faces meet
only where a lead is soldered on both, and only some leads can be reached from
the top (surround_board.TOP_OK). So this check rebuilds the connectivity from
the copper itself:

  * a track joins what it touches on its own face only;
  * a through-hole pad is always soldered on the bottom; it joins the top face
    only if TOP_OK says the iron can get there;
  * the ground pours are taken island by island, per face.

Every net must come out as one piece. It also refuses vias and top-face tracks
that end on a lead that cannot be soldered there, and it lists the joints that
have to be soldered on both faces.
"""
import math
import sys
from pathlib import Path
import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import surround_board as cfg

STEP = pcbnew.FromMM(0.15)


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def seg_points(t):
    a, b = t.GetStart(), t.GetEnd()
    n = max(1, int(math.hypot(b.x - a.x, b.y - a.y) / STEP))
    return [pcbnew.VECTOR2I(int(a.x + (b.x - a.x) * k / n), int(a.y + (b.y - a.y) * k / n)) for k in range(n + 1)]


def seg_dist(p, t):
    a, b = t.GetStart(), t.GetEnd()
    dx, dy = b.x - a.x, b.y - a.y
    L2 = dx * dx + dy * dy
    u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / L2))
    return math.hypot(p.x - (a.x + u * dx), p.y - (a.y + u * dy))


def analyse(board, top_ok):
    """Returns (problems, joints soldered on both faces that carry a connection)."""
    problems = []
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            problems.append("via on the board: this process has none")
    pads = [(fp.GetReference(), p) for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname()]
    zone = next((z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"), None)
    nets = sorted({p.GetNetname() for _, p in pads})
    twice = []
    for net in nets:
        d = DSU()
        npads = [(r, p) for r, p in pads if p.GetNetname() == net]
        ntracks = [t for t in tracks if t.GetNetname() == net]
        both = set()
        for r, p in npads:
            key = (r, p.GetNumber(), p.GetPosition().x, p.GetPosition().y)
            d.find(("B", key))
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and top_ok(r):
                both.add(key)
        # tracks against pads and against each other, face by face
        for i, t in enumerate(ntracks):
            face = "F" if t.GetLayer() == pcbnew.F_Cu else "B"
            node = ("T", i)
            d.find(node)
            pts = seg_points(t)
            for r, p in npads:
                if not p.IsOnLayer(t.GetLayer()):
                    continue
                if any(p.HitTest(q) for q in pts):
                    key = (r, p.GetNumber(), p.GetPosition().x, p.GetPosition().y)
                    if face == "B":
                        d.union(node, ("B", key))
                    elif key in both:
                        d.union(node, ("F", key))
                    elif p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd()):
                        problems.append(f"{net}: a top-face track ends on {r}.{p.GetNumber()}, "
                                        f"which cannot be soldered from the top")
            for j in range(i):
                u = ntracks[j]
                if u.GetLayer() != t.GetLayer():
                    continue
                lim = (t.GetWidth() + u.GetWidth()) / 2 * 0.9
                if (seg_dist(t.GetStart(), u) < lim or seg_dist(t.GetEnd(), u) < lim
                        or seg_dist(u.GetStart(), t) < lim or seg_dist(u.GetEnd(), t) < lim):
                    d.union(node, ("T", j))
        # the pours, island by island
        if net == "GND" and zone is not None:
            for face, layer in (("B", pcbnew.B_Cu), ("F", pcbnew.F_Cu)):
                fill = zone.GetFilledPolysList(layer)
                for r, p in npads:
                    if not p.IsOnLayer(layer):
                        continue
                    key = (r, p.GetNumber(), p.GetPosition().x, p.GetPosition().y)
                    if face == "F" and key not in both:
                        continue
                    for k in range(fill.OutlineCount()):
                        if fill.Outline(k).PointInside(p.GetPosition()):
                            d.union((face, key), ("Z", face, k))
                            break
        # a lead soldered on both faces joins them
        used = [key for key in both if ("F", key) in d.p]
        for key in used:
            d.union(("F", key), ("B", key))
        groups = {}
        for r, p in npads:
            key = (r, p.GetNumber(), p.GetPosition().x, p.GetPosition().y)
            groups.setdefault(d.find(("B", key)), []).append(f"{r}.{p.GetNumber()}")
        if len(groups) > 1:
            parts = sorted(groups.values(), key=len, reverse=True)
            problems.append(f"{net}: in {len(parts)} pieces; cut off: " + " | ".join(", ".join(sorted(set(g))) for g in parts[1:]))
        # which double joints matter: removing the top joint would split the net
        for key in sorted(used):
            twice.append((key[0], key[1], net))
    return problems, twice


def main(path):
    board = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    problems, twice = analyse(board, cfg.TOP_OK)
    for p in problems:
        print("FAIL", p)
    top = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.F_Cu]
    print(f"{len(top)} top-face track segments; {len(twice)} leads soldered on both faces:")
    by = {}
    for ref, num, net in twice:
        by.setdefault(net, []).append(f"{ref}.{num}")
    for net in sorted(by):
        print(f"  {net}: " + ", ".join(sorted(set(by[net]))))
    if problems:
        return 1
    print("OK every net is one piece, using only joints that can be made")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
