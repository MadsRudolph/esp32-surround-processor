#!/usr/bin/env bash
# Regenerate every render from hardware/surround.kicad_pcb.
#
#   hardware/renders/render.sh [--preview] [--shot NAME ...]
#
# 1. prepare_board.py copies the board to board/ and gives every part a 3D model.
# 2. kicad-cli exports the copy to build/board.glb (copper, pads, legend, parts; no mask).
# 3. render.py renders it in Blender (Cycles): bare milled copper on top, green mask below.
# 4. Each PNG gets a .webp copy at quality 88.
# The design file and lib/ are only read. Needs kicad-cli 10, Blender 4.2 or newer and
# ImageMagick. The stand-in models and legend textures in models/ are rebuilt only with
# --models (FreeCAD, Pillow).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$here/build"

args=()
for a in "$@"; do
    if [ "$a" = "--models" ]; then
        freecadcmd "$here/models/make_pcm5102_module.py" | grep wrote
        rm -rf "$here/models/__pycache__"
        python3 "$here/models/make_textures.py"
    else
        args+=("$a")
    fi
done

python3 "$here/prepare_board.py"
kicad-cli pcb export glb -f -o "$here/build/board.glb" --subst-models \
    --include-tracks --include-pads --include-zones --include-silkscreen \
    "$here/board/surround.kicad_pcb" 2>&1 | grep -v 'image handler' || true
blender -b --factory-startup --python "$here/render.py" -- "${args[@]}" 2>&1 | grep -E '^(wrote|render device)|Error|Traceback' || true

for png in "$here"/*.png; do
    [ -e "$png" ] || continue
    if [ ! -e "${png%.png}.webp" ] || [ "$png" -nt "${png%.png}.webp" ]; then
        magick "$png" -quality 88 "${png%.png}.webp"
    fi
done
ls -l "$here"/*.png "$here"/*.webp
