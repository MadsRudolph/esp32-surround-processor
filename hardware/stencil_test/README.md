# Solder stencil cutting test

A 22 x 22 mm coupon for finding out what the xTool F1 Ultra can cut as a solder
stencil. It has never been cut; the laser settings are for you to find.

Files: `stencil_test.dxf` and `stencil_test.svg` hold the same geometry at 1:1 in mm.
Import the SVG if the DXF misbehaves. `preview.png` shows it; `make_stencil_test.py`
regenerates all three.

Colours: red (layer `CUT_APERTURES`) are the openings, green (layer `CUT_OUTLINE`) is
the outline, to be cut last. There are no labels and nothing to engrave.

What is on it, with the antenna end of the ESP32 footprint at the top and pin 1 top left:

- **Around the edge:** the 38 pads of the ESP32-WROOM-32 from this board's footprint, each
  0.05 mm smaller per side than the copper pad. Smallest strip between two pads: 0.47 mm.
- **Middle:** the centre ground pad as a 3 x 3 grid of 0.95 mm squares.
- **Top row, round holes, left to right:** 0.3, 0.4, 0.5, 0.6, 0.8, 1.0 mm.
- **Second row, two combs of eight openings, 1.5 mm long:** left 0.5 mm pitch with
  0.25 mm openings (0.25 mm strips between them, the hardest thing on the coupon),
  right 0.65 mm pitch with 0.35 mm openings.
- **Lower row, slots 3 mm long, left to right:** 0.15, 0.20, 0.25, 0.30, 0.40, 0.50 mm wide.

After cutting, look at: the narrowest slot and smallest hole that come out clean and
open, whether the strips in the left comb survive, whether the pad corners are sharp or
burnt round, and how flat the sheet stays. The outline is 22.00 mm square, and the outer
edges of the left and right pad columns are 18.90 mm apart: measure both with calipers
to get scale and kerf.
