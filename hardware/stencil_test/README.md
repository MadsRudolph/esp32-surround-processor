# Solder stencil cutting test (xTool F1 Ultra)

A 60 x 45 mm test coupon for finding laser settings for stencils. It is untested: it has never been cut, and the laser settings are for you to find. Files are 1:1 in millimetres; `stencil_test.svg` usually imports into xTool more reliably than `stencil_test.dxf`. Rebuild both with `python3 make_stencil_test.py`, which also re-checks the DXF. `preview.png` shows the layout.

Layers (same names and colours in DXF and SVG): `CUT_APERTURES` red, cut first; `ENGRAVE_LABELS` blue, light engrave or score; `CUT_OUTLINE` green, cut last so the coupon stays in place.

- **ESP32-WROOM-32 (left)**: the 38 edge pads of U1 from `hardware/surround.kicad_pcb`, as seen from the module side (pin 1 top left, marked "1", antenna end up, marked "ANT"). U1 sits on the back of the board, so this is the view looking at the back. Each aperture is the copper pad minus 0.05 mm per side (pads 1.4 x 0.8 mm, 1.27 mm pitch). The 4.2 mm centre ground pad is a 3 x 3 window pane of 0.95 mm squares.
- **D row**: round holes 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0 mm diameter.
- **W row**: slots 3 mm long, 0.15 to 1.0 mm wide (labels drop the leading zero: ".15" is 0.15 mm).
- **P row**: combs of 8 apertures 1.5 mm long. Pitch 0.5 / 0.65 / 0.8 / 1.27 mm with apertures 0.25 / 0.35 / 0.45 / 0.6 mm wide, leaving webs of 0.25 / 0.30 / 0.35 / 0.67 mm.
- **Chip pads**: 0402, 0603, 0805, 1206, from KiCad's standard R_xxxx_Metric land pads (IPC-7351 nominal) minus 0.05 mm per side. Apertures 0.49 x 0.54, 0.70 x 0.85, 0.925 x 1.30 and 1.025 x 1.65 mm.
- **Scale**: a 10.00 mm square hole and two marks whose centres are 20.00 mm apart.

Smallest aperture: the 0.15 mm slot (0.3 mm smallest hole). Smallest web: 0.25 mm, in the 0.5 mm pitch comb; outside the combs it is 0.47 mm, between the ESP32 edge pads. Rectangles have 0.1 mm corner radius.

What to look at after cutting:
1. Measure the 10.00 mm square. Measured minus 10.00 is the kerf (if the 20.00 marks measure right).
2. Measure the 20.00 marks centre to centre: average of inside and outside edge distances. Off means a scaling problem, not kerf.
3. The smallest hole and slot that came through cleanly, with no slag left in them.
4. The finest comb whose webs are still standing, straight and not burnt through.
5. ESP32 pads: same size along the whole row, and the webs between them intact and flat.
6. Burr or melted rim on the bottom side, and whether the sheet warped.
