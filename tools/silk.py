#!/usr/bin/env python3
"""Silkscreen for the fiber laser: F.Silkscreen only, top side, unmirrored.

Called by tools/surround_board.py. Every reference goes in the first free spot
on or beside its own part; function labels say what each connector pin, button
and LED is. Nothing may sit on a pad, and values live on F.Fab, out of the etch.
"""
import pcbnew
from pcbnew import VECTOR2I

import surround_board as cfg

X0, Y0, W, H = cfg.X0, cfg.Y0, cfg.W, cfg.H
UXc, UYc = cfg.UXc, cfg.UYc
SILK_H, SILK_W = 1.0, 0.15


def mm(v):
    return pcbnew.FromMM(float(v))


def _box(t):
    b = t.GetBoundingBox()
    return (pcbnew.ToMM(b.GetLeft()) - X0, pcbnew.ToMM(b.GetTop()) - Y0,
            pcbnew.ToMM(b.GetRight()) - X0, pcbnew.ToMM(b.GetBottom()) - Y0)


def _hit(a, b, m=0.0):
    return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]


def dress_silk(board, fps):
    blocked = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            b = pad.GetBoundingBox()
            blocked.append((pcbnew.ToMM(b.GetLeft()) - X0, pcbnew.ToMM(b.GetTop()) - Y0,
                            pcbnew.ToMM(b.GetRight()) - X0, pcbnew.ToMM(b.GetBottom()) - Y0))
    def seg_box(a, b, w=0.15):
        return (min(a[0], b[0]) - w, min(a[1], b[1]) - w, max(a[0], b[0]) + w, max(a[1], b[1]) + w)

    def silk_shapes(items):
        out = []
        for g in items:
            if g.GetLayer() != pcbnew.F_SilkS or not isinstance(g, pcbnew.PCB_SHAPE):
                continue
            st = g.GetShape()
            if st in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY):
                pts = [g.GetRectCorners()[i] for i in range(4)] if st == pcbnew.SHAPE_T_RECT else \
                    [g.GetPolyShape().COutline(0).CPoint(i) for i in range(g.GetPolyShape().COutline(0).PointCount())]
                pts = [(pcbnew.ToMM(v.x) - X0, pcbnew.ToMM(v.y) - Y0) for v in pts]
                out += [seg_box(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
            elif st == pcbnew.SHAPE_T_SEGMENT:
                a = g.GetStart(); b = g.GetEnd()
                out.append(seg_box((pcbnew.ToMM(a.x) - X0, pcbnew.ToMM(a.y) - Y0), (pcbnew.ToMM(b.x) - X0, pcbnew.ToMM(b.y) - Y0)))
            else:
                bb = g.GetBoundingBox()
                out.append((pcbnew.ToMM(bb.GetLeft()) - X0, pcbnew.ToMM(bb.GetTop()) - Y0,
                            pcbnew.ToMM(bb.GetRight()) - X0, pcbnew.ToMM(bb.GetBottom()) - Y0))
        return out

    for fp in board.GetFootprints():
        blocked += silk_shapes(fp.GraphicalItems())
    placed = []

    def free(box, m=0.35):
        if box[0] < 0.6 or box[1] < 0.6 or box[2] > W - 0.6 or box[3] > H - 0.6:
            return False
        return not any(_hit(box, b, m) for b in blocked) and not any(_hit(box, b, m + 0.05) for b in placed)

    # labels first: they are where they must be
    for text, x, y, ang, size in cfg.LABELS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(SILK_W))
        t.SetTextAngleDegrees(ang); t.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
        board.Add(t)
        placed.append(_box(t))
    # module outline: it sits on the back, so its shape helps when fitting the sockets
    for (xa, ya, xb, yb) in ((UXc - 9.88, UYc - 9.12, W - 0.3, UYc - 9.12), (UXc - 9.88, UYc + 9.12, W - 0.3, UYc + 9.12),
                             (UXc - 9.88, UYc - 9.12, UXc - 9.88, UYc + 9.12)):
        ln = pcbnew.PCB_SHAPE(board)
        ln.SetShape(pcbnew.SHAPE_T_SEGMENT); ln.SetLayer(pcbnew.F_SilkS); ln.SetWidth(mm(0.15))
        ln.SetStart(VECTOR2I(mm(X0 + xa), mm(Y0 + ya))); ln.SetEnd(VECTOR2I(mm(X0 + xb), mm(Y0 + yb)))
        board.Add(ln)
        blocked.append(seg_box((xa, ya), (xb, yb)))
    pads = {f"{fp.GetReference()}.{q.GetNumber()}": q for fp in board.GetFootprints() for q in fp.Pads()}
    unplaced = []
    for text, key, size, fixed in cfg.PAD_LABELS:
        q = pads[key]
        px, py = pcbnew.ToMM(q.GetPosition().x) - X0, pcbnew.ToMM(q.GetPosition().y) - Y0
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(SILK_W))
        ok = False
        if fixed:
            dx, dy, ang = fixed
            # the stacked terminals alternate direction: follow the pin order
            t.SetTextAngleDegrees(ang)
            t.SetPosition(VECTOR2I(mm(X0 + px + dx), mm(Y0 + py + dy)))
            t.SetTextThickness(mm(0.12))
            ok = free(_box(t), m=0.05)
        else:
            for sz in (size, 0.8):
                t.SetTextSize(VECTOR2I(mm(sz), mm(sz)))
                w = len(text) * sz * 0.45
                for ang in (0, 90):
                    t.SetTextAngleDegrees(ang)
                    along, across = (w, 0.0) if ang == 0 else (0.0, w)
                    for rad in (1.8, 2.6, 3.4, 4.4, 5.6, 7.0):
                        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0.7, -0.7), (-0.7, -0.7), (0.7, 0.7), (-0.7, 0.7)):
                            x = px + dx * (rad + (along if dx else 0)); y = py + dy * (rad + (across if dy else 0))
                            t.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
                            if free(_box(t)):
                                ok = True
                                break
                        if ok:
                            break
                    if ok:
                        break
                if ok:
                    break
        if ok:
            board.Add(t)
            placed.append(_box(t))
        else:
            unplaced.append(f"label {text}@{key}")
    for ref in sorted(fps, key=lambda r: -fps[r].GetCourtyard(pcbnew.F_CrtYd).BBox().GetArea()
                      if fps[r].GetCourtyard(pcbnew.F_CrtYd).OutlineCount() else 0):
        fp = fps[ref]
        r = fp.Reference()
        if ref == "U1":                      # on the back: its texts stay there
            r.SetVisible(False)
            continue
        fp.Value().SetLayer(pcbnew.F_Fab)
        if ref.startswith("H") or ref in cfg.REF_HIDE:
            r.SetVisible(False)
            continue
        if ref in cfg.REF_POS:               # a spot chosen by hand
            x, y, ang = cfg.REF_POS[ref]
            r.SetVisible(True); r.SetLayer(pcbnew.F_SilkS)
            r.SetTextSize(VECTOR2I(mm(SILK_H), mm(SILK_H))); r.SetTextThickness(mm(SILK_W))
            r.SetKeepUpright(True)
            r.SetTextAngleDegrees(ang)
            r.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
            placed.append(_box(r))
            continue
        r.SetVisible(True); r.SetLayer(pcbnew.F_SilkS)
        r.SetTextSize(VECTOR2I(mm(SILK_H), mm(SILK_H))); r.SetTextThickness(mm(SILK_W))
        r.SetKeepUpright(True)
        c = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False)
        x0, y0 = pcbnew.ToMM(bb.GetLeft()) - X0, pcbnew.ToMM(bb.GetTop()) - Y0
        x1, y1 = pcbnew.ToMM(bb.GetRight()) - X0, pcbnew.ToMM(bb.GetBottom()) - Y0
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if "CP_Radial" in str(fp.GetFPID().GetLibItemName()):
            # in the clear half of the can's outline, above the + pad
            inside = [(x0 + 0.3 * (x1 - x0), y0 + 2.0, 0)] if x1 - x0 > 9.0 else []
        else:
            inside = [(cx, cy, 0), (cx, cy, 90), (cx, y0 + 1.1, 0), (cx, y1 - 1.1, 0)]
        cands = inside + [(cx, y0 - 0.8, 0), (cx, y1 + 0.8, 0),
                 (x0 - 0.8, cy, 90), (x1 + 0.8, cy, 90), (x0 - 2.0, cy, 0), (x1 + 2.0, cy, 0)]
        for dx in (-2.0, 2.0, -4.0, 4.0):
            cands += [(cx + dx, y0 - 0.8, 0), (cx + dx, y1 + 0.8, 0)]
        for dy in (-2.0, 2.0, -4.0, 4.0):
            cands += [(x0 - 0.8, cy + dy, 90), (x1 + 0.8, cy + dy, 90)]
        for x, y, ang in cands:
            r.SetTextAngleDegrees(ang)
            r.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
            if free(_box(r)):
                placed.append(_box(r))
                break
        else:
            # one more round at 0.8 mm before giving up
            r.SetTextSize(VECTOR2I(mm(0.8), mm(0.8))); r.SetTextThickness(mm(0.12))
            for x, y, ang in cands:
                r.SetTextAngleDegrees(ang)
                r.SetPosition(VECTOR2I(mm(X0 + x), mm(Y0 + y)))
                if free(_box(r)):
                    placed.append(_box(r))
                    break
            else:
                unplaced.append(ref)
                r.SetVisible(False)          # better no reference than one on a pad
    return unplaced


