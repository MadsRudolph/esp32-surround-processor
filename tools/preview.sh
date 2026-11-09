#!/usr/bin/env bash
# Render a board to a PNG for a live preview window (imv reloads it on change).
#
#   tools/preview.sh hardware/surround.kicad_pcb OUT.png ["caption"]
#
# Copper (B.Cu) is drawn as the mill sees it, with the silkscreen and outline on top.
set -euo pipefail
PCB=$1; OUT=$2; CAP=${3:-}
TMP=$(mktemp -d)
kicad-cli pcb export svg --mode-single --exclude-drawing-sheet --fit-page-to-board \
    -l "B.Cu,F.Cu,F.Silkscreen,Edge.Cuts" -o "$TMP/b.svg" "$PCB" >/dev/null 2>&1
rsvg-convert -w 1800 -b white "$TMP/b.svg" -o "$TMP/b.png"
if [ -n "$CAP" ] && command -v magick >/dev/null; then
    magick "$TMP/b.png" -gravity North -background '#222' -fill white -pointsize 28 \
        -splice 0x44 -annotate +0+6 "$CAP" "$TMP/b.png"
fi
mv -f "$TMP/b.png" "$OUT"      # atomic swap so the viewer never reads half a file
rm -rf "$TMP"
