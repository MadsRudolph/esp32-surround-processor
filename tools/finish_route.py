#!/usr/bin/env python3
"""Finish the links FreeRouting left open, on B.Cu, deterministically.

    python3 tools/kpy.py tools/finish_route.py <board.kicad_pcb> [--write out.kicad_pcb]
                                               [--grid 0.2] [--width 1.0] [--clearance 0.85]

FreeRouting gets 44-46 of this board's 48 nets and then stops, at any pass count
and under either update strategy -- the remainder is geometry it will not find,
not effort it has not spent. Those last links have to be milled copper (they are
I2S data, and a wire link is not allowed to carry those), so somebody has to draw
them. This does it with A* on a grid instead of by hand.

The model is deliberately blunt and conservative:

  * every pad and track NOT on the net being routed is an obstacle, rasterised
    at its true extent and then dilated by (track/2 + clearance), so any cell the
    search may stand on is already legal for a track centre;
  * the board edge is dilated inward by the same amount plus the edge clearance;
  * cells belonging to the target net are free, so a path may join existing
    copper anywhere along it rather than only at the pad;
  * the search is 8-connected with a turn penalty, so it produces long straight
    runs and 45 degree corners rather than staircases.

The pour is ignored on purpose: it is refilled afterwards and simply retreats
around whatever is drawn. What it must not do is fragment, which is
tools/gnd_stitch.py's job, run after this.
"""
import heapq
import math
import sys
import numpy as np
import pcbnew

GRID = 0.2
WIDTH = 0.8
CLEARANCE = 0.85
EDGE_CLEAR = 0.5


def board_box(b):
    bb = b.GetBoardEdgesBoundingBox()
    return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
            pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))


def dilate(mask, r):
    """Square-structuring-element dilation by r cells, via prefix sums."""
    if r <= 0:
        return mask
    p = np.zeros((mask.shape[0] + 1, mask.shape[1] + 1), dtype=np.int32)
    p[1:, 1:] = np.cumsum(np.cumsum(mask.astype(np.int32), 0), 1)
    h, w = mask.shape
    ys = np.arange(h)[:, None]
    xs = np.arange(w)[None, :]
    y0 = np.clip(ys - r, 0, h); y1 = np.clip(ys + r + 1, 0, h)
    x0 = np.clip(xs - r, 0, w); x1 = np.clip(xs + r + 1, 0, w)
    tot = p[y1, x1] - p[y0, x1] - p[y1, x0] + p[y0, x0]
    return tot > 0


class Raster:
    def __init__(self, b, grid=GRID):
        self.b, self.grid = b, grid
        x0, y0, x1, y1 = board_box(b)
        self.ox, self.oy = x0, y0
        self.w = int(math.ceil((x1 - x0) / grid)) + 1
        self.h = int(math.ceil((y1 - y0) / grid)) + 1

    def cell(self, x, y):
        return (int(round((y - self.oy) / self.grid)), int(round((x - self.ox) / self.grid)))

    def mm(self, r, c):
        return (self.ox + c * self.grid, self.oy + r * self.grid)

    def blank(self):
        return np.zeros((self.h, self.w), dtype=bool)

    def box(self, mask, x0, y0, x1, y1):
        r0, c0 = self.cell(x0, y0)
        r1, c1 = self.cell(x1, y1)
        r0, r1 = max(0, min(r0, r1)), min(self.h - 1, max(r0, r1))
        c0, c1 = max(0, min(c0, c1)), min(self.w - 1, max(c0, c1))
        mask[r0:r1 + 1, c0:c1 + 1] = True

    def seg(self, mask, p, q, halfw):
        n = max(2, int(math.hypot(q[0] - p[0], q[1] - p[1]) / self.grid) + 1)
        for i in range(n + 1):
            t = i / n
            x = p[0] + (q[0] - p[0]) * t
            y = p[1] + (q[1] - p[1]) * t
            self.box(mask, x - halfw, y - halfw, x + halfw, y + halfw)


def obstacles(b, ras, net, width, clearance, layer="B.Cu"):
    """(blocked, ontarget) masks for routing `net` on `layer`.

    A pad is an obstacle on either layer -- it is a plated hole through the
    board -- but only tracks on the SAME layer are."""
    blocked, target = ras.blank(), ras.blank()
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pos = p.GetPosition()
            sz = p.GetSize()
            x, y = pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)
            hx, hy = pcbnew.ToMM(sz.x) / 2, pcbnew.ToMM(sz.y) / 2
            m = target if p.GetNetname() == net else blocked
            ras.box(m, x - hx, y - hy, x + hx, y + hy)
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayerName() != layer:
            continue
        s, e = t.GetStart(), t.GetEnd()
        p = (pcbnew.ToMM(s.x), pcbnew.ToMM(s.y))
        q = (pcbnew.ToMM(e.x), pcbnew.ToMM(e.y))
        hw = pcbnew.ToMM(t.GetWidth()) / 2
        m = target if t.GetNetname() == net else blocked
        ras.seg(m, p, q, hw)
    pad = int(math.ceil((width / 2 + clearance) / ras.grid))
    blocked = dilate(blocked, pad)
    # board edge
    edge = int(math.ceil((width / 2 + EDGE_CLEAR) / ras.grid))
    blocked[:edge, :] = True; blocked[-edge:, :] = True
    blocked[:, :edge] = True; blocked[:, -edge:] = True
    # NOTE: do NOT unblock cells just because the net's own copper covers them.
    # Own copper is never added to `blocked` in the first place, so the only
    # cells that exception would free are ones blocked by ANOTHER net -- e.g. a
    # GND pad sitting 2.54 mm from a signal pad. Routing through those produced
    # wires that looked connected and failed DRC on clearance to the neighbour.
    return blocked, target


DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def astar(blocked, starts, goals):
    h, w = blocked.shape
    goal = np.zeros_like(blocked)
    for r, c in goals:
        if 0 <= r < h and 0 <= c < w:
            goal[r, c] = True
    if not goal.any():
        return None
    gr, gc = np.argwhere(goal).mean(0)
    best = {}
    pq = []
    for r, c in starts:
        if 0 <= r < h and 0 <= c < w and not blocked[r, c]:
            best[(r, c, -1)] = 0.0
            heapq.heappush(pq, (math.hypot(r - gr, c - gc), 0.0, r, c, -1, None))
    seen = {}
    while pq:
        f, g, r, c, d, par = heapq.heappop(pq)
        if (r, c, d) in seen:
            continue
        seen[(r, c, d)] = par
        if goal[r, c]:
            path = [(r, c)]
            k = (r, c, d)
            while seen[k] is not None:
                k = seen[k]
                path.append((k[0], k[1]))
            return path[::-1]
        for i, (dr, dc) in enumerate(DIRS):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < h and 0 <= nc < w) or blocked[nr, nc]:
                continue
            step = 1.0 if i < 4 else 1.414
            turn = 0.0 if (d == -1 or d == i) else 0.8
            ng = g + step + turn
            k = (nr, nc, i)
            if ng < best.get(k, 1e18):
                best[k] = ng
                heapq.heappush(pq, (ng + math.hypot(nr - gr, nc - gc), ng, nr, nc, i, (r, c, d)))
    return None


def simplify(path):
    """Collapse a cell path to corner points."""
    if len(path) < 2:
        return path
    out = [path[0]]
    for i in range(1, len(path) - 1):
        a, b, c = path[i - 1], path[i], path[i + 1]
        if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
            out.append(b)
    out.append(path[-1])
    return out


def open_links(b):
    """[(net, padA, padB)] for every net whose pads are not all one piece."""
    conn = b.GetConnectivity()
    conn.RecalculateRatsnest()
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pass
    # use KiCad's own unconnected list via the ratsnest
    for i in range(b.GetNetCount()):
        ni = b.FindNet(i)
        if ni is None:
            continue
    return out


def main():
    path = sys.argv[1]
    out = None
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
    grid = float(sys.argv[sys.argv.index("--grid") + 1]) if "--grid" in sys.argv else GRID
    width = float(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else WIDTH
    clear = float(sys.argv[sys.argv.index("--clearance") + 1]) if "--clearance" in sys.argv else CLEARANCE

    only = None
    if "--nets" in sys.argv:
        only = sys.argv[sys.argv.index("--nets") + 1].split(",")

    b = pcbnew.LoadBoard(path)
    if only:
        # Route these nets first, on a board with nothing else on it. Order is
        # the whole game on one layer: routed last, a net has to thread whatever
        # everything else already built, and on this board the four I2S links
        # left over by FreeRouting were not merely hard but walled in -- a flood
        # fill from one pad reached 81 cells. Fast nets go down first.
        todo = []
        for ni in [b.FindNet(i) for i in range(b.GetNetCount())]:
            if ni is None or ni.GetNetname() not in only:
                continue
            ps = [p for fp in b.GetFootprints() for p in fp.Pads()
                  if p.GetNetname() == ni.GetNetname()]
            ps.sort(key=lambda q: (q.GetPosition().x, q.GetPosition().y))
            for i in range(len(ps) - 1):
                todo.append((ni.GetNetname(),
                             f"{ps[i].GetParentFootprint().GetReference()}.{ps[i].GetNumber()}",
                             f"{ps[i+1].GetParentFootprint().GetReference()}.{ps[i+1].GetNumber()}"))
        ras = Raster(b, grid)
        print(f"grid {grid} mm  {ras.w} x {ras.h} cells   track {width} mm  clearance {clear} mm")
        print(f"pre-routing {len(todo)} link(s) over {len(only)} net(s)")
        _route(b, ras, todo, pads_of(b), width, clear)
        if out:
            pcbnew.ZONE_FILLER(b).Fill(b.Zones())
            pcbnew.SaveBoard(out, b)
            print(f"wrote {out}")
        return 0
    # KiCad's own view of what is still open
    conn = b.GetConnectivity()
    conn.RecalculateRatsnest()
    todo = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pass
    import json as _json
    import subprocess
    rep = "/tmp/_finish_drc.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json",
                    "-o", rep, path], capture_output=True)
    d = _json.load(open(rep))
    pads = pads_of(b)
    import re
    for u in d["unconnected_items"]:
        descs = [i["description"] for i in u["items"]]
        if any("Zone" in x for x in descs):
            continue
        refs = []
        for x in descs:
            m = re.search(r"pad (\S+) \[([^\]]*)\] of (\S+)", x)
            refs.append((f"{m.group(3)}.{m.group(1)}", m.group(2)) if m else None)
        if all(refs):
            todo.append((refs[0][1], refs[0][0], refs[1][0]))
    if not todo:
        print("nothing open: every net is already in one piece")
        return 0

    ras = Raster(b, grid)
    print(f"grid {grid} mm  {ras.w} x {ras.h} cells   track {width} mm  clearance {clear} mm")
    done = _route(b, ras, todo, pads, width, clear)
    if out:
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        pcbnew.SaveBoard(out, b)
        print(f"\nwrote {out}: {done}/{len(todo)} link(s) routed on B.Cu")
    return 0 if done == len(todo) else 1


def pads_of(b):
    return {f"{fp.GetReference()}.{p.GetNumber()}": p
            for fp in b.GetFootprints() for p in fp.Pads()}


def _route(b, ras, todo, pads, width, clear):
    done = 0
    for net, a, dest in todo:
        blocked, target = obstacles(b, ras, net, width, clear)
        pa, pc = pads[a], pads[dest]

        def cell_of(p):
            pos = p.GetPosition()
            return ras.cell(pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y))

        s0, g0 = cell_of(pa), cell_of(pc)
        # Goals are the DESTINATION pad only. Seeding them with "anywhere on the
        # net's copper" looks like a shortcut and is a trap: the source pad is on
        # that copper too, so the search reaches a goal without moving and the
        # link is reported closed while nothing was drawn.
        starts, goals = [s0], [g0]
        # A pad in a 2.54 mm row sits inside its neighbours' dilated keep-out, so
        # both endpoints have to be unblocked or the search cannot even start.
        # Two cells only, and DRC afterwards is what actually certifies the result.
        for rr, cc2 in (s0, g0):
            blocked[max(0, rr - 2):rr + 3, max(0, cc2 - 2):cc2 + 3] = False
        p = astar(blocked, starts, goals)
        if p is None:
            print(f"  FAIL {net:22s} {a} -> {dest}: no path at {clear} mm clearance")
            continue
        pts = [ras.mm(r, c) for r, c in simplify(p)]
        # snap the ends onto the real pad centres: a grid cell is up to half a
        # grid step away, which is enough to leave the track not touching the pad
        pts[0] = (pcbnew.ToMM(pa.GetPosition().x), pcbnew.ToMM(pa.GetPosition().y))
        pts[-1] = (pcbnew.ToMM(pc.GetPosition().x), pcbnew.ToMM(pc.GetPosition().y))
        length = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                     for i in range(len(pts) - 1))
        print(f"  ok   {net:22s} {a} -> {dest}: {len(pts) - 1} segment(s), {length:.1f} mm")
        nc = pa.GetNetCode()
        if len(pts) < 2:
            print(f"  FAIL {net}: degenerate path, nothing written")
            continue
        for i in range(len(pts) - 1):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(pts[i][0]), pcbnew.FromMM(pts[i][1])))
            t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(pts[i + 1][0]), pcbnew.FromMM(pts[i + 1][1])))
            t.SetWidth(pcbnew.FromMM(width))
            t.SetLayer(pcbnew.B_Cu)
            t.SetNetCode(nc)
            b.Add(t)
        done += 1
    return done


if __name__ == "__main__":
    sys.exit(main())
