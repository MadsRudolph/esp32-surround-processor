#!/usr/bin/env bash
# Production files for the mill (Gerber + Excellon) and the laser (silkscreen DXF).
# Linux version of the kicad-laser-pcb skill's export_production.ps1.
#
#   tools/export_production.sh hardware/surround.kicad_pcb hardware/production
#
# In SRM-CAM use the profile "SRM-20 0.8 mm ball mill": told 0.44 mm, 0.08 mm deep,
# "Cut gaps too narrow" on. Isolate B.Cu and do NOT pre-mirror; the CAM mirrors when
# the board is flipped.
set -euo pipefail
quiet() { "$@" 2>&1 >/dev/null | grep -v "Debug:" >&2 || true; }
PCB=$1
OUT=$2
B=$(basename "$PCB" .kicad_pcb)
mkdir -p "$OUT/gerbers"
quiet kicad-cli pcb export gerbers -l "B.Cu,Edge.Cuts" -o "$OUT/gerbers/" "$PCB"
quiet kicad-cli pcb export drill --format excellon -o "$OUT/gerbers/" "$PCB"
quiet kicad-cli pcb export dxf --mode-single -l "F.Silkscreen,Edge.Cuts" --ou mm --drill-shape-opt 0 \
    -o "$OUT/${B}_silk_top.dxf" "$PCB"
ls "$OUT/gerbers"
