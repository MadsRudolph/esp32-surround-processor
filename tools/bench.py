#!/usr/bin/env python3
"""Bench checks for the surround board with an Analog Discovery 3.

    python3 tools/bench.py rails          # CH1 = +5V, CH2 = +3V3: mean, ripple, noise
    python3 tools/bench.py uart [secs]    # DIO0 = J2 TX: print what the ESP32 says
    python3 tools/bench.py watch [secs]   # rails sampled slowly, min/max (brown-out hunt)

Wiring (all AD3 grounds are common):
    GND  -> J7 GND (or J2 GND)
    1+   -> A3 socket pin 1 (+5V after R17), 1- -> GND
    2+   -> J7 3V3,                          2- -> GND
    DIO0 -> J2 TX
"""
import os, sys, time
from ctypes import *

for p in ("/usr/lib/digilent/adept",):
    if p not in os.environ.get("LD_LIBRARY_PATH", ""):
        os.environ["LD_LIBRARY_PATH"] = p + ":" + os.environ.get("LD_LIBRARY_PATH", "")
        os.execv(sys.executable, [sys.executable] + sys.argv)

dwf = cdll.LoadLibrary("libdwf.so")
PROBE_ATTEN = float(os.environ.get("PROBE_ATTEN", "10"))   # scope probes on the BNC adapter, 10x


def open_dev():
    h = c_int()
    dwf.FDwfParamSet(c_int(4), c_int(0))            # on close: keep running = 0 -> stop
    dwf.FDwfDeviceOpen(c_int(-1), byref(h))
    if not h.value:
        e = create_string_buffer(512); dwf.FDwfGetLastErrorMsg(e)
        raise SystemExit("AD3 not opened: " + e.value.decode().strip())
    return h


def acquire(h, rate, n, rng=25.0):
    """One buffer from both scope channels. Returns two lists of volts."""
    for ch in (0, 1):
        dwf.FDwfAnalogInChannelEnableSet(h, c_int(ch), c_int(1))
        dwf.FDwfAnalogInChannelAttenuationSet(h, c_int(ch), c_double(PROBE_ATTEN))
        dwf.FDwfAnalogInChannelOffsetSet(h, c_int(ch), c_double(0))
        dwf.FDwfAnalogInChannelRangeSet(h, c_int(ch), c_double(rng))
    dwf.FDwfAnalogInFrequencySet(h, c_double(rate))
    dwf.FDwfAnalogInBufferSizeSet(h, c_int(n))
    dwf.FDwfAnalogInAcquisitionModeSet(h, c_int(0))
    dwf.FDwfAnalogInConfigure(h, c_int(1), c_int(1))
    sts = c_byte()
    t0 = time.time()
    while True:
        dwf.FDwfAnalogInStatus(h, c_int(1), byref(sts))
        if sts.value == 2:
            break
        if time.time() - t0 > n / rate + 5:
            raise SystemExit("acquisition timed out")
        time.sleep(0.01)
    out = []
    for ch in (0, 1):
        buf = (c_double * n)()
        dwf.FDwfAnalogInStatusData(h, c_int(ch), buf, c_int(n))
        out.append(list(buf))
    return out


def stats(v):
    m = sum(v) / len(v)
    rms = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5
    return m, min(v), max(v), rms


def rails(h):
    time.sleep(0.5)
    acquire(h, 1e5, 2000)                             # settle the front end
    print(f"{'rail':6} {'mean':>8} {'min':>8} {'max':>8} {'p-p':>8} {'rms':>8}   verdict")
    ok = True
    for label, rate, n in (("10 ms", 1e6, 10000), ("1 s", 16000, 16000)):
        a, b = acquire(h, rate, n)
        print(f"-- window {label}")
        for name, v, lo, hi in (("+5V", a, 4.75, 5.25), ("+3V3", b, 3.15, 3.45)):
            m, mn, mx, rms = stats(v)
            good = lo <= m <= hi and mn > lo - 0.15
            ok &= good
            print(f"{name:6} {m:8.3f} {mn:8.3f} {mx:8.3f} {1000*(mx-mn):6.0f}mV {1000*rms:6.1f}mV   {'ok' if good else 'OUT OF RANGE'}")
    return ok


def watch(h, secs):
    lo = [99, 99]; hi = [-99, -99]
    t0 = time.time()
    while time.time() - t0 < secs:
        a, b = acquire(h, 2e5, 16000)                 # 80 ms windows
        for i, v in enumerate((a, b)):
            lo[i] = min(lo[i], min(v)); hi[i] = max(hi[i], max(v))
        print(f"\r+5V {lo[0]:.3f}..{hi[0]:.3f}   +3V3 {lo[1]:.3f}..{hi[1]:.3f}", end="", flush=True)
    print()


def uart(h, secs, pin=0, baud=115200):
    dwf.FDwfDigitalUartRateSet(h, c_double(baud))
    dwf.FDwfDigitalUartRxSet(h, c_int(pin))
    dwf.FDwfDigitalUartBitsSet(h, c_int(8))
    dwf.FDwfDigitalUartParitySet(h, c_int(0))
    dwf.FDwfDigitalUartStopSet(h, c_double(1))
    n = c_int(); par = c_int()
    buf = create_string_buffer(8193)
    dwf.FDwfDigitalUartRx(h, None, c_int(0), byref(n), byref(par))
    print(f"listening on DIO{pin} at {baud} baud for {secs:.0f} s: tap RESET now", flush=True)
    got = bytearray()
    t0 = time.time()
    while time.time() - t0 < secs:
        dwf.FDwfDigitalUartRx(h, buf, c_int(8192), byref(n), byref(par))
        if n.value:
            got += buf.raw[:n.value]
            sys.stdout.write(buf.raw[:n.value].decode("ascii", "replace")); sys.stdout.flush()
        time.sleep(0.01)
    print(f"\n-- {len(got)} bytes")
    return got


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "rails"
    arg = float(sys.argv[2]) if len(sys.argv) > 2 else 20
    h = open_dev()
    try:
        if cmd == "rails":
            sys.exit(0 if rails(h) else 1)
        elif cmd == "watch":
            watch(h, arg)
        elif cmd == "uart":
            uart(h, arg, baud=int(sys.argv[3]) if len(sys.argv) > 3 else 115200)
        else:
            raise SystemExit(__doc__)
    finally:
        dwf.FDwfDeviceClose(h)
