#!/usr/bin/env python3
"""Run a pcbnew-using script under the system python with the SWIG iterator fixed.

This KiCad build's pcbnew.py wrapper (python 3.14) calls `it.next()` on
SwigPyIterator, which only has `__next__`; every `for x in board.GetTracks()`
then dies with AttributeError. Alias it and run the target script as __main__.

    python3 tools/kpy.py <script.py> [args...]
"""
import runpy, sys
import pcbnew
if not hasattr(pcbnew.SwigPyIterator, "next"):
    pcbnew.SwigPyIterator.next = pcbnew.SwigPyIterator.__next__
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
