"""Stand-in 3D model of the PCM5102 DAC module, face down on its sockets.

    freecadcmd models/make_pcm5102_module.py

Writes one STEP per material next to this script (pcm5102_pcb, _plastic, _pins,
_parts, _jack). KiCad model frame: x = footprint x, y = minus footprint y,
z = 0 at the carrier board's top face. The sizes come from the footprint
PCM5102_Module_FaceDown (31.0 x 17.1 mm board, 1x6 and 1x9 rows, jack overhang);
the parts on the module are blocks in roughly the right places, not a survey.
"""
import os
import re
import FreeCAD as App
import Part
from FreeCAD import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
SOCKET_H = 8.5          # 2.54 mm socket strip on the carrier
HDR_H = 2.54            # header plastic on the module
Z_PCB = SOCKET_H + HDR_H
T_PCB = 1.6


def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def fuse(shapes):
    return Part.makeCompound(shapes)


row6 = [(-13.0, 6.35 - 2.54 * i) for i in range(6)]            # footprint pads 1..6
row9 = [(-6.51 + 2.54 * i, -6.74) for i in range(9)]           # FLT .. L

# module board, with the header holes
pcb = box(-13.88, -8.49, Z_PCB, 17.08, 8.62, Z_PCB + T_PCB)
for x, y in row6 + row9:
    pcb = pcb.cut(Part.makeCylinder(0.5, T_PCB + 1, V(x, y, Z_PCB - 0.5)))

plastic = fuse([box(-14.27, -7.62, SOCKET_H, -11.73, 7.62, Z_PCB),
                box(-7.78, -8.01, SOCKET_H, 15.08, -5.47, Z_PCB)])

pins = fuse([box(x - 0.32, y - 0.32, SOCKET_H - 6.0, x + 0.32, y + 0.32, Z_PCB + T_PCB + 1.4)
             for x, y in row6 + row9])

# parts on the module's component side, which faces the carrier board
def under(x0, y0, x1, y1, h):
    return box(x0, y0, Z_PCB - h, x1, y1, Z_PCB)

parts = fuse([
    under(-3.25, -1.2, 3.25, 3.2, 1.1),        # PCM5102A, TSSOP-20
    under(-9.5, 2.0, -6.6, 3.6, 1.1),          # 3.3 V regulator, SOT-23-5
    under(-9.5, -2.6, -6.6, -1.0, 1.1),        # second regulator
    under(4.6, 4.2, 6.6, 5.45, 0.9),           # chip capacitors
    under(4.6, 1.8, 6.6, 3.05, 0.9),
    under(4.6, -0.6, 6.6, 0.65, 0.9),
    under(-5.6, 5.0, -3.6, 6.25, 0.9),
    under(-2.6, 5.0, -0.6, 6.25, 0.9),
    under(0.4, 5.0, 2.4, 6.25, 0.9),
])

# 3.5 mm jack, hanging off the long edge opposite the 1x9 row
jack = box(9.4, 0.6, Z_PCB - 5.0, 15.4, 11.6, Z_PCB)
barrel = Part.makeCylinder(2.5, 2.5, V(12.4, 11.6, Z_PCB - 2.5), V(0, 1, 0))
bore = Part.makeCylinder(1.8, 6.0, V(12.4, 9.0, Z_PCB - 2.5), V(0, 1, 0))
jack = jack.fuse(barrel).cut(bore)

for name, shape in (('pcb', pcb), ('plastic', plastic), ('pins', pins),
                    ('parts', parts), ('jack', jack)):
    path = os.path.join(HERE, 'pcm5102_%s.step' % name)
    shape.exportStep(path)
    # name the STEP product, so the part can be told apart after export to GLB
    with open(path) as f:
        step = f.read()
    step = re.sub(r'Open CASCADE STEP translator [0-9. ]+', 'pcm5102_%s' % name, step)
    with open(path, 'w') as f:
        f.write(step)
    print('wrote', path)
