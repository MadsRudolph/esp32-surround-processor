#!/usr/bin/env bash
# Route the single-sided carrier board.
#
# The fast nets -- I2S clocks and data, and the DAC outputs -- are pinned to B.Cu
# for the whole run (tools/dsn_restrict.py), so anything that comes back on F.Cu
# is a wire link, and a wire link is only ever allowed to land on a DC rail or a
# slow control line. tools/wire_links.py enforces that at the end.
#
# Two passes, because order decides everything on one copper layer:
#   1. FreeRouting alone, repeated -- it is not deterministic on this board, so
#      the best of a few runs is the honest answer rather than the first one;
#   2. a fresh board where the nets pass 1 could not reach are drawn FIRST by the
#      A* finisher and marked protected in the DSN, then FreeRouting fills in
#      around them. Drawing a net first guarantees it lands and can cut the board
#      badly enough to cost more than it saved, so the two passes are compared
#      rather than the second one simply being trusted.
#
# Run from the repo root. Needs ~/.freerouting/freerouting-2.4.1.jar.
#
#   tools/route.sh [passes]        default 150
set -euo pipefail
JAR=~/.freerouting/freerouting-2.4.1.jar
MP=${1:-150}
W=$(mktemp -d)
trap 'echo "work dir: $W"' EXIT
K="python3 tools/kpy.py"

run_fr() {   # <in.dsn> <out.ses> <log>
  java -Xmx2500m -XX:+UseSerialGC -jar "$JAR" \
       -de "$1" -do "$2" -mp "$MP" -mt 1 --gui.enabled=false > "$3" 2>&1
}

score() {    # <board> -> "<open FAST links> <open links> <top-layer segments>"
  kicad-cli pcb drc --severity-all --format json -o "$1.json" "$1" >/dev/null 2>&1
  python3 - "$1.json" "$1" <<'PY'
import json, sys, re
# A link left open on a fast net is a defect: those nets may not be wire links,
# so the board is unbuildable until it is drawn. A link left open on a DC rail or
# a slow control line is just a wire the assembler solders. Judge on the first.
FAST = re.compile(r"DIR_BCK|DIR_LRCK|A2-BCKO|A2-LRCKO|A2-DOUT|A1-IO34|A1-IO19|"
                  r"A1-IO23|A3-DIN|A4-DIN|A3-OUT|A4-OUT|J5-Pad|J6-Pad")
d = json.load(open(sys.argv[1]))
fast = tot = 0
for u in d["unconnected_items"]:
    ds = [i["description"] for i in u["items"]]
    if any("Zone" in x for x in ds):
        continue
    tot += 1
    if any(FAST.search(x) for x in ds):
        fast += 1
print(fast, tot, len(re.findall(r'"F\.Cu"\)', open(sys.argv[2]).read())))
PY
}

stuck_nets() {   # <board.json> -> comma-separated net names still open
  python3 - "$1" <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1]))
nets = set()
for u in d["unconnected_items"]:
    ds = [i["description"] for i in u["items"]]
    if any("Zone" in x for x in ds):
        continue
    for x in ds:
        m = re.search(r"\[([^\]]+)\]", x)
        if m:
            nets.add(m.group(1))
print(",".join(sorted(nets)))
PY
}

echo "== pass 1: route a few times, keep the best"
$K tools/dsn_export.py hardware/surround.kicad_pcb "$W/p1.dsn" | grep -v property.h
python3 tools/dsn_restrict.py "$W/p1.dsn" "$W/p1r.dsn"
BEST=99
for i in 1 2 3; do
  run_fr "$W/p1r.dsn" "$W/r$i.ses" "$W/r$i.log"
  $K tools/ses_import.py hardware/surround.kicad_pcb "$W/r$i.ses" "$W/r$i.kicad_pcb" >/dev/null
  cp hardware/surround.kicad_pro "$W/r$i.kicad_pro"; cp hardware/surround.kicad_dru "$W/r$i.kicad_dru"
  S=$(score "$W/r$i.kicad_pcb"); F=${S%% *}
  echo "  run $i: $S"
  if [ "$F" -lt "$BEST" ]; then BEST=$F; cp "$W/r$i.kicad_pcb" "$W/p1.kicad_pcb"; cp "$W/r$i.kicad_pcb.json" "$W/p1.json"; fi
done
cp hardware/surround.kicad_pro "$W/p1.kicad_pro"; cp hardware/surround.kicad_dru "$W/p1.kicad_dru"
STUCK=$(stuck_nets "$W/p1.json")

if [ -z "$STUCK" ]; then
  echo "  every net routed"
  cp "$W/p1.kicad_pcb" hardware/surround.routed.kicad_pcb
else
  echo "  still open: $STUCK"
  echo "== pass 2: draw those first, protect them, route the rest around them"
  $K tools/finish_route.py hardware/surround.kicad_pcb --nets "$STUCK" --write "$W/pre.kicad_pcb" | grep -v property.h
  cp hardware/surround.kicad_pro "$W/pre.kicad_pro"
  $K tools/dsn_export.py "$W/pre.kicad_pcb" "$W/p2.dsn" | grep -v property.h
  python3 tools/dsn_restrict.py "$W/p2.dsn" "$W/p2r.dsn"
  run_fr "$W/p2r.dsn" "$W/p2.ses" "$W/p2.log"
  $K tools/ses_import.py "$W/pre.kicad_pcb" "$W/p2.ses" "$W/p2.kicad_pcb" >/dev/null
  cp hardware/surround.kicad_pro "$W/p2.kicad_pro"; cp hardware/surround.kicad_dru "$W/p2.kicad_dru"
  S1=$(score "$W/p1.kicad_pcb"); S2=$(score "$W/p2.kicad_pcb")
  echo "  pass 1: $S1   (open fast, open total, top-layer segments)"
  echo "  pass 2: $S2"
  if [ "${S2%% *}" -lt "${S1%% *}" ]; then
    echo "  keeping pass 2"; cp "$W/p2.kicad_pcb" hardware/surround.routed.kicad_pcb
  else
    echo "  keeping pass 1"; cp "$W/p1.kicad_pcb" hardware/surround.routed.kicad_pcb
  fi
fi

cp hardware/surround.kicad_pro hardware/surround.routed.kicad_pro
cp hardware/surround.kicad_dru hardware/surround.routed.kicad_dru
echo
$K tools/wire_links.py hardware/surround.routed.kicad_pcb | grep -v property.h
