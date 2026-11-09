#!/usr/bin/env python3
"""One-screen summary of a kicad-cli DRC JSON report: counts by type, and every
error and every copper or courtyard finding in full."""
import collections
import json
import sys

d = json.load(open(sys.argv[1]))
QUIET = {"silk_overlap", "silk_over_copper", "silk_edge_clearance", "lib_footprint_mismatch", "lib_footprint_issues"}
for k in ("violations", "unconnected_items", "schematic_parity"):
    v = d.get(k, [])
    print(k, len(v), dict(collections.Counter(x["type"] for x in v)))
for x in d.get("violations", []):
    if x["type"] not in QUIET:
        print(" ", x["type"], "|", x["description"][:70], "|", [i["description"][:60] for i in x["items"]])
for x in d.get("unconnected_items", []):
    print("  OPEN", [i["description"][:60] for i in x["items"]])
