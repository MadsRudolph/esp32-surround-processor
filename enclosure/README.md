# Enclosure

A printed base that carries everything, closed by a flat lid laser cut from 4 mm clear acrylic and
held by four M3 screws into heat-set inserts in the base. Outside 143 x 117 x 56 mm.

**This is a first version. Nothing has been measured with calipers, printed or test-fitted.**
The carrier board comes from the KiCad file. The DIR9001 module's outline, holes and sockets come
from the seller's dimension drawing. The arrangement of the built unit comes from seven photos with
no ruler in frame. Every other size is assumed or scaled from those photos. See [Assumed dimensions](#assumed-dimensions) and
[MEASUREMENTS.md](MEASUREMENTS.md). A print made before those are filled in is a trial fit. The values most
likely to be wrong are the two standoff lengths (items 1 and 8, which set every height) and the jack
and pot holes (items 17 and 18). All of them are single parameters in `design.py`.

![Closed, front](render/closed-front.webp)
![Closed, rear](render/closed-rear.webp)
![Closed, from above](render/closed-top.webp)
![Open, from above](render/open-top.webp)
![Open, rear](render/open-rear.webp)
![Exploded](render/exploded.webp)
![Cut-away](render/cutaway.webp)

In the renders the green board with the translucent block over it is the DIR9001 module, the
purple blocks are the PCM5102 modules, the blue blocks are the screw terminals and the translucent
grey block behind the LM317 is room kept for a heatsink. They are envelopes, not models of the real parts.
The lid is drawn as clear acrylic.

## Mounting of the DIR9001 module

On the bench the module is stacked over the DAC modules with its TOSLINK socket, toggle and coax
RCA all on one edge, pointing east across the carrier toward the ESP32. No panel can reach them there.

In the enclosure the module stays stacked at the same height, but is **turned 180 degrees and moved
about 40 mm west**, so the socket, the toggle and the RCA jack pass through the rear wall. Mads has
agreed to this. It is the intended mounting, and the base is built round it.

### Re-mounting the module

1. Unplug the pigtail and take the module off its standoff.
2. Fit the carrier in the base (four screws from below into its standoffs).
3. **Wire the west screw terminals J3 to J6 now.** The module covers them afterwards, 9.5 mm above
   their screws, and has to come off again to reach them. J1 (9 V) stays reachable.
4. Leave the standoff on carrier hole **H3** (south-west, next to the 9 V terminal) where it is. It is
   the one the module already stands on. The standoffs on H1, H2 and H4 carry nothing.
5. Turn the module so its sockets point west. Push the TOSLINK, the toggle and the RCA barrel into
   their openings in the rear wall, then lower the module.
6. It now rests on three points:
   - the H3 standoff, under the hole at the module's south-east corner, next to the I2S-OUT end;
   - two printed pillars in the base, 7.5 mm from the carrier's west edge, under the two holes nearest
     the sockets. They stand in the jack bay, 12.5 mm and 68.5 mm north of the board's south edge.

   The fourth hole (north-east) is over bare board and stays empty.
7. Three M3 x 6 screws: two into the pillar inserts, one into the H3 standoff.
8. Plug the pigtail back in.

### Pigtail

I2S-OUT is on the module's east edge after the turn, 20 mm above the carrier. A2 is about 69 mm away
in a straight line (66 mm across, 20 mm down). Allow about 100 mm for a relaxed run that drops off the
module's east edge and crosses the board south of the DAC modules, clear of the USER button cap.

The pigtail's real length has not been measured. In the photos it makes a loop well over the board
that looks longer than 150 mm, so it is very likely long enough, with slack to tuck down beside the
regulators. Confirm with a ruler (item 16 in MEASUREMENTS.md). Where I2S-OUT sits along the module's
edge is scaled from the seller's drawing; the 20 mm height is a photo estimate.

The hole pattern and the socket positions are from the seller's drawing, not yet checked on the real
module. The standoff length on H3, which sets the height of the pillars and of the openings, is still
a photo estimate.

The TOSLINK receiver stands 1.5 mm into its window, and the toggle and the RCA jack sit in shallow
recesses on the outside of the wall, so the lever (5.8 mm proud of the recess floor) and the RCA
barrel (7.4 mm) can be reached. The overhangs behind those numbers are scaled from the drawing.

## Layout

The board keeps its KiCad orientation. "West" and "south" below are the board's own edges.

| Side | What is on it |
|---|---|
| Rear (west wall), upper row | TOSLINK, input toggle, coax RCA: the DIR9001 module's own parts, through openings in the wall. |
| Rear (west wall), lower row | From the north end: front left RCA, front right RCA, surround left TRS, surround right TRS, 9 V jack. Same order as the terminals J3 to J6 and J1 behind them. |
| Front (east wall) | Volume knob at the south end. The WROOM-32 antenna sits behind the plain part of this wall, 43 mm from the pot. |
| Lid (clear acrylic) | The USER button, pin holes over BOOT and RESET, vent slots over the regulators. The status, power and lock LEDs show through the plate. |
| Floor | Vent slots beside the regulators, four screw holes for the carrier's standoffs, two pillars for the module. |

- The carrier has four M3 mounting holes, H1 to H4, and already has hex standoffs under them. The base
  takes four countersunk screws from below into those standoffs. The floor is 1.6 mm thicker under each one.
- The wall in front of the antenna and the floor under it are thinned to 1.2 mm. The nearest metal is the
  board's own H2 screw (12.7 mm) and a lid insert (21.3 mm).
- There are 28 mm between the board's west edge and the rear wall for the jack bodies and the wires to the
  screw terminals, and 29.5 mm south of the board for the 9 V jack, the pot and a heatsink.
- All panel parts are in the base, so the lid comes off without unplugging anything.
- The UART header J2 and the DIP switches on the module are reached with the lid off.
- The uneven gap between the surround left and surround right jacks is where one module pillar stands.

## Printed parts

| Part | File | Size as printed | Orientation | Supports |
|---|---|---|---|---|
| Base | `print/Base.stl` | 143.1 x 116.8 x 52.1 mm | Floor on the bed, open side up | None. The wall openings are round holes up to 10.5 mm, two 16 mm recesses 1.2 mm deep, and one 11.8 mm bridge over the TOSLINK window. |
| User button | `print/User_Button.stl` | 10.5 x 10.5 x 40.0 mm | Skirt on the bed, stem up | None. The inside of the skirt is a 6.6 mm bridge and the collar has a 45 degree underside. Use a brim; it is a 6 mm pin 40 mm tall. |

The STLs are already in these orientations, in millimetres. STEP files of each part are in `cad/`.

Suggested settings, not tried: 0.4 mm nozzle, 0.2 mm layers, 3 perimeters, 20 % infill, PETG or PLA.
PETG if the regulators run warm. Walls and floor are 2.4 mm. The two module pillars are 8 mm
across and 33 mm tall; they are the weakest feature of the base.

### The USER button

The cap is a loose part. Its skirt slips over the body of the 6 mm USER switch, which keeps it centred,
and its stem comes up through a 6.6 mm hole in the acrylic, 1.5 mm proud. A collar on the stem 1 mm under
the plate stops the cap lifting off the switch when the box is turned over. Nothing is attached to the
plate. The skirt assumes an ordinary 6 x 6 mm switch body, 3.5 mm tall (`TACT_BODY`, `TACT_BODY_H`).

BOOT and RESET are 2.2 mm holes in the plate straight above the switches, which are 32 mm further down.
Use a straight 2 mm pin.

## Laser-cut lid

| | |
|---|---|
| Material | Clear acrylic (PMMA), 4 mm. Cast sheet engraves better than extruded. |
| Size | 142.1 x 115.8 mm, corners R3.5. It is 0.5 mm smaller than the base all round. |
| File | `lasercut/Lid_Plate_4mm_acrylic.dxf`, or the `.svg` with the same content. 1:1, millimetres. |
| Laser | CO2. A diode laser does not cut clear acrylic. |

The drawing is seen from above, outside face up. The front of the box is on the right.

| Layer | Colour | Use |
|---|---|---|
| `CUT` | red, hairline | Cut through: outline, four M3 holes (3.4 mm), USER button hole (6.6 mm), BOOT and RESET pin holes (2.2 mm), eight vent slots (3 x 31 mm). |
| `ENGRAVE` | blue, hairline | Engrave: USER, BOOT, RESET and SURROUND 4.0. Single-line strokes, so run it as a low-power line, not as a fill. The labels read from the front of the box. |
| `LED_OPTIONAL` | green | Two 3.2 mm holes over the LEDs. **Not for clear acrylic.** Delete the layer or set it to no output. It is only there in case the lid is ever cut from an opaque sheet. |

Kerf: the cut lines are already compensated for a 0.20 mm kerf, a typical figure for a CO2 laser in
4 mm acrylic. Holes and slots are drawn 0.10 mm smaller per side and the outline 0.10 mm larger. Check
the real kerf with a test cut (a 20 mm square, measured), put it in `LASER_KERF` in `design.py` and
re-run. If the laser software applies its own kerf offset, set `LASER_KERF = 0` instead. Nothing on
this plate is a tight fit, so an uncorrected kerf only costs a tenth or two of clearance.

How it sits: the plate lies on top of the walls and the four corner bosses and is located by its four
screws. It does not drop into a rebate. A rebate would leave a 1.2 mm rim of printed wall round a
sheet whose thickness and cut size both vary by a few tenths, and that rim is the first thing to
break. The price is that the edge of the acrylic is exposed; it is set 0.5 mm inside the base so it
does not catch.

Peel the film after cutting. Do not overtighten: acrylic cracks at the holes. Stop when the screw
head touches, or put a nylon washer under it. Do not countersink.

To engrave on the underside instead, so the lettering is protected, mirror the `ENGRAVE` layer left
to right before cutting and turn the plate over.

## Fitting the inserts

Standard M3 brass heat-set inserts, 4.6 mm outer diameter, 5.7 mm long. Six of them: one in each
corner boss for the lid, one on top of each module pillar. The pockets are 4.2 mm across and 6.7 mm
deep with a 0.6 mm chamfer at the mouth, and each corner boss has 2.4 mm of plastic round the pocket.
If an insert looks different, measure it and change `INSERT_OD`, `INSERT_LEN`, `INSERT_PILOT_D` and
`INSERT_PILOT_DEPTH` before printing.

1. Set the iron to 200 to 230 °C for PLA, 230 to 260 °C for PETG. Use a plain conical or an insert tip.
2. Stand the insert in the chamfer, narrow end down. Rest the tip in it and let its own weight take it down. Do not push hard.
3. Stop when the top is flush with the plastic, or a hair below. On the corner bosses it must not stand proud, or the plate will rock on it.
4. Take the iron out and at once press something flat (a steel rule) on the insert to square it up.
5. Let it cool for a minute before putting a screw in.

Do the two pillars with care: they are slender. Support the pillar with pliers while pressing.

## Hardware

Parts Bin lists no mechanical hardware, so the sources need confirming.

| Item | Qty | Where it goes | Source |
|---|---:|---|---|
| M3 heat-set insert, 4.6 mm OD x 5.7 mm | 6 | 4 corner bosses for the lid, 2 module pillars | home (per Mads) |
| Clear acrylic sheet, 4 mm | 1 piece, 150 x 125 mm or larger | The lid | buy or home: confirm |
| M3 x 10 pan or button head screw | 4 | Lid, through the acrylic into the inserts | buy (assumed) |
| M3 x 8 countersunk screw | 4 | From below into the carrier's standoffs | buy (assumed) |
| M3 x 6 pan head screw | 3 | The module: 2 into the pillars, 1 into the H3 standoff | buy (assumed) |
| Hex standoffs under and on the carrier | as fitted | Already on the board | home (in the photos) |
| Stick-on rubber foot, 3 mm or taller | 4 | Under the base, so the floor vents can breathe | buy (assumed) |

The panel jacks, the pot and the heatsink are in the main parts list in `hardware/BUILD-NOTES.md`.

## Assembly

1. Press the six inserts in (see Fitting the inserts).
2. Fit the jacks, the 9 V jack and the pot in the base.
3. Lower the carrier in, antenna end toward the front wall, and fit four screws from below into its standoffs.
4. Wire the terminals and plug in the pot.
5. Fit the module as described under Re-mounting the module. Plug in the pigtail.
6. Slip the user button over the USER switch. Lower the acrylic plate over its stem and fit four M3 x 10 screws.

## Assumed dimensions

None of these has been measured on the real parts. They are all in the block marked `NOT FROM KICAD`
at the top of `design.py`. "Photo" means scaled from a photo against the board outline. "Listing" means
a reseller's page for the same-named module.

| Parameter | Value | What it is |
|---|---:|---|
| `BOARD_T` | 1.6 | Board thickness |
| `CARRIER_STANDOFF_LEN`, `CARRIER_STANDOFF_AF` | 10, 5.5 | Standoffs under the carrier (photo). Sets the floor height. |
| `LEAD_TRIM` | 2.5 | Longest lead under the board |
| `HS_TOP_ABOVE_BOARD`, `HS_W`, `HS_D`, `HS_BOTTOM_ABOVE_BOARD` | 26, 22, 14, 3 | Room for an LM317 heatsink. None is fitted in the photos. |
| `DAC_TOP_ABOVE_BOARD` | 14.0 | PCM5102 modules on their sockets |
| `TERMINAL_H` | 10.5 | Screw terminals |
| `CAP_C1_H`, `CAP_SMALL_H` | 16, 12 | Electrolytic cans |
| `LED_TOP_ABOVE_BOARD` | 6.0 | LED domes; drawn only |
| `TACT_TOP_ABOVE_BOARD`, `TACT_BODY`, `TACT_BODY_H` | 4.3, 6.2, 3.5 | Switch plunger height and body; set the user button's length and skirt |
| `DIR_ABOVE_BOARD` | 20 | Underside of the module above the carrier (photo): the standoff on H3 |
| `DIR_COMP_H` | 12.9 | Tallest part on the module (listing: 14.5 overall). With `DIR_ABOVE_BOARD` it sets the height of the box. |
| `DIR_STANDOFF_AF` | 5.5 | Standoff across flats |
| `RCA_HOLE_D` | 6.4 | Output RCA jack hole |
| `TRS_HOLE_D` | 9.5 | TRS jack hole, for 6.35 mm jacks. Use 6.2 for 3.5 mm jacks. |
| `DC_HOLE_D` | 8.2 | 9 V jack hole |
| `POT_HOLE_D`, `POT_TAB` | 7.2, none | Pot bushing hole and anti-rotation tab |
| `JACK_PITCH`, `JACK_BODY_D`, `JACK_BODY_DEPTH` | 15.5, 15, 22 | Jack spacing and the room each needs behind the panel |
| `DC_BODY_D`, `DC_BODY_DEPTH` | 11, 14 | 9 V jack body |
| `POT_BODY_D`, `POT_BODY_DEPTH`, `POT_SHAFT_D`, `POT_SHAFT_LEN`, `KNOB_D`, `KNOB_H` | 17, 11, 6, 15, 20, 14 | Pot and knob |
| `CSK_D`, `CSK_H` | 6.5, 1.7 | Countersink for the floor screws |
| `LASER_KERF` | 0.20 | Typical CO2 kerf in 4 mm acrylic, to be checked with a test cut |

From the seller's dimension drawing of the DIR9001 module, not yet checked on the real one:

| Parameter | Value | What it is |
|---|---:|---|
| `DIR_W`, `DIR_L`, `DIR_T` | 64, 48, 1.6 | Board; the sockets are on a 64 mm edge |
| `DIR_HOLE_PITCH_W`, `DIR_HOLE_PITCH_L`, `DIR_HOLE_FROM_EDGE` | 56, 24.5, 19.5 | Holes: 4 mm in from each end, rows 4 and 28.5 mm from the I2S-OUT edge |
| `DIR_TOGGLE_U`, `DIR_RCA_U` | +23, +23 | TOSLINK to toggle to RCA, centre to centre |
| `DIR_OPT_BODY_W`, `DIR_OPT_BODY_H`, `DIR_OPT_ZC` | 10.8, 10.8, 5.6 | TOSLINK body and optical axis above the board. The drawing's "0.56 cm" is read as the axis height. |
| `DIR_TOGGLE_BUSH_D`, `DIR_TOGGLE_ZC` | 5.5, 3.0 | Toggle bushing and axis height |
| `DIR_RCA_BARREL_D`, `DIR_RCA_ZC` | 9.0, 6.3 | RCA barrel and centre height |

Scaled from the same drawing, because it gives no number: TOSLINK centre 9 mm from its end of the
board, which puts the toggle on the middle of the edge (`DIR_OPT_U`); TOSLINK front 2.5 mm past the
board edge, toggle bushing 2.5 mm, lever tip 8 mm, RCA barrel 9.6 mm (`DIR_OPT_OVERHANG`,
`DIR_TOGGLE_BUSH_OVERHANG`, `DIR_TOGGLE_TIP_OVERHANG`, `DIR_CONN_OVERHANG`); I2S-OUT centre 33 mm from
the TOSLINK end (`DIR_I2S_U`).

Taken from the KiCad board, not assumed: the board outline (101.88 x 73.25 mm), the four M3 holes, the
positions of the LEDs, switches, regulators, terminals and modules, and the antenna overhang (5.95 mm).

Seen in the photos, not assumed: the module is stacked over the west half of the carrier; TOSLINK,
toggle and RCA are on one edge of it and I2S-OUT on the opposite edge; the carrier has hex standoffs
under all four holes; no heatsink is fitted.

## Checks

`validate.py` intersects the printed parts and the acrylic plate with the STEP export of the board and with the envelopes,
and the envelopes with each other. Result for this version: no interference in 1086 pairs. Clearances
and wiring room are in `cad/validation.json`. Tightest: 0.5 mm between the assumed jack bodies and the
module pillars, 2 mm between the module's assumed top and the acrylic plate, 0.3 mm radial play of the
button stem in its hole. The tallest part on the carrier is 10.5 mm under the plate. The vent slots are
18 mm clear of the module and 9.5 mm inside the south wall; the highest thing under them is the heatsink
allowance, 10.5 mm down.

What that does and does not show: the model is consistent with itself and with the KiCad board. It does
not show that the real parts fit, because the module, standoff and jack sizes are assumed. The KiCad
library on this machine has no 3D model for the screw terminals or C11, and the PCM5102 modules and LEDs
have none in the board file, so those are envelopes too. Wires are not modelled.

## Rebuilding

Run from the repository root with the system Python (FreeCAD 1.1 libraries in `/usr/lib/freecad/lib`,
Blender 5.2 for the renders):

```sh
python3 enclosure/board_export.py     # only after the board changed: cad/board.step, cad/board_data.json
python3 enclosure/design.py           # cad/*.step, cad/surround_enclosure.FCStd, print/*.stl, lasercut/*
python3 enclosure/validate.py         # cad/validation.json
python3 enclosure/render_preview.py   # render/*.png
```

`board_export.py` copies the board to a temporary folder before opening it, so it never writes in `hardware/`.

| File | What |
|---|---|
| `design.py` | The model. Parameters at the top, the assumed ones in their own block. |
| `lasercut.py` | Writes the DXF and SVG of the lid from the plate geometry in `design.py`. |
| `board_export.py` | Board outline, holes and part positions from KiCad, and the STEP export. |
| `validate.py` | Interference and clearance checks. |
| `render_preview.py` | Preview renders. |
| `MEASUREMENTS.md` | The measurements and photos needed to finish the design. |
| `cad/` | STEP per part, the assembly STEP, the FreeCAD document, the board STEP and data, the check reports. |
| `print/` | STL per printed part, in print orientation. |
| `lasercut/` | The lid as DXF and SVG. |
| `render/` | Preview renders. |
