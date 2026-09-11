#!/usr/bin/env python3
"""Export a Specctra DSN for FreeRouting, with the via size a milled board can
actually make (1.6 mm ring, 0.8 mm hole = a wire link soldered top side).

    python3 tools/kpy.py tools/dsn_export.py hardware/surround.kicad_pcb out.dsn
"""
import sys
import pcbnew
from pcbnew import FromMM
src, dsn = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
ds = b.GetDesignSettings()
nc = b.GetAllNetClasses()["Default"]
nc.SetViaDiameter(FromMM(1.6)); nc.SetViaDrill(FromMM(0.8))
ds.m_ViasMinSize = FromMM(1.6); ds.m_MinThroughDrill = FromMM(0.8)
pcbnew.SaveBoard(src, b)
ok = pcbnew.ExportSpecctraDSN(b, dsn)
print("dsn export", "ok" if ok else "FAILED", dsn)
