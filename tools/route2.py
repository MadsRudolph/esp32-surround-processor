#!/usr/bin/env python3
"""Route the placed board on its two faces with tools/octoroute.py.

Called by tools/surround_board.py. The bottom face takes every net: first the
lanes the floorplan names (cfg.GUIDES), then whatever is left, shortest first.
The top face takes only the runs in cfg.TOP_ROUTES, each of which must start and
end on a lead that can be soldered from the top. GND is poured on both faces.
"""
import time
import pcbnew
from pcbnew import VECTOR2I, FromMM

import octoroute as oc

ESP_W, PWR_W, SIG_W = 0.9, 1.0, 0.5
POWER = {"+9V", "+5V", "+5V_DAC1", "+5V_DAC2", "+5V_DIR", "Net-(D2-A)"}
POUR = {"GND"}


def mm(v):
    return pcbnew.ToMM(v)


def collect(board, X0, Y0, layer):
    """Copper and holes on one face, as router items; pads by net and by REF.PAD."""
    by_net, by_key, items = {}, {}, []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            pos = p.GetPosition()
            cx, cy = mm(pos.x) - X0, mm(pos.y) - Y0
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                r = mm(p.GetDrillSize().x) / 2
                items.append(oc.Item("hole", "", c=(cx, cy), rad=r, r=r, clr=3.0 - r))
                continue
            if not p.IsOnLayer(layer):
                continue
            sz = p.GetSize(layer)
            shp = p.GetShape(layer)
            shape = {pcbnew.PAD_SHAPE_CIRCLE: "circle", pcbnew.PAD_SHAPE_OVAL: "oval"}.get(shp, "rect")
            ang = -p.GetOrientation().AsDegrees()
            it = oc.pad_item(p.GetNetname(), cx, cy, mm(sz.x), mm(sz.y), ang, shape, ref, p.GetNumber())
            it.escape = ref == "U1"
            items.append(it)
            if p.GetNetname():
                by_net.setdefault(p.GetNetname(), []).append(it)
                by_key.setdefault(f"{ref}.{p.GetNumber()}", []).append(it)
    return by_net, by_key, items


def write_tracks(board, router, X0, Y0, layer):
    nets = board.GetNetsByName()
    for net, segs in router.tracks.items():
        for a, b, w in segs:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(VECTOR2I(FromMM(float(X0 + a[0])), FromMM(float(Y0 + a[1]))))
            t.SetEnd(VECTOR2I(FromMM(float(X0 + b[0])), FromMM(float(Y0 + b[1]))))
            t.SetWidth(FromMM(float(w))); t.SetLayer(layer); t.SetNet(nets[net])
            board.Add(t)


def add_rule_areas(board, rects, X0, Y0):
    for x0, y0, x1, y1 in rects:
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True); z.SetZoneName("U1_escape"); z.SetLayer(pcbnew.B_Cu)
        z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False); z.SetDoNotAllowPads(False)
        z.SetDoNotAllowZoneFills(False); z.SetDoNotAllowFootprints(False)
        ol = z.Outline(); ol.NewOutline()
        for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ol.Append(FromMM(X0 + px), FromMM(Y0 + py))
        board.Add(z)


def run(board, cfg, verbose=True):
    bb = board.GetBoardEdgesBoundingBox()
    X0, Y0, W, H = mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetWidth()), mm(bb.GetHeight())
    X0 += 0.05; Y0 += 0.05; W -= 0.1; H -= 0.1          # the outline's own line width
    UXc, UYc = cfg.UXc, cfg.UYc
    origin = ((UXc + 8.25) % oc.G, (UYc - 8.75) % oc.G)
    esp = {p.GetNetname() for fp in board.GetFootprints() if fp.GetReference() == "U1"
           for p in fp.Pads() if p.GetNetname()} - POUR

    def width(n):
        return ESP_W if n in esp else PWR_W if n in POWER else SIG_W

    # ------------------------------------------------------------ bottom
    by_net, by_key, items = collect(board, X0, Y0, pcbnew.B_Cu)
    r = oc.Router(W, H, origin=origin)
    r.items = items
    r.keepouts = [(UXc - 8.7, UYc - 8.0, W + 1.0, UYc + 8.0)]          # under the module
    r.escape = [(UXc - 9.2, UYc - 12.5, W, UYc - 8.0),                  # north row
                (UXc - 9.2, UYc + 8.0, W, UYc + 12.5),                  # south row
                (UXc - 13.0, UYc - 7.0, UXc - 8.7, UYc + 7.0)]          # west column
    failed = []
    for n, chains in cfg.GUIDES.items():
        ok, msg = r.route_guided(n, cfg.WIDTHS.get(n, width(n)), chains,
                                 {k: v for k, v in by_key.items() if v[0].net == n})
        if not ok:
            failed.append(n)
            print("  GUIDE FAIL", msg)
    guided_ok = [n for n in cfg.GUIDES if n not in failed]
    # nets that are only partly guided still need the rest of their pads joined
    nets = [n for n in by_net if n not in POUR and len(by_net[n]) >= 2
            and (n not in guided_ok or n in cfg.FINISH)]

    def span(n):
        xs = [p.c[0] for p in by_net[n]]; ys = [p.c[1] for p in by_net[n]]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    hint = {n: i for i, n in enumerate(cfg.ORDER)}
    order = sorted(nets, key=lambda n: (hint.get(n, len(hint)), span(n)))
    keep = {n: list(r.tracks.get(n, [])) for n in guided_ok}
    best = None
    for attempt in range(4):
        for n in list(r.tracks):
            r.remove_net(n) if n not in guided_ok else None
        for n in cfg.FINISH:                 # restore the guided part, drop the auto part
            if n in guided_ok:
                r.remove_net(n)
                for a, b, w in keep[n]:
                    r.add_track(n, [a, b], w)
        bad = []
        t0 = time.time()
        for n in order:
            pads = [p for p in by_net[n] if f"{p.ref}.{p.num}" not in cfg.TOP_ONLY.get(n, ())]
            ok, msg = route_rest(r, n, pads, cfg.WIDTHS.get(n, width(n)), n in guided_ok)
            if not ok:
                bad.append(n)
                if verbose:
                    print("  FAIL", msg)
        if verbose:
            print(f"bottom attempt {attempt}: {len(order) - len(bad)}/{len(order)} nets in {time.time() - t0:.1f}s")
        if best is None or len(bad) < len(best[1]):
            best = (list(order), list(bad), {n: list(v) for n, v in r.tracks.items()},
                    [it for it in r.items])
        if not bad:
            break
        order = bad + [n for n in order if n not in bad]
    r.tracks = best[2]; r.items = best[3]
    failed += best[1]
    write_tracks(board, r, X0, Y0, pcbnew.B_Cu)
    add_rule_areas(board, r.escape, X0, Y0)

    # ------------------------------------------------------------ top
    t_net, t_key, t_items = collect(board, X0, Y0, pcbnew.F_Cu)
    t = oc.Router(W, H, origin=origin)
    t.items = t_items
    for n, chains in cfg.TOP_ROUTES.items():
        for ch in chains:
            for e in ch:
                if isinstance(e, str) and not cfg.TOP_OK(e.split(".")[0]):
                    raise SystemExit(f"top route on {n} ends on {e}, which cannot be soldered from the top")
        ok, msg = t.route_guided(n, cfg.TOP_WIDTHS.get(n, PWR_W), chains,
                                 {k: v for k, v in t_key.items() if v[0].net == n})
        if not ok:
            failed.append(n + " (top)")
            print("  TOP FAIL", msg)
    write_tracks(board, t, X0, Y0, pcbnew.F_Cu)

    # ------------------------------------------------------------ pour, both faces
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.GetNetname() == "GND":
            z.SetLayerSet(pcbnew.LSET.AllCuMask(2))
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print(f"routed; not completed: {failed if failed else 'nothing'}")
    return failed


def route_rest(r, net, pads, w, partly):
    """Join the pads of a net. If part of it is already laid along a guide, grow
    from that copper instead of starting again."""
    if not partly:
        return r.route_net(net, pads, w)
    free = r.free_mask(net, w)
    pad_nodes = [r.pad_nodes(p, w) for p in pads]
    for nodes in pad_nodes:
        for n in nodes:
            free[n] = True
    tree = {}
    for a, b, _ in r.tracks.get(net, []):
        na = int(round(max(abs(b[0] - a[0]), abs(b[1] - a[1])) / oc.G))
        for k in range(na + 1):
            x = a[0] + (b[0] - a[0]) * k / max(na, 1); y = a[1] + (b[1] - a[1]) * k / max(na, 1)
            tree[(int(round((x - r.ox) / oc.G)), int(round((y - r.oy) / oc.G)))] = None
    todo = []
    for k, nodes in enumerate(pad_nodes):
        if any(n in tree for n in nodes):
            for n in nodes:
                tree[n] = None
        else:
            todo.append(k)
    while todo:
        import numpy as np
        tx = np.array([r.node_xy(*n) for n in tree])
        todo.sort(key=lambda k: np.min(np.hypot(tx[:, 0] - pads[k].c[0], tx[:, 1] - pads[k].c[1])))
        k = todo.pop(0)
        path = r.astar(free, tree, set(pad_nodes[k]))
        if path is None:
            return False, f"{net}: no path to {pads[k].ref}.{pads[k].num}"
        pts = oc.snap_end(oc.simplify([r.node_xy(*n) for n in path]), pads[k].c)
        r.add_track(net, pts, w)
        for n in path:
            tree[n] = None
        for n in pad_nodes[k]:
            tree[n] = None
    return True, "ok"
