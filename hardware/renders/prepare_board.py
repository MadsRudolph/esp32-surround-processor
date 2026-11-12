#!/usr/bin/env python3
"""Copy hardware/surround.kicad_pcb to renders/board/ and give every part a 3D model.

The design file is only read. In the copy:
  - model paths that do not resolve under KiCad 10 are pointed at stock models,
  - footprints with no model get one (stock where one fits, the stand-in for the
    PCM5102 modules).
Prints what it did per footprint.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'surround.kicad_pcb'
DST = HERE / 'board' / 'surround.kicad_pcb'
K = '${KICAD10_3DMODEL_DIR}'
M = '${KIPRJMOD}/../models'


def model(path, off=(0, 0, 0), rot=(0, 0, 0)):
    return ('\t\t(model "%s"\n\t\t\t(offset\n\t\t\t\t(xyz %g %g %g)\n\t\t\t)\n\t\t\t(scale\n\t\t\t\t(xyz 1 1 1)\n\t\t\t)\n'
            '\t\t\t(rotate\n\t\t\t\t(xyz %g %g %g)\n\t\t\t)\n\t\t)\n' % ((path,) + tuple(off) + tuple(rot)))


PHX = K + '/TerminalBlock_Phoenix.3dshapes/TerminalBlock_Phoenix_MKDS-1,5-%d-5.08_1x0%d_P5.08mm_Horizontal.step'
SOCK = K + '/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x0%d_P2.54mm_Vertical.step'

# footprint name -> (list of model blocks, note). Replaces whatever the footprint carries.
FIX = {
    'TerminalBlock_2P_P5.08mm': ([model(PHX % (2, 2))],
                                 'vendored bornier-2 STEP is gone from KiCad 10: stock Phoenix MKDS 1,5/2-5.08'),
    'TerminalBlock_TS_P5.08mm': ([model(PHX % (2, 2))],
                                 'vendored bornier-2 STEP is gone from KiCad 10: stock Phoenix MKDS 1,5/2-5.08'),
    'TerminalBlock_TRS_P5.08mm': ([model(PHX % (3, 3))],
                                  'vendored bornier-3 STEP is gone from KiCad 10: stock Phoenix MKDS 1,5/3-5.08'),
    'CP_Radial_D5.0mm_P3.50mm_FormedLeads': (
        [model(K + '/Capacitor_THT.3dshapes/CP_Radial_D5.0mm_P2.50mm.step', off=(0.5, 0, 0))],
        'no such stock model: 5 mm can at 2.5 mm pitch, centred between the 3.5 mm holes'),
    'LED_D3.0mm_P5.08mm_LaserPads': (
        [model(K + '/LED_THT.3dshapes/LED_D3.0mm.step', off=(1.27, 0, 0))],
        'no model: stock 3 mm LED centred between the 5.08 mm holes (its legs are not spread)'),
    'TO-220-3_Vertical_LaserPads': (
        [model(K + '/Package_TO_SOT_THT.3dshapes/TO-220-3_Vertical.step')],
        'path used KICAD9_3DMODEL_DIR: same stock model through KICAD10_3DMODEL_DIR'),
    'DIR9001_Pigtail_1x6': (
        [model(K + '/Connector_JST.3dshapes/JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical.step',
               off=(0, -12.6, 0), rot=(0, 0, -90))],
        'no model: the photos show a 6-pin JST XH header here, stock B6B-XH-A (2.5 mm pitch in 2.54 mm holes)'),
    'TestPoint_THTPad_D2.0mm_Drill1.0mm': (
        [model(K + '/Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x01_P2.54mm_Vertical.step')],
        'no model: single header pin as a scope ground (seen on TP2 in the photos; TP1 assumed the same)'),
    'PCM5102_Module_FaceDown': (
        [model(SOCK % 6, off=(-13, 6.35, 0)),
         model(SOCK % 9, off=(-6.51, -6.74, 0), rot=(0, 0, -90))]
        + [model('%s/pcm5102_%s.step' % (M, p)) for p in ('pcb', 'plastic', 'pins', 'parts', 'jack')],
        'no model: stock 1x6 and 1x9 sockets plus the stand-in module from models/'),
}


def blocks(s):
    """Yield (start, end) of each top-level (footprint ...) block."""
    for m in re.finditer(r'\n\t\(footprint "', s):
        i = m.start() + 2
        depth, j, instr = 0, i, False
        while True:
            c = s[j]
            if instr:
                if c == '\\':
                    j += 1
                elif c == '"':
                    instr = False
            elif c == '"':
                instr = True
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield i, j + 1


def main():
    s = SRC.read_text(encoding='utf-8')
    out, pos, log = [], 0, []
    for i, j in blocks(s):
        b = s[i:j]
        name = re.match(r'\(footprint "([^"]+)"', b).group(1).split(':')[-1]
        ref = re.search(r'\(property "Reference" "([^"]+)"', b).group(1)
        if name in FIX:
            mods, note = FIX[name]
            b = re.sub(r'\t\t\(model "[^"]*"\n(?:\t\t\t.*\n)*\t\t\)\n', '', b)
            assert b.endswith('\n\t)'), ref
            b = b[:-2] + ''.join(mods) + '\t)'
            log.append((ref, name, note))
        elif '(model ' not in b:
            log.append((ref, name, 'no model, left bare'))
        out.append(s[pos:i]); out.append(b); pos = j
    out.append(s[pos:])
    DST.parent.mkdir(exist_ok=True)
    DST.write_text(''.join(out), encoding='utf-8')
    shutil.copy(SRC.with_suffix('.kicad_pro'), DST.with_suffix('.kicad_pro'))
    for ref, name, note in sorted(log):
        print('%-4s %-38s %s' % (ref, name, note))


if __name__ == '__main__':
    sys.exit(main())
