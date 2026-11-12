#!/usr/bin/env bash
# Run the board's Dolby Digital parser and decoder on a PC:  tools/dolby_test.sh <file with an AC-3 track>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; C="$ROOT/firmware/components"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
ffmpeg -hide_banner -loglevel error -y -i "$1" -map 0:a:0 -c copy -f spdif "$T/in.spdif"
gcc -O2 -w -fsingle-precision-constant -I"$C/liba52/include" -I"$C/liba52/src" -I"$C/dolby/include" \
    "$ROOT/tools/dolby_test.c" "$C/dolby/dolby.c" "$C"/liba52/src/{bit_allocate,bitstream,downmix,imdct,parse}.c -lm -o "$T/t"
"$T/t" "$T/in.spdif"
