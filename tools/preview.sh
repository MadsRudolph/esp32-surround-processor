#!/usr/bin/env bash
# Render a board to a PNG for a live preview window (imv reloads it on change).
#
#   tools/preview.sh hardware/surround.kicad_pcb OUT.png [layers]
#
# Default: both copper faces seen from the top, with the silkscreen and outline.
set -euo pipefail
PCB=$1; OUT=$2; LAYERS=${3:-B.Cu,F.Cu,F.Silkscreen,Edge.Cuts}
TMP=$(mktemp -d)
kicad-cli pcb export svg --mode-single --exclude-drawing-sheet --page-size-mode 2 \
    -l "$LAYERS" -o "$TMP/b.svg" "$PCB" >/dev/null 2>&1
rsvg-convert -w 1900 -b white "$TMP/b.svg" -o "$TMP/b.png"
mv -f "$TMP/b.png" "$OUT"      # atomic swap so the viewer never reads half a file
rm -rf "$TMP"
