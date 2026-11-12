# Measurements needed for the enclosure

Everything here is in millimetres. Calipers where possible, a ruler is fine for anything over 30 mm.
The value in brackets is what the model assumes until you answer. Each one is a named
parameter in the ASSUMED block of `design.py`. "Photo" means the value was scaled from the
photos of 12 November, which had no ruler in frame, so it is only good to a few millimetres.

## Settled

The DIR9001 module is turned 180 degrees and moved about 40 mm west, sockets through the rear wall,
still standing on the H3 standoff. The questions below are for that arrangement.

## Board and the parts on it

1. **Length of the four black hex standoffs under the carrier**, and their thread (M3 female at the bottom?). The floor screws go up into them. (assumed 10, M3, photo)
2. **Height of the tallest part on the carrier above its top face**, and which part it is. Ruler flat across its top, measure down. (the TO-220s, 18.9 in the KiCad model; no heatsink is fitted in the photos)
3. **Height of the plugged-in PCM5102 modules above the top face**, to their highest point. (assumed 14)
4. **Height of the USER button's plunger top above the top face**, not pressed, and the width and height of its square body. Are BOOT and RESET the same type? (assumed 4.3; body 6.2 x 6.2, 3.5 tall)
5. No longer needed: the LEDs show through the clear lid.
6. **Height of the screw terminals and of the blue 470 uF can above the top face.** (assumed 10.5 and 16)
7. **Board thickness.** (assumed 1.6)

## DIR9001 module

Answered by the seller's dimension drawing (worth one caliper check each when the module is off):

- [x] **9.** Bare board: **64.0 x 48.0, 1.6 thick**, sockets on a 64 mm edge.
- [x] **10.** Mounting holes: **56.0 x 24.5**, 4.0 in from each end, rows 4.0 and 28.5 from the I2S-OUT edge (19.5 from the socket edge). Hole diameter is not on the drawing; M3 assumed.
- [x] **14.** Height of the TOSLINK's optical axis above the module's top face: **5.6** (the drawing's "0.56 cm", read as the axis height). Body 10.8 x 10.8.
- [x] **11, 12, 13 in part:** TOSLINK to toggle **23.0**, toggle to RCA **23.0**; toggle bushing **5.5** diameter, axis **3.0** above the top face; RCA barrel **9.0** diameter, centre **6.3** above the top face.

Still open:

- **8.** **Length of the standoff on top of H3 that carries the module**, which is the gap between the carrier's top face and the underside of the module. (assumed 20, photo)
- **11.** **TOSLINK: distance from the nearer end of the board to the centre of the socket, and how far its front sits past the board edge.** The drawing gives neither. (9.0 and 2.5, scaled from the drawing)
- **12.** **Toggle: how far the bushing and the lever tip reach past the board edge.** (2.5 and 8.0, scaled from the drawing)
- **13.** **Coax RCA: how far the barrel reaches past the board edge.** (9.6, scaled from the drawing)
- **15.** **Tallest part on the module above its top face**, and how far the longest solder joint sticks out underneath. (assumed 12.9 above, from a listing's 14.5 overall)
- **16.** **Length of the pigtail between its two XH plugs.** The layout needs about 70 mm in a straight line, 100 mm for a relaxed run; the one in the photos looks much longer, which is fine.

## Panel jacks and pot

17. **RCA jacks, TRS jacks and the DC jack, each: thread diameter (the hole it needs), the widest diameter of the nut or flange, and how deep the body and solder lugs go behind the panel.** Are the TRS jacks 6.35 or 3.5 mm? Part numbers will do if they are not to hand. (assumed holes 6.4, 9.5 and 8.2; bodies up to 15 wide and 22 deep)
18. **Potentiometer: bushing thread diameter and length, body diameter and depth behind the panel, shaft diameter and length, and the anti-rotation tab (distance from the shaft centre, width), if it has one.** Also the knob diameter. (assumed M7 bushing in a 7.2 hole, 17 x 11 body, 6 mm shaft, tab snapped off, 20 mm knob)

## Heatsink

19. **Will the LM317 get a heatsink?** If so: width along the board edge, depth out from the tab, and how far its top is above the top face of the board. (assumed 22 wide, 14 deep, top at 26, hanging over the south edge)

## Fasteners and lid

Settled:

- [x] **20.** Inserts: the standard M3 brass heat-set insert, 4.6 mm outer diameter x 5.7 mm long, per Mads. Measure one before printing if it looks different.
- [x] **21.** Lid: clear acrylic, 4 mm, cut on a CO2 laser, per Mads. (A diode laser cannot cut clear acrylic.)

Still open:

- **22.** **Kerf of the laser in this acrylic**: cut a 20 mm square and measure it. (assumed 0.20; the cut file is drawn for that)
- **23.** **Real thickness of the acrylic sheet.** It only changes how far the button stands proud. (assumed 4.0)

## Photos that would still help

The first set shows the layout well. What is missing is scale and square-on views.
Put a ruler or the calipers in the frame and shoot square-on.

- The whole stack straight from the south edge and straight from the west edge, at board level, so the heights can be read off.
- The DIR9001 module on its own, straight from above, with a ruler along the socket edge.
- The DIR9001 module straight at the socket edge, with a ruler standing next to it.
- Each panel part (RCA, TRS, DC jack, pot, knob) from the side next to a ruler.
