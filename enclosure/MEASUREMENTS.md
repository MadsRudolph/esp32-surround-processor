# Measurements for the enclosure

Everything is in millimetres. Each value is a named parameter near the top of `design.py`, marked
MEASURED, seller drawing, or ASSUMED. Heights on the carrier are above its top face.

## Still open

Measure or decide these, in this order of importance.

- **11b. Toggle position on the module.** You measured the TOSLINK centre 6 from the nearer board end. With the drawing's 23.0 spacings that puts the toggle axis 29 from that end and the coax centre 52. The drawing's proportions say 9, 32 and 55, with the toggle on the middle of the 64 mm edge. One number settles it: **the distance from the TOSLINK end of the board to the toggle lever's axis** (29, or 32?). The three openings in the rear wall move together with it. **Check this before printing the base.**
- **18. Potentiometer, what is left:** the length of the 7 mm collar, whether the 8 mm shaft length is measured from the end of the collar or from the body, the height of the two small bosses on the front face, and a caliper check of the frame (9.8 x 11.3 from the photo). Print `Pot_Fit_Test` and `Pot_Cradle` to check the fit before the whole base. (assumed: collar 2.0, 8 measured from the collar, bosses 0.5)
- **17c. DC jack** (not in hand): thread diameter and nut size. The base has an 8.0 mm hole that can be opened up to 12 mm.
- **22. Kerf of the laser in the acrylic**: cut a 20 mm square and measure it. (assumed 0.20; the cut file is drawn for that)
- **23. Real thickness of the acrylic sheet.** It only changes how far the button stands proud. (assumed 4.0)

Small things still assumed, none of them likely to matter: the RCA nut (12.6 across corners) and its
depth behind the panel (15), the square body of the USER switch (6.2 wide, 3.5 tall), the smaller electrolytic cans (12), the longest lead under the board (2.5), hole diameter in
the module (M3).

## Measured by Mads

- [x] **1.** Standoffs under the carrier: **10**, M3 female at the bottom.
- [x] **2.** Tallest part on the carrier: **24**, the L7805.
- [x] **3.** Top of the PCM5102 modules: **8**.
- [x] **4.** USER button plunger top, unpressed: **4**.
- [x] **5.** LED tops: **6**.
- [x] **6.** Screw terminals **10**, blue 470 uF can **14**.
- [x] **7.** Board thickness: **1.6**.
- [x] **8.** Carrier top face to the underside of the module (the standoff on H3): **22**.
- [x] **11.** TOSLINK: centre **6** from the nearer board end, front **2.5** past the board edge. See 11b above.
- [x] **12.** Toggle: bushing **2** past the board edge, lever tip **8**.
- [x] **13.** Coax RCA barrel: **8** past the board edge.
- [x] **15.** Tallest part on the module above its top face: **12**.
- [x] **16.** Pigtail: over **100**, long enough (the layout needs about 70 in a straight line).
- [x] **17a.** RCA jacks: thread about **7**, white washer about **15** outer diameter. Four of them; there are no TRS jacks.
- [x] **18 (photo and partly measured).** Pot: no thread, collar **7**, D-shaft **6** diameter, **8** long, body **6** deep (calipers). From the photo against a ruler, good to about 0.5: frame **9.8** across the pins' direction and **11.3** along it, shaft axis about **6.6** from the pin edge, three pins on one side at 2.5 pitch reaching about **7** with their solder joints.
- [x] **19.** No heatsink on the LM317. The allowance for one is removed.

## From the seller's dimension drawing of the module

- [x] **9.** Bare board: **64.0 x 48.0, 1.6 thick**, sockets on a 64 mm edge.
- [x] **10.** Mounting holes: **56.0 x 24.5**, 4.0 in from each end, rows 4.0 and 28.5 from the I2S-OUT edge (19.5 from the socket edge).
- [x] **14.** TOSLINK optical axis above the module's top face: **5.6**. Body 10.8 x 10.8.
- [x] TOSLINK to toggle **23.0**, toggle to coax **23.0**; toggle bushing **5.5** diameter, axis **3.0** above the top face; coax barrel **9.0** diameter, centre **6.3** above the top face.

## Settled by Mads

- [x] The module is turned 180 degrees and moved west, sockets through the rear wall, standing on the H3 standoff.
- [x] **20.** Inserts: standard M3 brass heat-set, 4.6 outer diameter x 5.7 long.
- [x] **21.** Lid: clear acrylic, 4 mm, CO2 laser.

## From seller pictures of the panel parts

- RCA jack: panel up to 2 mm thick, 28.6 long overall, 8.26 barrel. Its "12 mm fixing hole" is for the shouldered washers, which are not used.
- DC jack: 5.5 x 2.1 mm, 2-pin panel socket, 18.2 long overall. Thread not given.
