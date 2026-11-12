#!/usr/bin/env python3
"""S/PDIF from the Analog Discovery 3, so the board can be tested without the TV.

    python3 tools/spdif_gen.py selftest          # no wiring: read the AD3's own pin back and decode it
    python3 tools/spdif_gen.py run [L_hz] [R_hz] [level_dbfs]   # play until Ctrl-C
    python3 tools/spdif_gen.py run 1017 1526 -12
    python3 tools/spdif_gen.py run 1017 -1017 -12   # negative right = same tone, inverted (pure surround)

The pattern generator runs at 100 MHz / 16 = 6.25 MHz, one sample per biphase cell,
which makes a sample rate of 48 828 Hz. One whole 192-frame S/PDIF block fits in the
pattern memory (AD3 configuration 4: 32 768 bits) and loops, so the tones are the ones
that fit a whole number of cycles into 192 frames: multiples of 254.3 Hz.

Wiring: DIO 1 -> 340 ohm (two 681 ohm in parallel) -> coax (RCA) centre pin,
        115 ohm from the centre pin to ground, AD3 GND -> RCA shell.
The bench server must not hold the AD3 while this runs (stop it, or Release AD3).
"""
import math, sys, time
from ctypes import byref, c_byte, c_double, c_int, c_ubyte, c_uint, create_string_buffer

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from bench import dwf                                  # noqa: E402  (sets the library path)

PIN = 1                      # DIO 1 (DIO 0 stays on the board's serial TX)
BASE_HZ = 100e6
DIVIDER = 16                 # 6.25 MHz cells
FRAMES = 192                 # one channel-status block
FS = BASE_HZ / DIVIDER / 128
CONFIG = 4                   # 32 768-bit pattern memory, 32 768-sample logic analyser

# preambles as cell patterns when the line was low before them
PRE = {"B": (1, 1, 1, 0, 1, 0, 0, 0), "M": (1, 1, 1, 0, 0, 0, 1, 0), "W": (1, 1, 1, 0, 0, 1, 0, 0)}


def channel_status():
    """Consumer, PCM audio, copy permitted, 48 kHz. 192 bits, sent one per frame."""
    c = [0] * 192
    c[2] = 1                 # copy permitted
    c[25] = 1                # sample rate 48 kHz (bits 24-27 = 0100)
    return c


def tone_bin(hz):
    """Nearest tone that fits 192 frames: returns whole cycles per block (signed)."""
    k = round(abs(hz) * FRAMES / FS)
    return int(math.copysign(max(k, 0), hz)) if hz else 0


def samples(l_hz, r_hz, level_db):
    amp = (2 ** 23 - 1) * 10 ** (level_db / 20.0)
    kl, kr = tone_bin(l_hz), tone_bin(r_hz)
    out = []
    for n in range(FRAMES):
        l = int(round(amp * math.sin(2 * math.pi * abs(kl) * n / FRAMES))) if kl else 0
        r = int(round(amp * math.sin(2 * math.pi * abs(kr) * n / FRAMES))) if kr else 0
        out.append((l if kl >= 0 else -l, r if kr >= 0 else -r))
    return out, abs(kl) * FS / FRAMES, abs(kr) * FS / FRAMES


def encode(pcm):
    """192 stereo 24-bit frames -> list of cells (0/1), biphase mark coded."""
    cs = channel_status()
    cells, level = [], 0
    for n, (l, r) in enumerate(pcm):
        for ch, s in ((0, l), (1, r)):
            pre = "B" if (n == 0 and ch == 0) else ("M" if ch == 0 else "W")
            cells += [b ^ level for b in PRE[pre]]
            level = cells[-1]
            bits = [(s >> i) & 1 for i in range(24)] + [0, 0, cs[n]]        # audio LSB first, V, U, C
            bits.append(sum(bits) & 1)                                       # even parity over slots 4-31
            for b in bits:
                level ^= 1                   # every bit starts with a transition
                cells.append(level)
                if b:
                    level ^= 1               # a one has a second transition in the middle
                cells.append(level)
    assert len(cells) == FRAMES * 128
    assert level == 0, "block does not end where it began: the loop would glitch"
    return cells


def decode(cells):
    """Cells back to frames, for the self-test. Returns (frames, errors)."""
    n = len(cells)
    def pre_at(i):
        seg = tuple(cells[i:i + 8])
        inv = tuple(1 - c for c in seg)
        for k, p in PRE.items():
            if seg == p or inv == p:
                return k
        return None
    i = 0
    while i + 128 <= n and pre_at(i) is None:       # find the first preamble
        i += 1
    frames, cur, errors = [], {}, 0
    while i + 64 <= n:
        k = pre_at(i)
        if k is None:
            errors += 1; i += 1
            continue
        bits = []
        for j in range(28):
            a, b = cells[i + 8 + 2 * j], cells[i + 9 + 2 * j]
            bits.append(a ^ b)
        if sum(bits) & 1:
            errors += 1
        v = sum(bit << t for t, bit in enumerate(bits[:24]))
        if v & 0x800000:
            v -= 1 << 24
        if k in ("B", "M"):
            cur = {"l": v, "pre": k}
        else:
            cur["r"] = v
            if "l" in cur:
                frames.append((cur["l"], cur["r"], cur["pre"]))
            cur = {}
        i += 64
    return frames, errors


def open_ad3():
    h = c_int()
    dwf.FDwfDeviceConfigOpen(c_int(-1), c_int(CONFIG), byref(h))
    if not h.value:
        e = create_string_buffer(512); dwf.FDwfGetLastErrorMsg(e)
        raise SystemExit("AD3 not opened: " + e.value.decode().strip())
    return h


def start(h, cells):
    data = bytearray((len(cells) + 7) // 8)
    for i, c in enumerate(cells):
        if c:
            data[i >> 3] |= 1 << (i & 7)
    buf = (c_ubyte * len(data)).from_buffer(data)
    dwf.FDwfDigitalOutReset(h)
    dwf.FDwfDigitalOutEnableSet(h, c_int(PIN), c_int(1))
    dwf.FDwfDigitalOutTypeSet(h, c_int(PIN), c_int(1))               # custom pattern
    dwf.FDwfDigitalOutIdleSet(h, c_int(PIN), c_int(1))               # idle low
    dwf.FDwfDigitalOutDividerSet(h, c_int(PIN), c_uint(DIVIDER))
    dwf.FDwfDigitalOutDataSet(h, c_int(PIN), buf, c_uint(len(cells)))
    dwf.FDwfDigitalOutRunSet(h, c_double(0))                         # run for ever
    dwf.FDwfDigitalOutRepeatSet(h, c_int(0))
    dwf.FDwfDigitalOutConfigure(h, c_int(1))


def capture(h, n=32768):
    """Read DIO PIN back with the logic analyser at 100 MHz."""
    dwf.FDwfDigitalInReset(h)
    dwf.FDwfDigitalInDividerSet(h, c_uint(1))
    dwf.FDwfDigitalInSampleFormatSet(h, c_int(16))
    dwf.FDwfDigitalInBufferSizeSet(h, c_int(n))
    dwf.FDwfDigitalInAcquisitionModeSet(h, c_int(0))
    dwf.FDwfDigitalInConfigure(h, c_int(1), c_int(1))
    sts = c_byte(); t0 = time.time()
    while True:
        dwf.FDwfDigitalInStatus(h, c_int(1), byref(sts))
        if sts.value == 2:
            break
        if time.time() - t0 > 3:
            raise SystemExit("logic analyser did not finish")
        time.sleep(0.01)
    raw = (c_ubyte * (2 * n))()
    dwf.FDwfDigitalInStatusData(h, raw, c_int(2 * n))
    return [(raw[2 * i] >> PIN) & 1 for i in range(n)]


def selftest():
    pcm, fl, fr = samples(1017, 1526, -12)
    cells = encode(pcm)
    # 1. the coder against the decoder, in software, with the block looped once
    frames, err = decode(cells + cells)
    want = [(l, r) for l, r in pcm] * 2
    ok_sw = err == 0 and [(l, r) for l, r, _ in frames][:len(want) - 1] == want[:len(frames)][:len(want) - 1] and frames[0][2] == "B"
    print(f"software round trip: {len(frames)} frames, {err} errors, {'OK' if ok_sw else 'FAILED'}")
    # 2. the real pin, read back by the AD3's own logic analyser
    h = open_ad3()
    try:
        start(h, cells)
        time.sleep(0.2)
        s = capture(h)
        # 16 samples per cell: take the middle of each cell after finding an edge
        edge = next(i for i in range(1, len(s)) if s[i] != s[i - 1])
        got = [s[i] for i in range(edge + DIVIDER // 2, len(s), DIVIDER)]
        runs, last, run = [], got[0], 0
        for c in got:
            if c == last: run += 1
            else: runs.append(run); run = 1; last = c
        frames, err = decode(got)
        ref = [(l, r) for l, r in pcm]
        # the capture starts anywhere in the block: line it up on the first decoded frame
        hits = 0
        for off in range(FRAMES):
            if all(ref[(off + k) % FRAMES] == frames[k][:2] for k in range(len(frames))):
                hits += 1
        longest = max(runs) if runs else 0
        ok_hw = err == 0 and len(frames) >= 12 and hits >= 1 and longest <= 3
        print(f"pin read back: {len(got)} cells, {len(frames)} frames decoded, {err} errors, "
              f"longest run {longest} cells (3 allowed), data matches the block: {'yes' if hits else 'NO'}"
              f" -> {'OK' if ok_hw else 'FAILED'}")
    finally:
        dwf.FDwfDigitalOutReset(h)
        dwf.FDwfDeviceClose(h)
    print(f"sample rate {FS:.1f} Hz, tones {fl:.1f} Hz left, {fr:.1f} Hz right")
    return ok_sw and ok_hw


def run(l_hz, r_hz, level_db):
    pcm, fl, fr = samples(l_hz, r_hz, level_db)
    h = open_ad3()
    start(h, encode(pcm))
    inv = " (right inverted)" if r_hz < 0 else ""
    print(f"S/PDIF on DIO {PIN}: {FS:.0f} Hz, left {fl:.1f} Hz, right {fr:.1f} Hz{inv}, {level_db:g} dBFS. Ctrl-C stops.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        dwf.FDwfDigitalOutReset(h)
        dwf.FDwfDeviceClose(h)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    elif cmd == "run":
        a = [float(x) for x in sys.argv[2:5]]
        run(a[0] if len(a) > 0 else 1017, a[1] if len(a) > 1 else 1526, a[2] if len(a) > 2 else -12)
    else:
        raise SystemExit(__doc__)
