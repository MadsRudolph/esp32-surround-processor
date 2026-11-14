# ESP32 surround processor

A four-speaker surround processor built around an ESP32. It takes the optical output of a TV, decodes Dolby Digital 5.1 in firmware, and drives two DACs: a front pair and a rear pair.

![The surround processor: a bare-copper milled board with two DAC modules, and the green optical receiver module stacked on top with its six-wire pigtail](docs/img/render-hero_stacked.webp)

![Block diagram: TV optical output into a DIR9001 receiver, data into the ESP32, two PCM5102 DACs for the front and rear pairs, with the receiver's clocks going to the ESP32 and both DACs](docs/img/signal-chain.svg)

The receiver recovers the clocks from the optical signal and everything else follows them. The ESP32 is a slave on both of its I2S ports.

## What it does

- Dolby Digital 5.1 from the TV is decoded on the ESP32 and played on four speakers.
- Plain stereo goes to the fronts untouched, and the rears get a stereo matrix signal.
- DTS and Dolby Digital Plus are recognised and kept silent.
- A potentiometer sets the volume, and the board updates over Wi-Fi.

## The board

The board is 101.9 x 73.2 mm with copper on both faces, milled on a desktop CNC. The holes are not plated and there are no vias: the two faces meet only at 19 component leads soldered on both sides. The top face is a ground plane, and every clock, data and audio signal stays on the bottom. The layout is written as code, and a separate check proves the board is connected with bare holes, which KiCad's own rule check cannot do.

![Top face of the board in a three-quarter view: bare copper ground plane, DAC modules, regulators and screw terminals](docs/img/render-top_34.webp)

![Bottom face of the board: green solder mask over the signal routing, the ESP32 module and four standoffs](docs/img/render-bottom_34.webp)

The pictures are renders made from the KiCad board file in Blender. The copper, the isolation channels, the legend and the part positions are the real design; the DAC and receiver modules are simplified stand-ins. The flat layer plots are in [docs/board.md](docs/board.md).

## Enclosure

![The enclosure closed: a dark printed base with the volume knob on the front and a clear acrylic lid showing the board](docs/img/enclosure-closed-front.webp)

A printed base with a laser-cut lid in 4 mm clear acrylic, held by M3 screws in heat-set inserts. The optical input, the coax input, four RCA outputs and the 9 V jack are on the rear panel, the volume knob on the front. The model uses caliper measurements of the real board and is collision-checked. The base is printed in PLA with a fuzzy-skin finish, and the box is assembled and tested (below). The files and the list of what is still assumed are in `enclosure/`.

![Rear panel: coax, input toggle and optical above, four RCA outputs and the 9 V jack below](docs/img/enclosure-closed-rear.webp)

## Measured

| | Result |
|---|---|
| Decode time | 5.3 ms average per 32 ms frame, with a film playing |
| Damaged frames | 0 in 48,044 |
| Channel separation | each channel on its own output, the others below -108 dBFS |
| Line outputs | 0.50 to 0.52 V rms at 1 kHz, -12 dBFS |
| Supply rails | 4.98 V and 3.21 V |

## Tested in the box

The finished box on its 9 V adapter, fed S/PDIF from an Analog Discovery 3 into the coax input (`tools/spdif_gen.py`), with the AD3's scope on the RCA outputs. The receiver locks in 2 to 3 s and the ESP32 reads exactly the −12.0 dBFS that is sent.

![Rear outputs in surround mode: with left and inverted right both rears give about 0.49 V rms, with left equal to right they are silent at 2 mV, and with left only they give half, about 0.245 V](docs/img/box-rear-matrix.svg)

The rear matrix does what it should: half of left minus right on both rears, so a sound that is the same in both channels cancels by more than 47 dB and one that is in antiphase comes out at full level.

![Line output level of the four outputs: 0.514, 0.501, 0.518 and 0.503 V rms on the bench, 0.484, 0.456, 0.488 and 0.458 V rms in the finished box](docs/img/box-output-levels.svg)

Every output carries its own channel at 0.46 to 0.49 V rms. That is 0.5 to 0.8 dB under the bench values, which were taken with a different signal source and different leads, so I read little into it. The right channel of each DAC is the lower one on both runs. The volume pot, mute (USER) and the mode button (BOOT) all work through the printed panel. The data and the plot script are `hardware/bench/box-test-2026-11-14.json` and `tools/plot_box_test.py`.

## What went wrong

- In the closed box on a 12 V adapter the LM317 that makes the 3.3 V got too hot, its output sagged, and the ESP32 reset from brown-out every second or so. On the 9 V adapter it is designed for, it runs without a reset. Feeding the LM317 from the 5 V rail would cut its heat by about 70 % and make a 12 V adapter safe.
- The vendor's I2S driver lost a 5 ms buffer now and then, because two interrupt handlers cleared each other's flags. A patched copy of the driver fixes it.
- The ESP32 drove its two data lines hard enough to disturb the clock lines beside them, and the DACs misread bits. The weakest drive setting is clean.
- The Dolby Digital decoder kept its FFT temporaries in doubles, and the ESP32 has no hardware for those. Single precision took the decode from 21 ms to about 5 ms per frame.

The full story is on the [project page](https://madsrudolph.dev/projects/esp32-surround-processor).

## Debug page

![The board's debug page while a film plays: Dolby Digital 3/2.1 detected, volume, a per-speaker test panel and level meters](docs/img/debug-page.webp)

The board's debug page while a film plays. It shows the input format, levels and decoder health, and can play a chime or a sine sweep on one speaker at a time.

## More

- [docs/board.md](docs/board.md): file layout, rebuilding, fabrication rules, routing rules and the board concept
- [docs/firmware.md](docs/firmware.md): the firmware projects, build commands and the faults in detail
- [docs/bench.md](docs/bench.md): the bring-up page and the Analog Discovery 3
- [hardware/BUILD-NOTES.md](hardware/BUILD-NOTES.md): milling order, assembly order and module straps

## Status

The board is cut, soldered and working, and the firmware has been tested with a TV on four speakers. The enclosure is printed, assembled and tested with the AD3; the optical input with a TV in the box is next. The mute pin on the DAC modules does not mute, so mute is done in the audio data. Writing my own AC-3 decoder in place of liba52 is the next step.

## Licence

Copyright (C) 2026 Mads Rudolph. The firmware, the tools and the hardware design files
are free software under the **GNU General Public License, version 3 or (at your option)
any later version**; see `LICENSE`. They come with no warranty.

Two parts are other people's work and keep their own licences:

- `firmware/components/liba52/`: liba52 from a52dec 0.7.4, (C) Aaron Holtzman and Michel
  Lespinasse, GPL version 2 or later (`COPYING` in that folder). One file is changed, with a
  notice at its top.
- `firmware/components/esp_driver_i2s/`: the I2S driver from ESP-IDF v5.5, (C) Espressif
  Systems, Apache License 2.0 (`LICENSE` in that folder). One file is changed, with a notice
  at its top.

The firmware links both with ESP-IDF (Apache 2.0), which is why the whole is GPL version 3:
that is the GPL version compatible with the Apache licence.

"Dolby" and "Dolby Digital" are trademarks of Dolby Laboratories. This project is not made,
tested or endorsed by Dolby.
