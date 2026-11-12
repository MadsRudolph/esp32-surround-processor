# Renders

3D renders of the surround carrier board as it is built: bare milled copper with a
laser-marked legend on top, a hand-applied green mask over the copper underneath, on
four black hex standoffs. Matched by eye to photos of the finished board (the photos
are not in the repository).

| File | View | Size |
|---|---|---|
| `hero.png` | lead image, low three-quarter view from the south-east | 1920 x 1280 |
| `hero_stacked.png` | same view with the DIR9001 board stacked above and its pigtail | 1920 x 1280 |
| `top_34.png` | top face, three-quarter view | 1920 x 1280 |
| `bottom_34.png` | bottom face, three-quarter view, board turned over left to right | 1920 x 1280 |
| `top.png` | top face, straight down, no perspective | 2000 x 1500 |
| `bottom.png` | bottom face, straight on, no perspective (east edge on the left) | 2000 x 1500 |

Each has a `.webp` copy at quality 88 for the web.

## How they are made

    hardware/renders/render.sh              # everything
    hardware/renders/render.sh --preview    # half size, quick, into build/
    hardware/renders/render.sh --shot hero  # one shot: hero hero_stacked top_34 bottom_34 top bottom
    hardware/renders/render.sh --models     # also rebuild the stand-in models and legend textures

1. `prepare_board.py` copies `hardware/surround.kicad_pcb` to `board/` and gives every
   part a 3D model. The design file and `lib/` are only read.
2. `kicad-cli pcb export glb` exports the copy with tracks, zones, pads, legend and
   parts, and without the mask layers, to `build/board.glb`.
3. `render.py` renders that in Blender with Cycles: copper, mask, laminate and legend
   materials, lead trimming, solder joints, standoffs, the DIR9001 stand-in, lights
   and cameras.
4. ImageMagick writes the `.webp` copies.

Needs kicad-cli 10, Blender (made with 5.2) and ImageMagick. A full run takes about
four minutes on an RTX 3060.

`kicad-cli pcb render` was tried first. Its ray tracer places the parts correctly but
always draws a solder mask, so it cannot show this board as it is.

## 3D models

Fixed in the copy by `prepare_board.py`:

| Parts | Problem in the design file | Model used |
|---|---|---|
| J1, J3, J4 | vendored `bornier-2` STEP is not in KiCad 10 | stock Phoenix MKDS 1,5/2-5.08 |
| J5, J6 | vendored `bornier-3` STEP is not in KiCad 10 | stock Phoenix MKDS 1,5/3-5.08 |
| U2, U3 | path uses `KICAD9_3DMODEL_DIR` | same stock TO-220, through `KICAD10_3DMODEL_DIR` |
| C11 | names a model that does not exist (3.5 mm formed leads) | stock 5 mm can, 2.5 mm pitch, centred |
| D1, D4 | no model | stock 3 mm LED, centred between the 5.08 mm holes |
| A3, A4 | no model | stock 1x6 and 1x9 sockets, plus the stand-in in `models/` |
| A2 | no model | stock JST XH B6B-XH-A header, as fitted on the real board |
| TP1, TP2 | no model | stock single header pin (seen on TP2 in the photos, TP1 assumed) |
| H1 to H4 | no model | hex standoffs, added in `render.py` |

Every other part already had a stock KiCad model.

## What is faithful and what is not

Faithful to the design file:

- the outline, every hole, all the copper on both faces and the isolation gaps, straight
  from the board's tracks and filled zones;
- the legend, straight from `F.Silkscreen`;
- where every part sits and which face it is on;
- the 0.08 mm step from copper down to laminate, the depth in the README.

Taken from the photos:

- green mask on the whole bottom face, right up to the WROOM-32; only the solder
  joints and the module itself are bare;
- green screw terminals at J1, J3 and J4, black at J5 and J6;
- blue metal-film resistors (R13 tan), yellow disc capacitors, blue C1, the other
  electrolytics black, green status LED, red power LED, plain TO-220 regulators;
- the DAC modules' purple back with its legend facing up;
- a white XH header at A2, black hex standoffs under and on top of H1 to H4;
- the DIR9001 board stacked over the DAC modules, connectors facing east.

Stand-ins and estimates:

- **DIR9001 board** (`hero_stacked.png` only). Built in `render.py` from the photos,
  scaled against the 73.2 mm carrier: board 64 x 48 x 1.6 mm, underside 17 mm above
  the carrier, south-west hole on the standoff at H3. All of these are estimates.
  TOSLINK socket, toggle switch, RCA jack, DIP switches, chips, capacitor and XH
  connector are plain blocks and cylinders placed by eye. The legend comes from
  `models/make_textures.py`, also drawn by eye; the small parts are part of that
  picture, not geometry. The POWER position is drawn as empty pads, as in the photos.
- **Pigtail.** Six wires on a smooth arc; the real loop is longer and untidy, and the
  colour order is approximate.
- **Standoffs.** 5.5 mm across flats, 10 mm under the board, 8 mm on top: estimates.
  How the DIR9001 board is held at its other three holes is not modelled.
- **PCM5102 modules.** `models/make_pcm5102_module.py` builds them from the footprint's
  own numbers: a 31.0 x 17.1 mm board, the two pin rows, the jack overhang. The parts
  underneath are plain blocks. The legend on the back is redrawn from the photos.
  The socket height is the stock 8.5 mm strip.
- **Mask.** A procedural uneven green coat. The real one has brush marks, splashes and
  smears that are not reproduced.
- **Screw terminals** are a stock Phoenix shape in the real colours, not the exact part.
- **Resistors** have no colour bands.
- **Copper finish.** A clean satin copper with light tarnish.
- **Channels.** Drawn with square walls at the design's 0.5 mm clearance, and dark as
  they look in the photos. The ball mill leaves a round-bottomed groove, measured
  0.44 mm wide.
- **Unfilled zone areas** show as laminate, which is what the KiCad fill says. An
  isolation mill only cuts the outlines, so the real board may keep copper there.
- **Solder.** A small generic fillet under every through-hole lead, and on the top at
  the leads `BUILD-NOTES.md` lists as soldered on both faces. The real joints are
  larger and uneven. The WROOM-32 castellations get a small bead on each edge pad.
- **Leads.** Trimmed to 1.6 mm under the board. The LEDs and C11 use stock models on a
  narrower pitch than their holes, so their legs stop at the top face.
- **Not shown:** wires in the screw terminals, the cable on the POT header, the plug
  and pigtail in the views without the DIR9001 board.

## Files

    render.sh               regenerates everything
    prepare_board.py        design file -> board/ copy with models
    render.py               Blender scene, materials, shots
    board/                  the board copy (generated)
    models/                 DAC module stand-in (FreeCAD script, STEP files) and the
                            legend textures (make_textures.py, PNG)
    build/                  board.glb and previews (ignored by git)
