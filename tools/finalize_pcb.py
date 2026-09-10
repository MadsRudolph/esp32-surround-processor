#!/usr/bin/env python3
"""Refill the GND pour of a routed board with KiCad's own ZONE_FILLER and save.

    python3 tools/kpy.py tools/finalize_pcb.py <routed.kicad_pcb> [out.kicad_pcb]

place_router.py copies the source board's (unfilled) zone through untouched, so
every connectivity number read from its output is meaningless until the pour
is refilled around the new tracks. Run DRC after this, never before.
"""
import sys
import pcbnew
src = sys.argv[1]; dst = sys.argv[2] if len(sys.argv) > 2 else src
b = pcbnew.LoadBoard(src)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
tracks = [t for t in b.GetTracks()]
layers = {t.GetLayerName() for t in tracks}
print(f"refilled {len(b.Zones())} zone(s); {len(tracks)} track segments on {sorted(layers)}; -> {dst}")
