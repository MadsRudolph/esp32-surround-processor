#!/usr/bin/env bash
# Production files for the mill (Gerber + Excellon, both faces, plus the top silkscreen
# and solder-mask Gerbers that SRM-CAM turns into laser DXFs) and the laser
# (silkscreen DXF, top face).
#
#   tools/export_production.sh hardware/surround.kicad_pcb hardware/production
#
# In SRM-CAM tick Double-sided (dowel pins) and use the profile "SRM-20 0.8 mm ball
# mill": told 0.44 mm, 0.08 mm deep, "Cut gaps too narrow" on. Do NOT pre-mirror
# either face; the CAM mirrors the bottom and reflects the top about the flip axis.
set -euo pipefail
quiet() { "$@" 2>&1 >/dev/null | grep -v "Debug:" >&2 || true; }
PCB=$1
OUT=$2
B=$(basename "$PCB" .kicad_pcb)
LAYERS=${3:-F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,Edge.Cuts}
rm -rf "$OUT/gerbers"
mkdir -p "$OUT/gerbers"
quiet kicad-cli pcb export gerbers -l "$LAYERS" -o "$OUT/gerbers/" "$PCB"
quiet kicad-cli pcb export drill --format excellon -o "$OUT/gerbers/" "$PCB"
quiet kicad-cli pcb export dxf --mode-single -l "F.Silkscreen,Edge.Cuts" --ou mm --drill-shape-opt 0 \
    -o "$OUT/${B}_silk_top.dxf" "$PCB"
ls "$OUT/gerbers"
