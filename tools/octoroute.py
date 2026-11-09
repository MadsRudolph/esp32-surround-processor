#!/usr/bin/env python3
"""A single-layer octilinear grid router for the milled board.

Used by tools/surround_board.py; routes every net except the poured GND on B.Cu
and enforces this board's rules by construction:

  * every segment is horizontal, vertical or exactly 45 degrees;
  * no run turns by more than 45 degrees (A* state carries the heading);
  * clearance is measured exactly against the real copper (pads, tracks, holes),
    not against a raster, so 0.50 mm means 0.50 mm. The only relaxation is the
    0.30 mm U1_escape rule, applied inside the escape areas around the
    castellations, as the project's .kicad_dru allows.

The grid is 0.254 mm, aligned so the WROOM pad rows sit on it. A track may end
anywhere inside a pad of its own net (KiCad counts it as connected).
"""
import heapq
import math
import numpy as np

G = 0.254
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
STEP = [G * math.hypot(dx, dy) for dx, dy in DIRS]
TURN45 = 0.45            # mm of extra cost per 45 degree turn: prefer long straight runs


class Item:
    """A piece of copper or a keep-out: a pad (rotated rect/oval/circle), a track
    segment, or a hole. dist(x, y) is the distance from points to its edge (<0 inside)."""
    def __init__(self, kind, net, **kw):
        self.kind, self.net = kind, net
        self.__dict__.update(kw)
        self.escape = kw.get("escape", False)

    def bbox(self, pad=0.0):
        if self.kind == "seg":
            r = self.w / 2 + pad
            return (min(self.a[0], self.b[0]) - r, min(self.a[1], self.b[1]) - r,
                    max(self.a[0], self.b[0]) + r, max(self.a[1], self.b[1]) + r)
        r = self.r + pad
        return (self.c[0] - r, self.c[1] - r, self.c[0] + r, self.c[1] + r)

    def dist(self, X, Y):
        if self.kind == "seg":
            ax, ay = self.a; bx, by = self.b
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            if L2 == 0:
                t = 0.0
            else:
                t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0, 1)
            return np.hypot(X - (ax + t * dx), Y - (ay + t * dy)) - self.w / 2
        if self.kind == "hole":
            return np.hypot(X - self.c[0], Y - self.c[1]) - self.rad
        # pad: rounded rectangle in its own frame (oval = rr with radius min/2)
        cx, cy = self.c
        ca, sa = math.cos(self.ang), math.sin(self.ang)
        u = (X - cx) * ca + (Y - cy) * sa
        v = -(X - cx) * sa + (Y - cy) * ca
        hx, hy, rr = self.hx, self.hy, self.rr
        qx = np.abs(u) - (hx - rr)
        qy = np.abs(v) - (hy - rr)
        out = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)
        return out - rr


def pad_item(net, cx, cy, sx, sy, ang_deg, shape, ref, num):
    hx, hy = sx / 2, sy / 2
    rr = min(hx, hy) if shape in ("circle", "oval") else 0.0
    return Item("pad", net, c=(cx, cy), hx=hx, hy=hy, rr=rr, ang=math.radians(ang_deg),
                r=math.hypot(hx, hy), ref=ref, num=num)


class Router:
    def __init__(self, W, H, origin=(0.0, 0.0), edge_clear=0.5):
        self.W, self.H = W, H
        self.ox, self.oy = origin           # grid origin offset (so pad rows land on grid)
        self.nx = int((W - self.ox) / G) + 1
        self.ny = int((H - self.oy) / G) + 1
        xs = self.ox + np.arange(self.nx) * G
        ys = self.oy + np.arange(self.ny) * G
        self.X, self.Y = np.meshgrid(xs, ys, indexing="ij")
        self.items = []
        self.keepouts = []                  # (x0, y0, x1, y1): no track centre inside
        self.escape = []                    # rectangles where the 0.30 mm rule applies
        self.edge_clear = edge_clear
        self.tracks = {}                    # net -> list of (a, b, w)

    # ---------------------------------------------------------------- geometry
    def node_xy(self, i, j):
        return self.ox + i * G, self.oy + j * G

    def in_escape(self, X, Y):
        m = np.zeros(X.shape, bool)
        for x0, y0, x1, y1 in self.escape:
            m |= (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
        return m

    def free_mask(self, net, w, clr=0.5, esc_clr=0.30):
        """True where a track of width w on `net` may have its centre."""
        h = w / 2
        free = np.ones((self.nx, self.ny), bool)
        # board edge
        e = self.edge_clear + h
        free &= (self.X >= e) & (self.X <= self.W - e) & (self.Y >= e) & (self.Y <= self.H - e)
        for x0, y0, x1, y1 in self.keepouts:
            free &= ~((self.X > x0) & (self.X < x1) & (self.Y > y0) & (self.Y < y1))
        for it in self.items:
            if it.net == net and it.kind != "hole":
                continue
            need = h + (clr if it.kind != "hole" else it.clr)
            x0, y0, x1, y1 = it.bbox(need + G)
            i0 = max(0, int((x0 - self.ox) / G)); i1 = min(self.nx, int((x1 - self.ox) / G) + 2)
            j0 = max(0, int((y0 - self.oy) / G)); j1 = min(self.ny, int((y1 - self.oy) / G) + 2)
            if i0 >= i1 or j0 >= j1:
                continue
            Xs, Ys = self.X[i0:i1, j0:j1], self.Y[i0:i1, j0:j1]
            d = it.dist(Xs, Ys)
            lim = np.full(d.shape, need)
            if it.escape and self.escape:
                lim = np.where(self.in_escape(Xs, Ys), h + esc_clr, lim)
            free[i0:i1, j0:j1] &= ~(d < lim - 1e-6)
        return free

    def pad_nodes(self, it, w):
        """Grid nodes where a track of width w can end inside this pad."""
        x0, y0, x1, y1 = it.bbox(0)
        i0 = max(0, int((x0 - self.ox) / G)); i1 = min(self.nx, int((x1 - self.ox) / G) + 2)
        j0 = max(0, int((y0 - self.oy) / G)); j1 = min(self.ny, int((y1 - self.oy) / G) + 2)
        Xs, Ys = self.X[i0:i1, j0:j1], self.Y[i0:i1, j0:j1]
        d = it.dist(Xs, Ys)
        # keep the track end well inside the copper
        lim = -min(0.25, max(0.0, min(it.hx, it.hy) - 0.2))
        ii, jj = np.nonzero(d <= lim)
        if len(ii) == 0:
            ii, jj = np.nonzero(d <= 0)
        cx, cy = it.c
        nodes = [(i0 + a, j0 + b) for a, b in zip(ii, jj)]
        nodes.sort(key=lambda n: math.hypot(*np.subtract(self.node_xy(*n), (cx, cy))))
        return nodes

    # ---------------------------------------------------------------- search
    def astar(self, free, sources, targets, start_dirs=None):
        """sources: {(i,j): set(dirs) or None}; targets: set of (i,j). Returns node path."""
        tset = set(targets)
        if not tset:
            return None
        tx = np.array([t[0] for t in tset]); ty = np.array([t[1] for t in tset])
        tminx, tmaxx, tminy, tmaxy = tx.min(), tx.max(), ty.min(), ty.max()

        def hfun(i, j):
            dx = max(tminx - i, 0, i - tmaxx); dy = max(tminy - j, 0, j - tmaxy)
            return G * (max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy))

        openq, best, parent = [], {}, {}
        for (i, j), dirs in sources.items():
            for d in (dirs if dirs is not None else range(8)):
                s = (i, j, d)
                best[s] = 0.0
                parent[s] = None
                heapq.heappush(openq, (hfun(i, j), 0.0, s))
        nx, ny = self.nx, self.ny
        while openq:
            f, g, s = heapq.heappop(openq)
            if g > best.get(s, 1e18) + 1e-9:
                continue
            i, j, d = s
            if (i, j) in tset:
                path = [(i, j)]
                while parent[s] is not None:
                    s = parent[s]
                    path.append((s[0], s[1]))
                return path[::-1]
            for dd, extra in ((0, 0.0), (1, TURN45), (-1, TURN45)):
                nd = (d + dd) % 8
                di, dj = DIRS[nd]
                ni, nj = i + di, j + dj
                if not (0 <= ni < nx and 0 <= nj < ny) or not free[ni, nj]:
                    continue
                if di and dj and not (free[i + di, j] or free[i, j + dj]):
                    pass
                ng = g + STEP[nd] + extra
                ns = (ni, nj, nd)
                if ng < best.get(ns, 1e18) - 1e-9:
                    best[ns] = ng
                    parent[ns] = s
                    heapq.heappush(openq, (ng + hfun(ni, nj), ng, ns))
        return None

    # ---------------------------------------------------------------- nets
    def add_track(self, net, pts, w):
        for a, b in zip(pts, pts[1:]):
            self.items.append(Item("seg", net, a=a, b=b, w=w, escape=self.seg_in_escape(a, b)))
            self.tracks.setdefault(net, []).append((a, b, w))

    def seg_in_escape(self, a, b):
        for x0, y0, x1, y1 in self.escape:
            for (x, y) in (a, b, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)):
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return True
        return False

    def remove_net(self, net):
        self.items = [it for it in self.items if not (it.kind == "seg" and it.net == net)]
        self.tracks.pop(net, None)

    def route_net(self, net, pads, w):
        """pads: list of pad Items on this net. Builds a tree; returns (ok, msg)."""
        free = self.free_mask(net, w)
        pad_nodes = [self.pad_nodes(p, w) for p in pads]
        for k, nodes in enumerate(pad_nodes):
            for n in nodes:
                free[n] = True           # own pad copper is always enterable
        # grow from the pad nearest the centroid of the others
        order = list(range(len(pads)))
        cx = np.mean([p.c[0] for p in pads]); cy = np.mean([p.c[1] for p in pads])
        order.sort(key=lambda k: math.hypot(pads[k].c[0] - cx, pads[k].c[1] - cy))
        tree_nodes = {n: None for n in pad_nodes[order[0]]}
        connected = [order[0]]
        remaining = order[1:]
        new_paths = []
        while remaining:
            # nearest remaining pad to the tree
            tx = np.array([self.node_xy(*n) for n in tree_nodes])
            remaining.sort(key=lambda k: np.min(np.hypot(tx[:, 0] - pads[k].c[0], tx[:, 1] - pads[k].c[1])))
            k = remaining.pop(0)
            path = self.astar(free, tree_nodes, set(pad_nodes[k]))
            if path is None:
                for p in new_paths:
                    pass
                self.remove_net(net)
                return False, f"{net}: no path to {pads[k].ref}.{pads[k].num}"
            pts = simplify([self.node_xy(*n) for n in path])
            # end on the pad centre when that keeps the run octilinear
            pts = snap_end(pts, pads[k].c)
            if len(new_paths) == 0 and path[0] in set(pad_nodes[order[0]]):
                pts = snap_start(pts, pads[order[0]].c)
            new_paths.append(pts)
            self.add_track(net, pts, w)
            for n in path:
                tree_nodes[n] = None
            for n in pad_nodes[k]:
                tree_nodes[n] = None
            connected.append(k)
        return True, "ok"


    # ---------------------------------------------------------------- guided
    def nearest_free(self, free, x, y, rad=6):
        i0 = int(round((x - self.ox) / G)); j0 = int(round((y - self.oy) / G))
        best = None
        for r in range(rad + 1):
            for i in range(i0 - r, i0 + r + 1):
                for j in range(j0 - r, j0 + r + 1):
                    if 0 <= i < self.nx and 0 <= j < self.ny and free[i, j]:
                        d = (i - i0) ** 2 + (j - j0) ** 2
                        if best is None or d < best[0]:
                            best = (d, (i, j))
            if best:
                return best[1]
        return None

    def route_guided(self, net, w, chains, padmap):
        """chains: lists of elements; an element is "REF.PAD", an (x, y) guide point,
        or, as a chain's first element, an (x, y) point snapped onto this net's
        copper routed so far. The run turns at most 45 degrees at a guide point."""
        free = self.free_mask(net, w)
        own = {}
        for key, items in padmap.items():
            for it in items:
                for n in self.pad_nodes(it, w):
                    free[n] = True
                    own.setdefault(key, set()).add(n)
        tree = set()
        for chain in chains:
            first = chain[0]
            if isinstance(first, str):
                sources = {n: None for n in own[first]}
            else:
                if not tree:
                    self.remove_net(net)
                    return False, f"{net}: chain starts on copper that is not routed yet"
                fx, fy = first
                n0 = min(tree, key=lambda n: (self.node_xy(*n)[0] - fx) ** 2 + (self.node_xy(*n)[1] - fy) ** 2)
                sources = {n0: None}
            pts_all = []
            for elem in chain[1:]:
                if isinstance(elem, str):
                    targets = own[elem]
                else:
                    t = self.nearest_free(free, *elem)
                    if t is None:
                        self.remove_net(net)
                        return False, f"{net}: guide point {elem} is blocked"
                    targets = {t}
                path = self.astar(free, sources, targets)
                if path is None:
                    self.remove_net(net)
                    return False, f"{net}: no path to {elem}"
                pts_all.extend(path if not pts_all else path[1:])
                tree.update(path)
                end = path[-1]
                if len(path) >= 2:
                    d = (path[-1][0] - path[-2][0], path[-1][1] - path[-2][1])
                    k = DIRS.index(d)
                    sources = {end: {(k - 1) % 8, k, (k + 1) % 8}}
                else:
                    sources = {end: None}
            pts = simplify([self.node_xy(*n) for n in pts_all])
            if isinstance(chain[-1], str):
                pts = snap_end(pts, padmap[chain[-1]][0].c)
            if isinstance(chain[0], str):
                pts = snap_start(pts, padmap[chain[0]][0].c)
            self.add_track(net, pts, w)
            free = self.free_mask(net, w)          # own copper never blocks itself
            for key, nodes in own.items():
                for n in nodes:
                    free[n] = True
        return True, "ok"


def simplify(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            d1 = (round((b[0] - a[0]) / G), round((b[1] - a[1]) / G))
            d2 = (round((p[0] - b[0]) / G), round((p[1] - b[1]) / G))
            if d1[0] * d2[1] == d1[1] * d2[0] and d1[0] * d2[0] + d1[1] * d2[1] > 0:
                out[-1] = p
                continue
        out.append(p)
    return out


def _octi(a, b, tol=0.02):
    dx, dy = b[0] - a[0], b[1] - a[1]
    return abs(dx) < tol or abs(dy) < tol or abs(abs(dx) - abs(dy)) < tol


def snap_end(pts, c):
    """Move the last point onto the pad centre if the final segment stays octilinear
    and parallel to itself; otherwise leave the end inside the pad."""
    if len(pts) < 2:
        return pts
    a, b = pts[-2], pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    if n == 0:
        return pts
    ux, uy = dx / n, dy / n
    # project the centre onto the final line; accept if it lies on it
    t = (c[0] - a[0]) * ux + (c[1] - a[1]) * uy
    px, py = a[0] + t * ux, a[1] + t * uy
    if t > 0 and math.hypot(px - c[0], py - c[1]) < 0.03:
        return pts[:-1] + [c]
    return pts


def snap_start(pts, c):
    return snap_end(pts[::-1], c)[::-1]
