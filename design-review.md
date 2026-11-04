# ESP32 4.0 Surround Processor: Design Review

Sources checked: TI DIR9001 datasheet SLES198A (rev. May 2015), TI PCM510xA datasheet SLAS859C (rev. May 2015), ESP-IDF v5.3 `esp_driver_i2s` source and I2S API docs.

## 1. Verdict: what to change before you build

The architecture is sound in outline. Five things in the proposal are wrong or would have cost you a board spin:

1. **The ESP32 must be an I2S slave on both ports. It never becomes clock master.** The DIR9001 recovered clock is the only clock in the system. Both I2S0 (RX+TX, full duplex) and I2S1 (TX) run in slave role on the same external BCLK/WS. The APLL is not used at all. Details in section 2.
2. **DIR9001 strap for I2S is FMT1 = H, FMT0 = H.** Datasheet Table 13: LL = 16-bit right-justified, LH = 24-bit right-justified, HL = 24-bit left-justified, HH = 24-bit I2S. Many breakouts ship strapped LL. BCKO is always 64 fs, so use 32-bit slots on the ESP32 and treat DOUT as 24-bit left-aligned in a 32-bit word.
3. **FSOUT0/1 are useless without a 24.576 MHz crystal on XTI.** The sample-rate calculator uses XTI as its reference. Drop those pins and measure fs in firmware by counting frames per second. Also keep CKSEL = L and XTI = DGND; do not use the AUTO/XTI mode, because on unlock it switches BCKO to 6.144 MHz (96 kHz), which is exactly where ESP32 slave-TX timing becomes marginal.
4. **Tie PCM5102A SCK to ground on both boards (3-wire mode).** Do not route SCKO. Reasoning in section 2.
5. **The 30 ms lip-sync figure is the wrong target.** The PCM path lands around 9 ms. The AC-3 path cannot beat about 45 ms because one AC-3 frame is 1536 samples = 32 ms and must be complete before decoding starts. Every AV receiver has the same floor. ITU-R BT.1359 puts the detectability threshold for late audio at about 125 ms, so set the budget at PCM ≤ 15 ms and AC-3 ≤ 60 ms and stop worrying.

Smaller corrections: the (L−R) matrix gives one mono surround signal to both SL and SR, which is what Dolby Surround did; accept that or decorrelate. Arduino audio libraries are the wrong tool here (section 5). Add a high-pass around 100 Hz for the Eris 3.5.

## 2. Deliverable 1: clock domain and I2S feasibility

### 2.1 Clock tree

```
TOSLINK ─► TORX ─► DIR9001 PLL ─┬─► BCKO  = 64 fs  (3.072 MHz @ 48 k, 2.8224 MHz @ 44.1 k)
                                ├─► LRCKO = fs
                                ├─► DOUT  (24-bit, I2S, changes ≤ 5 ns after BCKO falling edge)
                                └─► SCKO  (unused, leave PSCK[1:0] = LL → 128 fs, lowest EMI)

BCKO ──┬─► ESP32 GPIO32 ──► I2S0 BCLK-in  and  I2S1 BCLK-in  (two matrix routes, one pad)
       ├─► DAC1 BCK
       └─► DAC2 BCK
LRCKO ─┬─► ESP32 GPIO35 ──► I2S0 WS-in and I2S1 WS-in
       ├─► DAC1 LRCK
       └─► DAC2 LRCK
DOUT ───► ESP32 GPIO34 ──► I2S0 DIN
ESP32 GPIO19 (I2S0 DOUT) ──► DAC1 DIN
ESP32 GPIO23 (I2S1 DOUT) ──► DAC2 DIN
```

### 2.2 Can I2S0 slave-RX, I2S0 TX and I2S1 TX all run from the recovered clock? Yes.

- **I2S0 full duplex, slave role.** Allocate TX and RX in one `i2s_new_channel()` call with `I2S_ROLE_SLAVE`. The driver then sets the ESP32's `I2S_SIG_LOOPBACK` bit (`i2s_ll_share_bck_ws`), which makes the TX and RX shift registers share one BCLK and one WS. In slave role both are GPIO inputs. DAC1 therefore gets its BCK/LRCK directly from the DIR9001 net, and the ESP32 only supplies DIN.
- **I2S1 TX, slave role, same pads.** In v5.3 `i2s_gpio_check_and_set()` calls `gpio_set_direction(INPUT)` plus `esp_rom_gpio_connect_in_signal()` for inputs and only calls `i2s_output_gpio_reserve()` for outputs. One GPIO pad can feed any number of peripheral input signals through the GPIO matrix, so `.bclk = 32, .ws = 35` on both ports is legal. GPIO 16/17 are reserved in the pinout as a second physical tap in case a future IDF release starts reserving input pins.
- **Input-only GPIOs are legal for BCLK, WS and DIN in slave role** for the same reason: the driver only ever configures them as inputs.
- **The internal I2S clock still runs in slave mode, but it does not matter.** `i2s_std_calculate_clock()` forces `bclk_div = 8` and `mclk = 8 × bclk` (24.576 MHz at 48 kHz) from the 160 MHz PLL_D2. That clock only oversamples the external BCLK for the slave logic. Its accuracy is irrelevant, no APLL is needed, and a 44.1 kHz stream is followed without any reconfiguration. Set `sample_rate_hz = 48000` as the nominal value.
- **DAC1/DAC2 sample alignment.** Both TX units shift on the same BCLK edges and frame on the same WS. Their DMA engines start independently, so the static offset between DIN1 and DIN2 is 0 or 1 frame (20.8 µs). Make it deterministic: preload both TX channels with the same number of zero frames, then enable tx1, tx0, rx0 back to back with interrupts disabled. Check on a scope. A 1-frame offset is invisible next to the 20–30 ms Haas delay and can be absorbed into the delay-line length.

### 2.3 The one real timing risk: slave-TX clock-to-output delay

In slave role the ESP32 launches DIN on the BCLK falling edge, but that edge is first resynchronised inside the I2S block at 8 × BCLK. Estimated launch delay: pad + GPIO matrix in (~15 ns) + 1–2 periods of 24.576 MHz (41–81 ns) + matrix out + pad (~15 ns) = roughly 70–110 ns.

| fs | BCLK | Half period | DAC setup margin (163 ns − 110 ns) |
|---|---|---|---|
| 44.1 kHz | 2.8224 MHz | 177 ns | ~65 ns |
| 48 kHz | 3.072 MHz | 163 ns | ~50 ns |
| 96 kHz | 6.144 MHz | 81 ns | negative, fails |

The PCM5102A samples DIN on the BCLK rising edge and needs setup and hold in the ~10 ns class. 48 kHz is fine, 96 kHz is not, which is why 96 kHz clocks must never reach the bus (see the CKSEL note above). Verify with a scope at the DAC end, BCLK on channel 1, DIN on channel 2. If setup is under 20 ns, the escape hatch is a 74LVC1G79 flip-flop retiming DIN with inverted BCLK. Do not use the driver's `bclk_inv` flag: WS is sampled relative to the same clock and would move by half a bit.

### 2.4 Why ESP32-as-master with APLL is a dead end

An APLL at 12.288 MHz is free-running against the TV's crystal. At ±100 ppm the drift is 4.8 samples/s, so a 512-sample buffer slack is consumed in about 106 s and then you get a click. Fixing that needs either an asynchronous sample-rate converter in software (20–40 MHz of CPU, added latency) or a servo loop trimming the APLL fractional divider from buffer fill. The APLL step with `sdm0` is 40 MHz / 65536 / 32 ≈ 19 Hz at 12.288 MHz, or 1.5 ppm, so the servo is possible, but it is a project in itself and gains nothing. Slave mode is bit-exact and free.

### 2.5 PCM5102A: external SCK or BCK-PLL? Ground SCK.

- The datasheet's 3-wire mode: the device starts up expecting SCK; if BCK and LRCK are running while SCK stays at ground for 16 LRCK periods, the internal PLL starts and synthesises SCK from BCK. Table 11 lists 64 fs BCK at 32/44.1/48 kHz as supported.
- The 4-wire alternative needs SCKO at ≥ 128 fs (12.288 MHz at 256 fs) fanned out over jumper wires to two boards. With 2–3 ns edges the critical length is about 7 cm, so every wire becomes a transmission line, and the 12 MHz square wave couples straight into the analog outputs.
- Jitter: the DIR9001 SCKO is specified at 50 ps rms typical. The PCM5102A's own PLL adds filtering of the BCK jitter. TI characterises the part with 512 fs SCK but publishes no penalty for PLL mode, and this is how nearly every PCM5102A board in existence is run.
- Unlock behaviour with CKSEL = L and XTI = GND: BCKO/LRCKO keep running from the free-running VCO at a wandering but 64:1-consistent ratio, and DOUT is muted low. The DAC PLL follows, so there is no clock-halt event and no pop. ERROR goes high, and firmware pulls XSMT low.

## 3. Deliverable 2: ESP-WROOM-32 pinout

| Net | GPIO | Pin row | Peripheral | Notes |
|---|---|---|---|---|
| DIR_AUDIO | 36 (SENSOR_VP) | upper | GPIO poll | non-PCM flag, active high |
| DIR_ERROR | 39 (SENSOR_VN) | upper | GPIO ISR, any edge | firmware debounces 5 ms |
| DIR_DOUT | 34 | upper | I2S0 din | input-only pin |
| DIR_LRCK | 35 | upper | I2S0 ws + I2S1 ws | input-only pin |
| DIR_BCK | 32 | upper | I2S0 bclk + I2S1 bclk | |
| XSMT (both DACs) | 21 | lower | GPIO | 10 kΩ to GND: muted through boot |
| DAC1_DIN | 19 | lower | I2S0 dout | 43 Ω series at the ESP32 |
| DAC2_DIN | 23 | lower | I2S1 dout | 43 Ω series at the ESP32 |
| VOLUME_POT | 33 | upper | ADC1 | 1 kΩ in series at the ESP32; panel pot on flying leads |
| BTN_USER | 18 | lower | GPIO | internal pull-up |
| BOOT | 0 | lower | strap | 10 kΩ pull-up, button to GND |
| RESET | EN | upper | | 10 kΩ pull-up, 1 µF and button to GND |
| STATUS_LED | 4 | lower | GPIO | 330 Ω |
| Spare | 5, 13, 14, 16, 17, 22, 25, 26, 27 | | | 5 pulses at boot, 13/14 are JTAG |

Two things about this map are set by the board rather than by the peripheral.
The five DIR9001 signals all sit on the **upper** pin row in the order the
DIR9001's own pins meet them, so the bus fans out without crossing. The two DAC
data lines sit on the **lower** row: the upper row is a 2.54 mm wall with only a
20 mm channel behind it, already carrying the five DIR9001 signals, and a data
line taken from there could not be routed on copper at all. 

Kept free on purpose: GPIO 0, 2, 12, 15 (strapping; 12 must never be pulled high or the flash runs at 1.8 V and the module bricks at boot), GPIO 1/3 (UART0 flashing and logs), GPIO 6–11 (SPI flash, fatal). GPIO 36/39 have an erratum where they glitch when the RTC ADC power-gates in light sleep; this design never sleeps, and they carry only status flags.

## 4. Deliverable 3: schematic, netlist, straps, power, grounding

### 4.1 Schematic

```
                              +5 V (class II adapter, 2 A)  ── PTC 1.1 A ── 470 µF
  ┌───────────────────────────────┬──────────────┬─────────────────┬──────────────────┐
  │                               │ R17 10Ω      │ R18 10Ω         │ R19 10Ω          │
  │                            100 µF        100 µF             100 µF                │
  │                               │              │                 │                  │
  ▼ VIN                           ▼ VIN          ▼ VIN             ▼ VCC(5V/3V3*)     │
┌───────────────┐          ┌───────────┐   ┌───────────┐     ┌──────────────┐         │
│ ESP-WROOM-32  │          │ DAC1      │   │ DAC2      │     │ DIR9001 brd  │◄─TOSLINK│
│  module       │          │ PCM5102A  │   │ PCM5102A  │     │  + TORX      │         │
│               │          │ FRONT L/R │   │ SURR L/R  │     │              │         │
│ GPIO32 ◄──────┼──────────┤ BCK ◄─────┼───┤ BCK ◄─────┼──56Ω┤ BCKO         │         │
│ GPIO35 ◄──────┼──────────┤ LRCK ◄────┼───┤ LRCK ◄────┼──56Ω┤ LRCKO        │         │
│ GPIO34 ◄──────┼──────────┼───────────┼───┼───────────┼──56Ω┤ DOUT         │         │
│ GPIO39 ◄──────┼──────────┼───────────┼───┼───────────┼─────┤ ERROR        │         │
│ GPIO36 ◄──────┼──────────┼───────────┼───┼───────────┼─────┤ AUDIO        │         │
│ GPIO19 ──56Ω──┼─────────►│ DIN       │   │           │     │ FMT1=H FMT0=H│         │
│ GPIO23 ──56Ω──┼──────────┼───────────┼──►│ DIN       │     │ CKSEL=L      │         │
│ GPIO21 ───────┼──────────┤ XSMT      ├───┤ XSMT      │     │ XTI=DGND     │         │
│   └─10k─GND   │          │ SCK=GND   │   │ SCK=GND   │     │ PSCK=LL      │         │
│               │          │ FMT=L     │   │ FMT=L     │     │ RST: int. PU │         │
│ GPIO33 ◄──────┼─ vol pot │ FLT=L     │   │ FLT=L     │     └──────┬───────┘         │
│ GPIO18 ◄──────┼─ button  │ DEMP=L    │   │ DEMP=L    │            │                 │
│               │          │ OUT L/R ──┼─► RCA ─► Fosi │ OUT L/R ──┼─► TRS ─► Eris 3.5│
│ GND           │          │ GND       │   │ GND       │     GND    │                 │
└──────┬────────┘          └─────┬─────┘   └─────┬─────┘     ───────┴─────            │
       │                         │               │                 │                  │
       └─────────────────────────┴───────────────┴─────────────────┴──── STAR GND ────┘
                                                                     (at the 9 V input)  
* check whether your DIR9001 breakout has an on-board 3.3 V LDO; if not, feed it 3.3 V from a
  dedicated LDO, not from the LM317 that feeds the ESP32.
```

### 4.2 Netlist

| Net | From | To | Series R | Notes |
|---|---|---|---|---|
| DIR_BCK | DIR9001 BCKO | ESP32 GPIO32, DAC1 BCK, DAC2 BCK | 43 Ω at DIR9001 | 3 loads ≈ 50 pF, fine at 3 MHz |
| DIR_LRCK | DIR9001 LRCKO | ESP32 GPIO35, DAC1 LRCK, DAC2 LRCK | 43 Ω at DIR9001 | |
| DIR_DOUT | DIR9001 DOUT | ESP32 GPIO34 | 43 Ω at DIR9001 | |
| DIR_ERROR | DIR9001 ERROR | ESP32 GPIO39 | none | H = unlocked or parity error |
| DIR_AUDIO | DIR9001 AUDIO | ESP32 GPIO36 | none | H = non-PCM (channel status bit 1) |
| DAC1_DIN | ESP32 GPIO19 | DAC1 DIN | 43 Ω at ESP32 | |
| DAC2_DIN | ESP32 GPIO23 | DAC2 DIN | 43 Ω at ESP32 | |
| XSMT | ESP32 GPIO21 | DAC1 XSMT, DAC2 XSMT | none | 10 kΩ pull-down at ESP32 |
| VOLUME_POT | panel pot wiper | GPIO33 | 1 kΩ at ESP32 | 3V3 to GND across the pot |
| BTN_USER | button | GPIO18 | none | to GND, internal pull-up |
| +9V | adapter | 1N5817, then LM7805 and LM317 | | class II, 9 V 1 A, centre positive |
| +3V3 | LM317 (243 Ω / 392 Ω) | ESP32 pin 2, DIR FMT straps, pot | | 470 µF + 100 nF at pin 2 |
| +5V | LM7805 | R17→DAC1 VIN; R18→DAC2 VIN; R19→DIR board | | 10 Ω + 100 µF per module |
| GND | star at jack | one wire per board | | signal wires twisted with a GND return |
| FRONT_L/R | DAC1 OUT | Fosi RCA in | on-board 470 Ω + 2.2 nF | short cable |
| SURR_L/R | DAC2 OUT | Eris 3.5 TRS in | 100 Ω tip, 100 Ω ring-to-GND | impedance-balanced, see 4.5 |

Wire rules: every digital line under 10 cm, 43 Ω at the driving end, each clock twisted with a ground return or carried on ribbon cable with GND on alternating conductors. On the board the traces leaving the ESP32 are 0.9 mm, the width of its pads, with the ground pour beside them at the 0.50 mm ball-mill gap, which is a 76 Ω coplanar line; 43 Ω plus a 25 to 40 Ω CMOS source sits on that, and `tools/impedance.py` in the repository derives it.

### 4.3 PCM5102A board straps (GY-PCM5102 type)

| Pin | Level | Meaning | How on the GY board |
|---|---|---|---|
| SCK | GND | 3-wire BCK-PLL mode | short the SCK header pin or pad to GND |
| FMT | L | I2S | solder bridge to L |
| FLT | L | normal FIR filter, 20 ts latency = 0.42 ms | bridge to L; low-latency IIR saves 0.34 ms and costs stopband, not worth it |
| DEMP | L | de-emphasis off | bridge to L |
| XSMT | GPIO21 | firmware mute | remove the H bridge, wire the centre pad to GPIO21 |
| VIN | 5 V | on-board LDO to 3.3 V | logic inputs are 3.3 V, matches ESP32 |

### 4.4 DIR9001 board straps

| Pin | Level | Why |
|---|---|---|
| FMT1, FMT0 | H, H | 24-bit I2S (Table 13) |
| PSCK1, PSCK0 | L, L | SCKO unused; 128 fs is the lowest EMI |
| CKSEL | L | PLL clock source always; keeps clocks alive on unlock via the VCO |
| XTI | DGND | no crystal needed; FSOUT unused |
| RST | leave | internal pull-up |
| RXIN | TORX output | most breakouts have the TORX and the 10 kΩ pull-down on board |

### 4.5 Power and grounding

- **Supply:** one class-II 9 V adapter, never a PC USB port. A PC ties the processor to mains earth, and if the Eris 3.5 is earthed too you have a loop through the surround cable.
- **Decoupling:** each board keeps its own 100 nF + 10 µF at the supply pin. Add 10 Ω and 100 µF in front of each DAC board and the DIR board. The ESP32 draws 50–80 mA continuous with 200 mA spikes when cache misses hit the flash; with Wi-Fi and Bluetooth disabled in menuconfig the 500 mA RF bursts never happen. Disable dynamic frequency scaling too.
- **Star ground:** the return of every board goes to the 5 V jack. Digital return current never passes through an RCA shield: each RCA jack's shield is tied only to its own DAC board GND at the jack.
- **Loop inventory:** TOSLINK is galvanically isolated, so the TV contributes nothing. The Fosi amp runs from a floating class-II barrel supply. The Eris 3.5 uses a two-pin figure-8 mains cord on most revisions and therefore also floats; check yours. With everything floating there is no earth loop, and the RCA/TRS shields simply define one common reference.
- **Long surround run:** the Eris master speaker sits behind the listener, so this is the cable that picks up hum. Its inputs are balanced TRS. Drive them impedance-balanced: tip = DAC output through 100 Ω, ring = 100 Ω to DAC GND, sleeve = DAC GND. The Eris input stage then rejects common-mode pickup even though the source is single-ended. If hum still appears, a 1:1 line isolation transformer on this run is the brute-force fix.
- **Levels:** PCM5102A full scale is 2.1 Vrms into ≥ 1 kΩ. Keep the digital master gain at or below 0 dB and use the Fosi and Eris knobs for calibration; match fronts to surrounds with pink noise and a phone SPL meter at the seat.

## 5. Deliverable 4: firmware and buffer architecture

### 5.1 Framework: ESP-IDF v5.3 or newer with `driver/i2s_std.h`

Arduino-ESP32 wrappers hide exactly the three things this design depends on: slave role on two ports, full-duplex clock sharing, and explicit DMA descriptor sizing. `ESP32-audioI2S` is a stream decoder for MP3/AAC playback with the ESP32 as I2S master, so it is the wrong tool. The AudioTools library can do I2S slave input but adds a copy loop and stream abstractions on the real-time path. If you need Arduino libraries for the display, compile Arduino as an ESP-IDF component and still call `i2s_std` directly.

### 5.2 Channel configuration

```c
// I2S0: full duplex, slave. RX from DIR9001, TX to DAC1.
i2s_chan_config_t c0 = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_SLAVE);
c0.dma_desc_num  = 8;      // RX slack: 8 x 2.67 ms = 21 ms, costs no latency
c0.dma_frame_num = 128;    // 128 frames x 8 bytes = 1024 bytes per descriptor (max 4092)
c0.auto_clear    = true;   // underrun -> zeros, not a repeated buffer
i2s_new_channel(&c0, &tx0, &rx0);

i2s_std_config_t s0 = {
    .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(48000),   // nominal only; clock is external
    .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT,
                                                    I2S_SLOT_MODE_STEREO),
    .gpio_cfg = { .mclk = I2S_GPIO_UNUSED, .bclk = 32, .ws = 35,
                  .dout = 19, .din = 34 },
};
i2s_channel_init_std_mode(tx0, &s0);
i2s_channel_init_std_mode(rx0, &s0);

// I2S1: TX only, slave, same clock pads.
i2s_chan_config_t c1 = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_SLAVE);
c1.dma_desc_num = 4; c1.dma_frame_num = 128; c1.auto_clear = true;
i2s_new_channel(&c1, &tx1, NULL);
i2s_std_config_t s1 = s0;
s1.gpio_cfg = (i2s_std_gpio_config_t){ .mclk = I2S_GPIO_UNUSED, .bclk = 32, .ws = 35,
                                        .dout = 23, .din = I2S_GPIO_UNUSED };
i2s_channel_init_std_mode(tx1, &s1);

// Start: prime both TX with 2 buffers of zeros, then enable back to back.
i2s_channel_preload_data(tx0, zeros, 2 * 1024, &n);
i2s_channel_preload_data(tx1, zeros, 2 * 1024, &n);
portDISABLE_INTERRUPTS();
i2s_channel_enable(tx1); i2s_channel_enable(tx0); i2s_channel_enable(rx0);
portENABLE_INTERRUPTS();
```

Call `i2s_new_channel()` from a task pinned to core 0 so the I2S interrupts land on core 0. Run the audio task on core 1 at priority `configMAX_PRIORITIES - 2`.

Sample handling: each RX word is 24-bit audio left-aligned in 32 bits, so `x = (float)(int32_t)word * (1.0f / 2147483648.0f)`. For IEC 61937 the payload is the top 16 bits: `w = word >> 16`. Verify channel order with a left-only test tone once; the ESP32 classic swaps channels only in 8/16-bit mono modes, which this design does not use.

### 5.3 DMA sizing and latency, 48 kHz, stereo, 32-bit slots (8 bytes per frame)

Latency is set by two things only: how far the audio task lags the RX DMA (one buffer if it keeps up) and how deep the TX channel is primed. RX descriptor count buys stall tolerance for free.

| dma_frame_num | Buffer | RX lag | TX priming (2 buf) | I2S path | + DIR9001 ~2 fr + DAC 20 ts | Total front |
|---|---|---|---|---|---|---|
| 64 | 1.33 ms | 1.33 | 2.67 | 4.0 ms | 0.5 ms | ~4.5 ms |
| 128 | 2.67 ms | 2.67 | 5.33 | 8.0 ms | 0.5 ms | ~8.5 ms |
| 256 | 5.33 ms | 5.33 | 10.7 | 16.0 ms | 0.5 ms | ~16.5 ms |

Recommendation: 128 frames, 8 RX descriptors, 4 TX descriptors primed to 2. Front latency ≈ 8.5 ms; surrounds add the deliberate 20–30 ms Haas delay on top. DSP cost per 2.67 ms block: 4 outputs × 2 biquads × 128 frames ≈ 5 k cycles plus the delay line, under 100 µs on a 240 MHz core, a 25× deadline margin.

The realistic underrun cause is not DSP load but SPI flash writes: an NVS write disables the flash cache on both cores for 5–40 ms, and any code running from flash stalls. Mark the audio task, DSP kernels and ISR-adjacent code `IRAM_ATTR`, keep their data in DRAM, and only persist the volume setting after a few seconds of pot inactivity. The 21 ms RX slack rides through most of that; a TX underrun during a volume save produces one click and is acceptable.

### 5.4 AC-3 path

- Framing: search the 16-bit stream for Pa = 0xF872, Pb = 0x4E1F; Pc bits 0–4 = 1 means AC-3, Pd = payload length in bits; bursts repeat every 1536 frames. Detect non-PCM both from the AUDIO pin and from the sync search, because several TVs never set channel-status bit 1. If the first payload word reads 0x770B instead of the AC-3 sync 0x0B77, byte-swap the payload before handing it to the decoder.
- Decoder: liba52 in float mode with output mode `A52_2F2R` and `A52_ADJUST_LEVEL`. That mode already folds centre into L/R at −3 dB and follows the ATSC A/52 downmix convention of dropping LFE, which suits a pair of 12-inch JBL 4412 woofers. Expected load is 30–60 MHz of core 1; measure with `esp_cpu_get_cycle_count()` around `a52_block()`. State plus tables is well under 100 KB. Licence is GPL-2, fine for a student build. Dolby Digital Plus is not covered; TVs transcode DD+ to DD on the optical output, so this rarely matters.
- Latency: 32 ms frame accumulation + 5–10 ms decode + 8 ms I2S path ≈ 45–50 ms. Modern TVs delay the picture for their own processing, so measure end-to-end with a clap or a sync test clip before touching any AV-delay setting.

### 5.5 DSP block (PCM path)

- Surround: S = 0.5 × (L − R), then 2nd-order Butterworth HPF at 100 Hz, 4th-order Butterworth LPF at 7 kHz as two cascaded biquads with Q = 0.5412 and Q = 1.3066, then a 20–30 ms circular delay (1440 floats at 48 kHz for 30 ms). Use `dsps_biquad_f32_ae32` from ESP-DSP. Recompute coefficients and delay length when the measured fs changes between 44.1 and 48 kHz.
- fs measurement: count received frames per second in the `on_recv` callback; 44100 vs 48000 vs 32000 separate cleanly.
- Mute state machine: ERROR high → XSMT low, output zeros. ERROR low for 100 ms → classify PCM vs IEC 61937 → output two valid buffers → XSMT high. Muting also on every rate or format change, since the PCM5102A soft-mute ramp takes 150 ts + 0.2 ms ≈ 3.3 ms and avoids the pop.
- Volume: digital gain in the ESP32 before conversion to 32-bit output; with 16-bit sources and a 32-bit DAC there is no resolution loss until beyond −48 dB. Read the pot on ADC1 with averaging and some hysteresis, so a noisy wiper does not make the volume hunt.

## 5.6 Transmission lines on a single-sided board

Worth stating explicitly because the usual formula does not apply here. The board has copper on one side only, so a trace is **not** microstrip: there is no return conductor under it. It is a coplanar waveguide with the ground pour beside it and air and FR4 below, which puts roughly half the field in each, so the effective permittivity is (εr + 1)/2 ≈ 2.65 rather than 3.3. Using a microstrip formula would predict about 110 Ω for a 1 mm trace on 1.6 mm FR4 and would be meaningless.

| Track width | Z0 | Propagation delay |
|---|---|---|
| 0.3 mm | 105 Ω | 5.43 ps/mm |
| 0.5 mm | 91 Ω | 5.43 ps/mm |
| 0.9 mm | 76 Ω | 5.43 ps/mm |
| 1.0 mm | 74 Ω | 5.43 ps/mm |

Three consequences.

**The board is at the boundary where termination matters at all.** At 5.43 ps/mm a 2 ns edge has a critical length of about 61 mm on the usual rise-time-over-six rule. The BCK and LRCK nets span the board and exceed it; the point-to-point data lines at 45 mm do not. So the series resistors are doing real work on the clocks and are insurance on the data lines.

**43 Ω is the right series value.** With a 0.9 mm trace at 76 Ω and a CMOS output impedance of 25 to 40 Ω, the resistor that makes the source match is 36 to 51 Ω, and the shop has 43.2 Ω. R4 and R5 sit at the DAC end because they carry DIN over the BCK run, so they damp rather than source-match; those lines are about 15 and 37 mm, under the 61 mm critical length. The DIR9001 datasheet gives only a DC bound on its output drive, so tune on a scope at the far pad if the edges ring.

**Mill tolerance is not the problem people expect.** ±0.03 mm on both the trace and the gap, the ball mill's measured spread, moves Z0 by about ±2 Ω, and the FR4 permittivity spread over 4.2 to 4.6 moves it by under 2 Ω. What does vary is the pour: where the ground retreats from a trace the local impedance rises, so the number is a nominal, not a controlled-impedance spec.

## 6. Bring-up order

1. Power only, check 3.3 V on every board, confirm ESP32 boots with GPIO 12 floating.
2. DIR9001 alone with a TV playing PCM: scope BCKO = 3.072 MHz, LRCKO = 48 kHz, ERROR low.
3. Add the DACs with SCK grounded, DIN left open: outputs must sit at 0 V, no noise.
4. ESP32 pass-through firmware, RX to both TX unprocessed, XSMT high: verify L/R order, check DIN setup margin at the DAC end with the scope.
5. Add the matrix DSP, then the IEC 61937 detector, then liba52.
