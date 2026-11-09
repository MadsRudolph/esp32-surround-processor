#!/usr/bin/env python3
"""Route a placed board with tools/octoroute.py and write the copper back.

    python3 tools/kpy.py tools/autoroute.py hardware/surround.kicad_pcb [--keep-tracks]

Reads pads, holes and the outline from the board, routes every net except GND
(poured) in priority order, writes B.Cu tracks, adds the U1 escape rule areas and
refills the pour. Prints any net it could not complete.
"""
import math
import sys
import time
from pathlib import Path
import pcbnew
from pcbnew import VECTOR2I, FromMM

sys.path.insert(0, str(Path(__file__).resolve().parent))
import octoroute as oc

ROOT = Path(__file__).resolve().parents[1]
ESP_W, PWR_W, SIG_W = 0.9, 1.0, 0.5
POWER = {"+9V", "+5V", "+5V_DAC1", "+5V_DAC2", "+5V_DIR", "Net-(D2-A)"}
POUR = {"GND"}


def mm(v):
    return pcbnew.ToMM(v)


def board_geometry(board):
    bb = board.GetBoardEdgesBoundingBox()
    return mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetWidth()), mm(bb.GetHeight())


def collect(board, X0, Y0):
    pads = {}
    items = []
    u1 = None
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref == "U1":
            u1 = fp
        for p in fp.Pads():
            pos = p.GetPosition()
            cx, cy = mm(pos.x) - X0, mm(pos.y) - Y0
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                r = mm(p.GetDrillSize().x) / 2
                items.append(oc.Item("hole", "", c=(cx, cy), rad=r, r=r, clr=3.0 - r))
                continue
            if not (p.IsOnLayer(pcbnew.B_Cu)):
                continue
            sz = p.GetSize(pcbnew.B_Cu)
            shp = p.GetShape(pcbnew.B_Cu)
            shape = {pcbnew.PAD_SHAPE_CIRCLE: "circle", pcbnew.PAD_SHAPE_OVAL: "oval"}.get(shp, "rect")
            ang = -p.GetOrientation().AsDegrees()
            it = oc.pad_item(p.GetNetname(), cx, cy, mm(sz.x), mm(sz.y), ang, shape, ref, p.GetNumber())
            it.escape = ref == "U1"
            items.append(it)
            if p.GetNetname():
                pads.setdefault(p.GetNetname(), []).append(it)
    return pads, items, u1


def write_tracks(board, router, X0, Y0):
    nets = board.GetNetsByName()
    for net, segs in router.tracks.items():
        for a, b, w in segs:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(VECTOR2I(FromMM(float(X0 + a[0])), FromMM(float(Y0 + a[1]))))
            t.SetEnd(VECTOR2I(FromMM(float(X0 + b[0])), FromMM(float(Y0 + b[1]))))
            t.SetWidth(FromMM(float(w))); t.SetLayer(pcbnew.B_Cu); t.SetNet(nets[net])
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


def route_board(board, keepouts, escapes, grid_origin, guides=None, order_hint=(), verbose=True, tries=4):
    """keepouts: rectangles no track centre may enter (the module body);
    escapes: rectangles where the 0.30 mm castellation rule applies;
    grid_origin: (ox, oy) so the castellations sit on grid nodes."""
    X0, Y0, W, H = board_geometry(board)
    pads, items, u1 = collect(board, X0, Y0)
    esp_nets = {p.GetNetname() for p in u1.Pads() if p.GetNetname()} - POUR
    r = oc.Router(W, H, origin=grid_origin)
    r.items = items
    r.keepouts = list(keepouts)
    r.escape = list(escapes)
    nets = [n for n in pads if n not in POUR and len(pads[n]) >= 2]

    def width(n):
        if n in esp_nets:
            return ESP_W
        if n in POWER:
            return PWR_W
        return SIG_W

    def span(n):
        xs = [p.c[0] for p in pads[n]]; ys = [p.c[1] for p in pads[n]]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    hint = {n: i for i, n in enumerate(order_hint)}
    order = sorted(nets, key=lambda n: (hint.get(n, len(hint)), -width(n), span(n)))
    guides = guides or {}
    padmap = {}
    for n, plist in pads.items():
        for it in plist:
            padmap.setdefault(f"{it.ref}.{it.num}", []).append(it)
    guided_fail = []
    for n, chains in guides.items():
        ok, msg = r.route_guided(n, width(n), chains, {k: v for k, v in padmap.items() if v[0].net == n})
        if not ok:
            guided_fail.append(n)
            if verbose:
                print("  GUIDE FAIL", msg)
    if verbose:
        print(f"guided: {len(guides) - len(guided_fail)}/{len(guides)}")
    order = [n for n in order if n not in guides or n in guided_fail]
    guided_ok = [n for n in guides if n not in guided_fail]
    failed, best = [], None
    for attempt in range(tries):
        for n in list(r.tracks):
            if n not in guided_ok:
                r.remove_net(n)
        failed = []
        t0 = time.time()
        for n in order:
            ok, msg = r.route_net(n, pads[n], width(n))
            if not ok:
                failed.append(n)
                if verbose:
                    print("  FAIL", msg)
        if verbose:
            print(f"attempt {attempt}: {len(order) - len(failed)}/{len(order)} nets in {time.time() - t0:.1f}s")
        if best is None or len(failed) < len(best[1]):
            best = (list(order), list(failed))
        if not failed:
            break
        # move the failures to the front and try again
        order = failed + [n for n in order if n not in failed]
    if failed and best and len(best[1]) < len(failed):
        # replay the best attempt; the router is deterministic
        for n in list(r.tracks):
            if n not in guided_ok:
                r.remove_net(n)
        failed = []
        for n in best[0]:
            ok, msg = r.route_net(n, pads[n], width(n))
            if not ok:
                failed.append(n)
        if verbose:
            print(f"replayed best attempt: {len(best[0]) - len(failed)}/{len(best[0])}")
    return r, failed + guided_fail, (X0, Y0)


def strip_copper(path):
    """Drop tracks and the U1_escape rule areas from the file text. Removing them
    through pcbnew corrupts its SWIG state and segfaults on save."""
    lines = Path(path).read_text().split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("\t(segment") or ln.startswith("\t(arc") or ln.startswith("\t(via") or ln.startswith("\t(zone"):
            j = i + 1
            while not lines[j].startswith("\t)"):
                j += 1
            block = lines[i:j + 1]
            if ln.startswith("\t(zone") and not any('"U1_escape"' in b for b in block):
                out.extend(block)
            i = j + 1
            continue
        out.append(ln)
        i += 1
    Path(path).write_text("\n".join(out))


def main():
    path = sys.argv[1]
    strip_copper(path)
    board = pcbnew.LoadBoard(path)
    sys.exit("autoroute.py main() is superseded: run tools/surround_board.py")
    write_tracks(board, r, X0, Y0)
    add_rule_areas(board, r.escape, X0, Y0)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print("failed:", failed)


if __name__ == "__main__":
    main()
