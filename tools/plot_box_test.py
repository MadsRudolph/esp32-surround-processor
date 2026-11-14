#!/usr/bin/env python3
"""Graphs of the finished-box test, as SVG in the style of the project page.

    python3 tools/plot_box_test.py [hardware/bench/box-test-2026-11-14.json]

Writes docs/img/box-rear-matrix.svg and docs/img/box-output-levels.svg.
The data comes from the AD3: S/PDIF from tools/spdif_gen.py into the coax input,
10x probes on the RCA outputs.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "hardware/bench/box-test-2026-11-14.json"
OUT = ROOT / "docs/img"

BG, WHITE, MUTED, NOTE = "#151312", "#ffffff", "#8f8888", "#c3c2b7"
ORANGE, BLUE = "#d95926", "#3987e5"          # the site's series pair; checked for colour-blind separation
GRID = "rgba(255,255,255,0.09)"
STYLE = (".t{font:600 17px system-ui,sans-serif;fill:#ffffff}.s{font:14px system-ui,sans-serif;fill:#8f8888}"
         ".a{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#8f8888}"
         ".h{font:600 14px system-ui,sans-serif;fill:#ffffff}.v{font:13px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#c3c2b7}"
         ".n{font:13px system-ui,sans-serif;fill:#c3c2b7}.lab{font:13px system-ui,sans-serif;fill:#c3c2b7}")


def svg(w, h, label, body):
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{label}">\n<rect width="{w}" height="{h}" fill="{BG}"/>\n<style>{STYLE}</style>\n'
            + "\n".join(body) + "\n</svg>\n")


def legend(x, y, items, dots=False, left=False):
    """Swatch + label pairs in a row: right-aligned at x, or left-aligned with left=True.
    Lines for line charts, dots for dot plots."""
    out = []
    if left:
        cx = x
        for colour, dash, text in items:
            if dots:
                out.append(f'<circle cx="{cx + 6}" cy="{y}" r="6" fill="{colour}"/>'); cx += 20
            else:
                d = f' stroke-dasharray="{dash}"' if dash else ""
                out.append(f'<line x1="{cx}" y1="{y}" x2="{cx + 22}" y2="{y}" stroke="{colour}" stroke-width="2.5"{d}/>'); cx += 30
            out.append(f'<text class="lab" x="{cx}" y="{y + 4.5}">{text}</text>')
            cx += 7.2 * len(text) + 28
        return out
    cx = x
    for colour, dash, text in reversed(items):
        cx -= 7.2 * len(text)
        out.append(f'<text class="lab" x="{cx:.1f}" y="{y + 4.5}">{text}</text>')
        cx -= 30
        d = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<line x1="{cx:.1f}" y1="{y}" x2="{cx + 22:.1f}" y2="{y}" stroke="{colour}" stroke-width="2.5"{d}/>')
        cx -= 22
    return out


def rear_matrix(d):
    cases = d["matrix_test"]["cases"]
    fs = d["matrix_test"]["fs"]
    panels = [("inverted", "Left, and right inverted", "expected: full level"),
              ("inphase", "Left = right", "expected: silence"),
              ("leftonly", "Left only", "expected: half level, −6 dB")]
    W, H = 900, 400
    x0s, pw = [66, 341, 616], 250                 # three panels, 25 px apart
    ytop, ph = 128, 196
    vmax, ms = 0.8, 3.0                           # ±0.8 V, 3 ms
    n = int(fs * ms / 1000)
    body = [f'<text class="t" x="18" y="26">Rear outputs in surround mode</text>',
            f'<text class="s" x="18" y="45">Both rears get half of left minus right. The same 1 kHz tone at −12 dBFS on both inputs, three ways.</text>']
    body += legend(882, 64, [(ORANGE, None, "SURR L"), (BLUE, "6 4", "SURR R")])
    for (key, title, expect), px in zip(panels, x0s):
        c = cases[key]
        l, r = c["surr_l_V"], c["surr_r_V"]
        ml, mr = sum(l) / len(l), sum(r) / len(r)          # the AD3 inputs sit a few mV off zero
        l = [v - ml for v in l]; r = [v - mr for v in r]
        start = 0
        if c["surr_l_mV_rms"] > 20:                         # line up on a rising zero crossing
            start = next(i for i in range(1, len(l) - n) if l[i - 1] < 0 <= l[i])
        Y = lambda v: ytop + ph / 2 - v / vmax * (ph / 2)
        X = lambda i: px + i / n * pw
        body.append(f'<text class="h" x="{px}" y="{ytop - 38}">{title}</text>')
        body.append(f'<text class="v" x="{px}" y="{ytop - 18}">L {c["surr_l_mV_rms"]:.0f} · R {c["surr_r_mV_rms"]:.0f} mV rms</text>')
        for v in (-0.5, 0.0, 0.5):
            body.append(f'<line x1="{px}" y1="{Y(v):.1f}" x2="{px + pw}" y2="{Y(v):.1f}" stroke="{GRID}" stroke-width="{1.4 if v == 0 else 1}"/>')
            if px == x0s[0]:
                body.append(f'<text class="a" x="{px - 9}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:+.1f} V</text>'.replace("+0.0", "0"))
        for t in range(0, int(ms) + 1):
            xx = px + t / ms * pw
            body.append(f'<line x1="{xx:.1f}" y1="{ytop}" x2="{xx:.1f}" y2="{ytop + ph}" stroke="{GRID}" stroke-width="1"/>')
            body.append(f'<text class="a" x="{xx:.1f}" y="{ytop + ph + 18}" text-anchor="middle">{t}</text>')
        for wave, colour, dash in ((l, ORANGE, None), (r, BLUE, "6 4")):
            pts = " ".join(f"{X(i):.1f},{Y(wave[start + i]):.1f}" for i in range(n + 1))
            dd = f' stroke-dasharray="{dash}"' if dash else ""
            body.append(f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="2" stroke-linejoin="round"{dd}/>')
        body.append(f'<text class="n" x="{px}" y="{ytop + ph + 44}">{expect}</text>')
    body.append(f'<text class="a" x="{x0s[2] + pw}" y="{ytop + ph + 44}" text-anchor="end">ms</text>')
    return svg(W, H, "Rear output waveforms in surround mode for three input cases", body)


def output_levels(d):
    bench, box = d["levels_V_rms"]["bench_test_firmware"], d["levels_V_rms"]["in_the_box_spdif"]
    names = ["FRONT L", "FRONT R", "SURR L", "SURR R"]
    W, H = 900, 350
    x0, x1, lo, hi = 150, 620, 0.40, 0.55
    X = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    ytop, row = 130, 42
    body = [f'<text class="t" x="18" y="26">Line output level, 1 kHz at −12 dBFS</text>',
            f'<text class="s" x="18" y="45">Each output on the bench with a test firmware, and in the finished box fed S/PDIF. Volume at maximum.</text>']
    body += legend(x0, 76, [(ORANGE, None, "bench, test firmware"), (BLUE, None, "finished box, S/PDIF in")], dots=True, left=True)
    ybot = ytop + row * (len(names) - 1)
    for k in range(0, 4):
        v = lo + k * 0.05
        body.append(f'<line x1="{X(v):.1f}" y1="{ytop - 18}" x2="{X(v):.1f}" y2="{ybot + 18}" stroke="{GRID}" stroke-width="1"/>')
        body.append(f'<text class="a" x="{X(v):.1f}" y="{ybot + 38}" text-anchor="middle">{v:.2f}</text>')
    body.append(f'<text class="a" x="{x1}" y="{ybot + 58}" text-anchor="end">V rms</text>')
    body.append(f'<text class="a" x="{x1 + 36}" y="{ytop - 26}">bench → box</text>')
    for i, nm in enumerate(names):
        y = ytop + i * row
        a, b = bench[nm], box[nm]
        body.append(f'<text class="lab" x="{x0 - 16}" y="{y + 4.5}" text-anchor="end">{nm}</text>')
        body.append(f'<line x1="{X(b):.1f}" y1="{y}" x2="{X(a):.1f}" y2="{y}" stroke="{MUTED}" stroke-width="2"/>')
        for v, colour in ((a, ORANGE), (b, BLUE)):
            body.append(f'<circle cx="{X(v):.1f}" cy="{y}" r="6" fill="{colour}" stroke="{BG}" stroke-width="2"/>')
        db = 20 * __import__("math").log10(b / a)
        body.append(f'<text class="v" x="{x1 + 36}" y="{y + 4.5}">{a:.3f} → {b:.3f}  ({db:+.1f} dB)</text>'.replace("(-", "(−"))
    return svg(W, H, "Line output level of the four outputs, bench against finished box", body)


if __name__ == "__main__":
    d = json.loads(DATA.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "box-rear-matrix.svg").write_text(rear_matrix(d))
    (OUT / "box-output-levels.svg").write_text(output_levels(d))
    print("wrote", OUT / "box-rear-matrix.svg", "and", OUT / "box-output-levels.svg")
