#!/usr/bin/env python3
"""Rewrite a Specctra DSN so the router may only put the fast nets on B.Cu.

    python3 tools/dsn_restrict.py in.dsn out.dsn [--via-cost 300]

WHY. This board is single sided: B.Cu is milled copper, and anything the router
puts on F.Cu is a wire soldered between two through-hole pads on the component
side. A wire link is a fine conductor for a DC rail or a static logic level and
a bad one for anything fast -- it is an uncontrolled-impedance stub standing
3 mm off the board, with no ground beside it and a loop area to match, so it
both radiates and picks up. It is equally bad for the DAC outputs, which would
run as a bare wire straight past the digital section.

So the I2S and ANALOG netclasses get `(circuit (use_layer B.Cu))`, which
FreeRouting honours: verified on this board, F.Cu came back carrying only
+5V/+3V3 branches, the DIR9001 ERROR and AUDIO flags, XSMT, the encoder switch
and the LED, with every I2S and audio net on milled copper. Nets left in
kicad_default may take a link; vias are priced high so the router only spends
one where it has no alternative.

Note that `use_layer` restricts the ROUTER, not the geometry -- a THT pad still
exists on both layers, which is why these links need no drilled via at all.
"""
import re
import sys

RESTRICTED = ("I2S,Default", "ANALOG,Default")


def restrict(text, cls, layer="B.Cu"):
    m = re.search(r"\(class " + re.escape(cls) + r"\b", text)
    if not m:
        return text, False
    at = text.find("(circuit", m.end())
    end = text.find("(rule", m.end())
    if at < 0 or at > end:                      # no circuit scope: make one
        return (text[:end] + f"(circuit\n        (use_layer {layer})\n      )\n      "
                + text[end:]), True
    return text[:at + len("(circuit")] + f"\n        (use_layer {layer})" + text[at + len("(circuit"):], True


AUTOROUTE = """    (autoroute_settings
      (fanout off)
      (autoroute on)
      (postroute on)
      (vias on)
      (via_costs {vc})
      (plane_via_costs {vc})
      (start_ripup_costs 100)
      (start_pass_no 1)
    )
"""


def main():
    src, dst = sys.argv[1], sys.argv[2]
    vc = 300
    if "--via-cost" in sys.argv:
        vc = int(sys.argv[sys.argv.index("--via-cost") + 1])
    t = open(src, encoding="utf-8").read()
    done = []
    for cls in RESTRICTED:
        t, ok = restrict(t, cls)
        done.append(f"{cls}{'' if ok else ' (NOT FOUND)'}")
    # the scope must precede the first (plane ...): the layer rules resolve
    # against the LayerStructure built from the (layer ...) entries before it
    m = re.search(r"^\s*\(plane\s", t, re.M)
    if not m:
        raise SystemExit("no (plane ...) in DSN; expected the GND pour")
    t = t[:m.start()] + "\n" + AUTOROUTE.format(vc=vc) + t[m.start():]
    # Any track already on the board was put there deliberately (the A* finisher
    # pre-routing a net FreeRouting could not reach) and must survive this pass.
    # KiCad exports existing copper as `(type route)`, which FreeRouting is free
    # to rip up; `protect` keeps it and routes around it.
    n_prot = t.count("(type route)")
    t = t.replace("(type route)", "(type protect)")
    open(dst, "w", encoding="utf-8").write(t)
    print(f"restricted to B.Cu: {', '.join(done)}; via cost {vc}; "
          f"{n_prot} pre-routed wire(s) protected -> {dst}")


if __name__ == "__main__":
    main()
