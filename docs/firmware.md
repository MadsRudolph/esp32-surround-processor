# Firmware

ESP-IDF v5.5, in `firmware/`. Three projects share the components in `firmware/components/`.
Paths in backticks are relative to the repository root, and commands are run from there.
Back to the [README](../README.md).

| Path | What |
|---|---|
| `firmware/surround/` | **The firmware.** Dolby Digital 5.1 and stereo matrix decoding to four outputs. |
| `firmware/passthrough/` | Bring-up: the DIR9001's stereo straight to both DACs. |
| `firmware/boardtest/` | Bring-up without the DIR9001: the ESP32 makes the clocks and plays a 1 kHz tone on one output at a time. |
| `firmware/components/netota/` | Wi-Fi, over-the-air update with rollback, `/status` and `/set` over HTTP. |
| `firmware/components/dolby/` | Finds IEC 61937 bursts in the S/PDIF data and maps decoded 5.1 to four speakers. Plain C, also built on a PC by `tools/dolby_test.sh`. |
| `firmware/components/liba52/` | liba52 0.7.4, the AC-3 decoder. **GPL-2.0-or-later** (see `COPYING` there), so firmware built with it is GPL. One change from the original, noted in its `CMakeLists.txt`. |
| `firmware/components/esp_driver_i2s/` | ESP-IDF's I2S driver with one fix (below). Overrides the IDF copy. |

What `firmware/surround` does:

- **Dolby Digital (AC-3) bitstream:** decoded on the ESP32. Centre is folded into the fronts, the
  LFE channel is added to both fronts (the subwoofer is fed from them), surround left and right go
  straight to the rear outputs. About 5 ms of decode per 32 ms frame at 240 MHz.
- **Stereo PCM:** fronts untouched; rear = 0.5 x (L - R), high-pass 100 Hz, low-pass 7 kHz, 20 ms
  delay, the same signal to both rears.
- **DTS, Dolby Digital Plus:** recognised and kept silent.
- Volume on the pot (J7), mute on USER, mode on BOOT. It starts muted.

```bash
cp firmware/wifi_secrets.h.example firmware/wifi_secrets.h   # then fill it in; it is not in git
. ~/esp/esp-idf/export.sh
idf.py -C firmware/surround build
tools/ota.sh surround            # build and flash over Wi-Fi (the first flash goes over J2)
tools/dolby_test.sh film.mkv     # run the parser and decoder on a PC against any AC-3 track
```

Two faults found during bring-up, both heard as loud clicks:

- **Data lines driven too hard.** At the ESP32's default drive strength the two I2S data outputs
  disturbed the shared clock lines whenever both switched together, and the DACs misread bits.
  The firmware sets `GPIO_DRIVE_CAP_0` on both; clicks start at `CAP_2` and are severe at `CAP_3`.
- **A lost-interrupt bug in ESP-IDF's I2S driver** (v5.5, classic ESP32, full duplex): the RX and
  TX handlers share one interrupt and each cleared every pending flag, so one erased the other's
  event and a 5 ms buffer went missing. Fixed in `firmware/components/esp_driver_i2s`.

And one in liba52: its FFT kept temporaries in `double`, which the ESP32 computes in software. As
`float` the decode time fell from 21 ms to under 5 ms per frame.

The debug page (`tools/debug_page.html`, served by the bench server at `/debug`) shows the input
format, levels and decoder health live, and has a per-speaker test (chime or sine sweep).
See [bench.md](bench.md) for the bench server.
