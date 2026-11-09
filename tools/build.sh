#!/usr/bin/env bash
# Rebuild everything from the schematic script to the routed board, then check it.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/make_symbols.py >/dev/null
python3 tools/netclasses.py >/dev/null
python3 tools/surround_layout.py | tail -1
( cd hardware
  kicad-cli sch erc --severity-all -o surround.erc surround.kicad_sch 2>&1 | grep -i violations
  kicad-cli sch export netlist --format kicadsexpr -o surround.net surround.kicad_sch >/dev/null 2>&1
  python3 ../tools/netlist_json.py surround.net surround.json )
python3 tools/kpy.py tools/pcb_bootstrap.py 101.88x71.12 | tail -1
python3 tools/kpy.py tools/surround_board.py
kicad-cli pcb drc --severity-all --format json -o /tmp/surround_drc.json hardware/surround.kicad_pcb 2>&1 | grep -i -E "found|unconnected" || true
python3 tools/drc_summary.py /tmp/surround_drc.json
python3 tools/kpy.py tools/check_board.py hardware/surround.kicad_pcb
python3 tools/kpy.py tools/build_notes.py hardware/surround.kicad_pcb
tools/export_production.sh hardware/surround.kicad_pcb hardware/production >/dev/null
