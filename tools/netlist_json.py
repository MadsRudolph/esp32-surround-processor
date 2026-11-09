#!/usr/bin/env python3
"""KiCad netlist (kicadsexpr) -> the small JSON tools/pcb_bootstrap.py reads.

    python3 tools/netlist_json.py surround.net surround.json
"""
import json
import re
import sys
from pathlib import Path


def parse(text):
    """Minimal s-expression reader: nested lists of strings."""
    tok = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack, cur = [], []
    for t in tok:
        if t == "(":
            stack.append(cur); cur = []
        elif t == ")":
            done = cur; cur = stack.pop(); cur.append(done)
        else:
            cur.append(t[1:-1].replace('\\"', '"') if t.startswith('"') else t)
    return cur[0]


def field(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c[1] if len(c) > 1 else ""
    return None


def main(netf, outf):
    tree = parse(Path(netf).read_text(encoding="utf-8"))
    comps, nets = {}, []
    for sec in tree:
        if not isinstance(sec, list) or not sec:
            continue
        if sec[0] == "components":
            for c in sec[1:]:
                ref = field(c, "ref")
                if ref and not ref.startswith("#"):
                    comps[ref] = {"ref": ref, "value": str(field(c, "value")), "footprint": field(c, "footprint"), "pads": {}}
        elif sec[0] == "nets":
            for n in sec[1:]:
                name = field(n, "name")
                if not name or name.startswith("unconnected-"):
                    continue
                nets.append(name)
                for node in n:
                    if isinstance(node, list) and node and node[0] == "node":
                        ref, pin = field(node, "ref"), str(field(node, "pin"))
                        if ref in comps:
                            comps[ref]["pads"][pin] = name
    Path(outf).write_text(json.dumps({"components": list(comps.values()), "nets": nets}, indent=1), encoding="utf-8")
    print(f"{outf}: {len(comps)} components, {len(nets)} nets")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
