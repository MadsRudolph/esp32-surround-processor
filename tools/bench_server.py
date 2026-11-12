#!/usr/bin/env python3
"""Bench page for the surround board: the Analog Discovery 3 drawn live in a browser.

    python3 tools/bench_server.py            # then open http://127.0.0.1:8791/
    python3 tools/bench_server.py --port N

One process owns the AD3 (opened on first use, reopened after an unplug) and serves
tools/bench_page.html, which is the test procedure as well as the instruments. Results
are kept in hardware/bench/results.json. Stdlib only; libdwf through ctypes (bench.py).

Wiring (as tools/bench.py): GND -> J2 GND, 1+ -> front DAC socket pin 1 (+5V),
2+ -> J7 3V3, 1- and 2- -> GND, DIO0 -> J2 TX. DIO15 is the UART self-test pin: it is
driven during the self-test only, so leave it unconnected.

How the instruments share the AD3: every libdwf call goes through one lock. The scope
(analog in) has a second lock held for a whole acquisition, so live view, rail check,
ripple and the rail watch take turns. UART decode runs on the digital-in engine; its
poller only needs the call lock, so it keeps reading between the scope's calls and the
two run together.
"""
import os, sys

# libdwf needs the Adept runtime on the library path; bench.py re-execs to set it.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import dwf, PROBE_ATTEN                                    # noqa: E402  (re-execs if needed)

import json, math, random, signal, threading, time, datetime     # noqa: E402
from ctypes import byref, c_byte, c_double, c_int, create_string_buffer   # noqa: E402
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer       # noqa: E402
from urllib.parse import urlparse, parse_qs                                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PAGE = os.path.join(HERE, "bench_page.html")
BENCH_DIR = os.path.join(REPO, "hardware", "bench")
RESULTS = os.path.join(BENCH_DIR, "results.json")

RAILS = (("+5V", 4.75, 5.25), ("+3V3", 3.15, 3.45))     # CH1, CH2 (as bench.py)
DIP = (4.60, 3.00)                                        # rail watch: a dip is below this
SELFTEST_PIN = 15
ENV_POINTS = 1000                                         # envelope columns sent to the page


def log(msg):
    sys.stderr.write(time.strftime("%H:%M:%S ") + msg + "\n")
    sys.stderr.flush()


class DeviceError(Exception):
    pass


class Busy(Exception):
    pass


class NoTrigger(Exception):
    pass


# --------------------------------------------------------------------------- device

class AD3:
    """One AD3 handle. `lock` serialises every libdwf call; `ain` owns the scope."""

    def __init__(self):
        self.lock = threading.RLock()
        self.ain = threading.Lock()
        self.ain_owner = None
        self.h = None
        self.gen = 0                       # bumps on every (re)open
        self.name = self.sn = None
        self.last_error = None
        self.cfg = None                    # cached single-acquisition setup
        self.fe = None                     # (ranges, offsets) the front end is set to
        self.last_auto = False             # last triggered acquisition was an auto-timeout free run

    @staticmethod
    def _errmsg():
        e = create_string_buffer(512)
        dwf.FDwfGetLastErrorMsg(e)
        msg = " ".join(e.value.decode(errors="replace").split())
        return msg or "unknown libdwf error"

    def ensure(self):
        """Open the device if it is not open. Raises DeviceError with a clear message."""
        with self.lock:
            if self.h is not None:
                return
            n = c_int()
            dwf.FDwfEnum(c_int(0), byref(n))
            if n.value < 1:
                self.last_error = "AD3 not found: is it plugged in to USB?"
                raise DeviceError(self.last_error)
            nm = create_string_buffer(64); sn = create_string_buffer(32); used = c_int()
            dwf.FDwfEnumDeviceName(c_int(0), nm); dwf.FDwfEnumSN(c_int(0), sn)
            dwf.FDwfEnumDeviceIsOpened(c_int(0), byref(used))
            h = c_int()
            dwf.FDwfParamSet(c_int(4), c_int(1))           # DwfParamOnClose: 1 = stop
            dwf.FDwfDeviceOpen(c_int(-1), byref(h))
            if not h.value:
                msg = self._errmsg()
                if used.value:
                    msg = "AD3 is in use by another program (WaveForms?): close it. " + msg
                self.last_error = "AD3 not opened: " + msg
                raise DeviceError(self.last_error)
            self.h = h
            self.gen += 1
            self.name, self.sn = nm.value.decode(), sn.value.decode()
            self.cfg = self.fe = None
            self.last_error = None
            log(f"AD3 opened: {self.name} {self.sn} (open #{self.gen})")

    def drop(self, reason=None):
        with self.lock:
            if reason:
                log("AD3 closed: " + reason)
            if self.h is not None:
                try:
                    dwf.FDwfDeviceClose(self.h)
                except Exception:
                    pass
            self.h = None
            self.cfg = self.fe = None
            if reason:
                self.last_error = reason

    def call(self, fn, *args):
        """Call FDwf<fn>(h, *args). A failed call closes the handle so the next use reopens."""
        with self.lock:
            if self.h is None:
                raise DeviceError(self.last_error or "AD3 not open")
            if not getattr(dwf, "FDwf" + fn)(self.h, *args):
                msg = f"FDwf{fn} failed: {self._errmsg()}"
                self.drop(msg + " (the AD3 will be reopened on the next request)")
                raise DeviceError(msg)

    def status(self):
        with self.lock:
            if self.h is not None:
                # Open: no USB enumeration here (it holds the lock ~0.1 s and would stall the
                # UART poller). An unplug shows up as a failed call, which drops the handle.
                present = True
            else:
                n = c_int()
                dwf.FDwfEnum(c_int(0), byref(n))
                present = n.value > 0
            return {"present": present, "open": self.h is not None, "name": self.name,
                    "sn": self.sn, "error": self.last_error, "scope_owner": self.ain_owner}

    # -- analog in ---------------------------------------------------------------

    def take_scope(self, owner, timeout):
        if self.ain_owner in ("rail watch", "roll scope"):   # hold the scope until stopped: say so now
            raise Busy(f"the scope is busy: the {self.ain_owner} is running (stop it first)")
        if not self.ain.acquire(timeout=timeout):
            raise Busy(f"the scope is busy: {self.ain_owner or 'another request'} is using it")
        self.ain_owner = owner

    def give_scope(self):
        self.ain_owner = None
        self.ain.release()

    def _frontend(self, ranges, offsets):
        """Set range and offset; after a change, take one short acquisition to let it settle."""
        key = (tuple(ranges), tuple(offsets))
        if self.fe == key:
            return
        with self.lock:
            for ch in (0, 1):
                self.call("AnalogInChannelEnableSet", c_int(ch), c_int(1))
                self.call("AnalogInChannelAttenuationSet", c_int(ch), c_double(PROBE_ATTEN))
                self.call("AnalogInChannelRangeSet", c_int(ch), c_double(ranges[ch]))
                self.call("AnalogInChannelOffsetSet", c_int(ch), c_double(offsets[ch]))
            self.fe = key
            self.cfg = None
        time.sleep(0.03)
        self._single(1e6, 2000)

    def _single(self, rate, n, timeout=None, trig=None, wait=None):
        """One buffer from both channels with the current front end. Caller owns `ain`.
        trig = (channel, slope, level V, auto timeout s, trigger position s, hysteresis V) or None.
        wait: with a trigger and no auto timeout, give up after this many seconds (NoTrigger)."""
        with self.lock:
            if self.cfg != (rate, n, trig):
                self.call("AnalogInFrequencySet", c_double(rate))
                self.call("AnalogInBufferSizeSet", c_int(n))
                self.call("AnalogInAcquisitionModeSet", c_int(0))
                if trig:
                    ch, slope, level, auto, pos, hyst = trig
                    self.call("AnalogInTriggerAutoTimeoutSet", c_double(auto))   # 0 = wait forever
                    self.call("AnalogInTriggerSourceSet", c_byte(2))      # trigsrcDetectorAnalogIn
                    self.call("AnalogInTriggerTypeSet", c_int(0))         # trigtypeEdge
                    self.call("AnalogInTriggerChannelSet", c_int(ch))
                    self.call("AnalogInTriggerLevelSet", c_double(level))
                    # With zero hysteresis the AD3 fires on both edges whatever the slope says
                    # (measured on a 1 kHz sine): the hysteresis is what makes rise/fall real.
                    self.call("AnalogInTriggerHysteresisSet", c_double(hyst))
                    self.call("AnalogInTriggerConditionSet", c_int(slope))  # 0 rise, 1 fall
                    self.call("AnalogInTriggerPositionSet", c_double(pos))
                else:
                    self.call("AnalogInTriggerSourceSet", c_byte(0))      # none: free run
                self.cfg = (rate, n, trig)
            self.call("AnalogInConfigure", c_int(1), c_int(1))
            fr = c_double()
            self.call("AnalogInFrequencyGet", byref(fr))
        span = n / fr.value
        t0 = time.time()
        sts = c_byte()
        poll = min(0.005, max(0.0005, span / 20))
        limit = span + (timeout or 3.0)
        if trig and wait:
            limit = wait
        while True:
            self.call("AnalogInStatus", c_int(1), byref(sts))     # takes the lock per call
            if sts.value == 2:
                break
            if time.time() - t0 > limit:
                self.cfg = None
                if trig and wait:
                    with self.lock:
                        self.call("AnalogInConfigure", c_int(0), c_int(0))     # abort the armed scope
                    raise NoTrigger(f"no trigger within {wait:g} s")
                raise DeviceError("scope acquisition timed out")
            time.sleep(poll)
        auto = c_int()
        out = []
        with self.lock:
            self.call("AnalogInStatusAutoTriggered", byref(auto))
            for ch in (0, 1):
                buf = (c_double * n)()
                self.call("AnalogInStatusData", c_int(ch), buf, c_int(n))
                out.append(list(buf))
        self.last_auto = bool(auto.value)
        return fr.value, out

    def acquire(self, rate, n, ranges=(50.0, 50.0), offsets=(0.0, 0.0), trig=None, wait=None):
        self.ensure()
        self._frontend(ranges, offsets)
        return self._single(rate, n, trig=trig, wait=wait)


dev = AD3()


def stats(v):
    n = len(v)
    m = sum(v) / n
    mn, mx = min(v), max(v)
    rms = math.sqrt(max(0.0, sum(x * x for x in v) / n - m * m))   # AC rms (mean removed)
    return {"mean": m, "min": mn, "max": mx, "pp": mx - mn, "rms": rms}


def envelope(v, cols=ENV_POINTS, nd=5):
    """Min/max per column: spikes survive the decimation."""
    n = len(v)
    if n <= cols:
        return [[round(x, nd), round(x, nd)] for x in v]
    out = []
    for i in range(cols):
        seg = v[i * n // cols:(i + 1) * n // cols]
        out.append([round(min(seg), nd), round(max(seg), nd)])
    return out


def rnd(d, nd=6):
    return {k: (round(x, nd) if isinstance(x, float) else x) for k, x in d.items()}


LOGIC_TH = 1.65            # logic readout threshold, V


def schmitt_freq(v, rate):
    """Frequency of a periodic signal, or None: rising edges through the mid level with 30 %
    hysteresis (linear interpolation), at least 3 edges and periods within 15 % of each other."""
    mn, mx = min(v), max(v)
    pp = mx - mn
    if pp < 0.05:
        return None
    mid = (mn + mx) / 2
    hi, lo = mid + 0.15 * pp, mid - 0.15 * pp
    low = v[0] < hi
    edges = []
    prev = v[0]
    for i, x in enumerate(v):
        if low:
            if x >= hi:
                edges.append(i - 1 + (hi - prev) / (x - prev) if i and x != prev else i)
                low = False
        elif x <= lo:
            low = True
        prev = x
    if len(edges) < 3:
        return None
    per = [b - a for a, b in zip(edges, edges[1:])]
    avg = sum(per) / len(per)
    if avg <= 0 or max(abs(p - avg) for p in per) > 0.15 * avg:
        return None
    return rate / avg


def stats2(v, rate):
    """Everything the live scope shows for one channel."""
    n = len(v)
    m = sum(v) / n
    mn, mx = min(v), max(v)
    msq = math.sumprod(v, v) / n
    high = sum(x >= LOGIC_TH for x in v) / n
    logic = "HIGH" if mn >= LOGIC_TH else "LOW" if mx < LOGIC_TH else "EDGES"
    return {"mean": m, "min": mn, "max": mx, "pp": mx - mn,
            "rms": math.sqrt(max(0.0, msq)), "acrms": math.sqrt(max(0.0, msq - m * m)),
            "freq": schmitt_freq(v, rate), "logic": logic, "duty": 100 * high}


# --------------------------------------------------------------------------- scope

LO_RANGE = 5.0
LO_HALF = 2.55            # usable half-window of the 5 V range (measured 2.61; keep a margin)


class Scope:
    """Live view, two channels, any signal. Per channel the input range is '50' (50 V span,
    3.7 mV steps), '5' (5 V span centred on the signal, 0.3 mV steps) or 'auto' (follows the
    signal: fine when it fits, coarse when it does not or when it clips). Optional hardware
    edge trigger so a periodic signal stands still."""

    SLOPES = {"r": 0, "f": 1}

    def __init__(self):
        self.hw = [{"fine": False, "c": None}, {"fine": False, "c": None}]

    def _centres(self):
        _, data = dev.acquire(1e6, 10000)          # 10 ms: whole cycles of anything above 100 Hz
        for ch, v in enumerate(data):
            self.hw[ch]["c"] = round(sum(v) / len(v), 2)

    def frame(self, window, rng, trig, level, wait, hyst=0.1):
        window = min(max(window, 1e-4), 2.0)
        n = 16000 if window >= 0.05 else 10000
        rate = n / window
        dev.take_scope("live scope", timeout=4.0 + (wait or 0))
        try:
            dev.ensure()
            for ch in (0, 1):
                if rng[ch] == "50":
                    self.hw[ch]["fine"] = False
                elif rng[ch] == "5":
                    self.hw[ch]["fine"] = True
            if any(self.hw[ch]["fine"] and self.hw[ch]["c"] is None for ch in (0, 1)):
                self._centres()
            ranges = tuple(LO_RANGE if self.hw[ch]["fine"] else 50.0 for ch in (0, 1))
            offs = tuple((self.hw[ch]["c"] or 0.0) if self.hw[ch]["fine"] else 0.0 for ch in (0, 1))
            tr = None
            if trig:
                auto = 0.0 if wait else max(0.1, window)
                tr = (int(trig[0]), self.SLOPES[trig[1]], float(level), auto, 0.0, float(hyst))   # position 0 = trigger at the buffer middle
            rate, data = dev.acquire(rate, n, ranges, offs, trig=tr, wait=wait)
            out = []
            for ch, v in enumerate(data):
                st = self.hw[ch]
                mn, mx = min(v), max(v)
                clip = st["fine"] and (mn < offs[ch] - LO_HALF or mx > offs[ch] + LO_HALF)
                note = (f"5 V range centred on {offs[ch]:.2f} V (0.3 mV steps)" if st["fine"]
                        else "50 V range (3.7 mV steps)")
                out.append({"stats": rnd(stats2(v, rate)), "env": envelope(v, 1000), "clipped": clip,
                            "note": note, "fine": st["fine"], "centre": offs[ch]})
                mid = round((mn + mx) / 2, 2)           # next frame's front end
                if rng[ch] == "auto":
                    if not st["fine"] and mx - mn < 2.0:
                        st["fine"], st["c"] = True, mid
                    elif st["fine"] and clip:
                        if mx - mn < 4.0:
                            st["c"] = mid
                        else:
                            st["fine"] = False
                elif rng[ch] == "5" and clip:
                    st["c"] = mid
            return {"window": n / rate, "rate": rate, "n": n, "t": time.time(), "ch": out,
                    "trig": ({"src": int(trig[0]), "slope": trig[1], "level": float(level),
                              "auto": dev.last_auto, "hyst": float(hyst), "pos": n / rate / 2} if trig else None)}
        except NoTrigger as e:
            return {"notrigger": True, "message": str(e), "t": time.time()}
        finally:
            dev.give_scope()


scope = Scope()


def rail_check():
    """bench.py rails: settle, then 10 ms and 1 s windows on the 50 V range."""
    dev.take_scope("rail check", timeout=10.0)
    try:
        dev.ensure()
        dev.acquire(1e5, 2000)                    # settle the front end
        time.sleep(0.2)
        windows, ok = [], True
        for label, rate, n in (("10 ms", 1e6, 10000), ("1 s", 16000, 16000)):
            fr, data = dev.acquire(rate, n)
            chs = []
            for (name, lo, hi), v in zip(RAILS, data):
                s = stats(v)
                good = lo <= s["mean"] <= hi and s["min"] > lo - 0.15
                ok &= good
                chs.append({"name": name, "lo": lo, "hi": hi, "stats": rnd(s), "pass": good,
                            "env": envelope(v, 600, 4)})
            windows.append({"label": label, "rate": fr, "n": n, "window": n / fr, "ch": chs})
        return {"pass": ok, "t": time.time(), "windows": windows}
    finally:
        dev.give_scope()


def ripple():
    """Ripple at high resolution: 5 V range centred on each rail, 10 ms and 1 s windows."""
    dev.take_scope("ripple measurement", timeout=10.0)
    try:
        dev.ensure()
        _, data = dev.acquire(1e6, 10000)
        means = [sum(v) / len(v) for v in data]
        present = [m > 1.0 for m in means]
        centres = [round(m, 2) for m in means]
        windows = []
        for label, rate, n in (("10 ms", 1e6, 10000), ("1 s", 16000, 16000)):
            fr, data = dev.acquire(rate, n, (LO_RANGE, LO_RANGE), tuple(centres))
            chs = []
            for i, v in enumerate(data):
                s = stats(v)
                clip = min(v) < centres[i] - LO_HALF or max(v) > centres[i] + LO_HALF
                m = s["mean"]
                chs.append({"name": RAILS[i][0], "present": present[i], "clipped": clip,
                            "mean": round(m, 5), "pp_mV": round(1000 * s["pp"], 2),
                            "rms_mV": round(1000 * s["rms"], 3),
                            "env_mV": [[round(1000 * (a - m), 2), round(1000 * (b - m), 2)]
                                       for a, b in envelope(v, 600, 6)]})
            windows.append({"label": label, "rate": fr, "n": n, "window": n / fr, "ch": chs})
        return {"t": time.time(), "centres": centres, "windows": windows,
                "note": "5 V range centred on each rail, 0.3 mV steps"}
    finally:
        dev.give_scope()


# --------------------------------------------------------------------------- rail watch

class Watch:
    """Continuous record at 100 kS/s; min/max/mean per 80 ms window, kept for 2 hours."""

    RATE = 1e5
    WIN = 0.08
    KEEP = 90000

    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.stop_flag = threading.Event()
        self.clear()

    def clear(self):
        with getattr(self, "lock", threading.Lock()):
            self.points = []          # [seq, t, min5, max5, mean5, min3, max3, mean3]
            self.seq = 0
            self.events = []          # dips: {ch, t0, t1, min}
            self.lowest = [None, None]
            self.highest = [None, None]
            self.total = self.lost = self.corrupt = 0
            self.started = time.time() if getattr(self, "thread", None) and self.running else None
            self.error = None
            self._dip = [None, None]

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.running:
            return
        self.stop_flag.clear()
        ready = threading.Event()
        box = {}
        self.thread = threading.Thread(target=self._run, args=(ready, box), daemon=True)
        self.thread.start()
        ready.wait(15)
        if "error" in box:
            raise box["error"]

    def stop(self):
        self.stop_flag.set()
        if self.thread:
            self.thread.join(5)

    def _emit(self, t, mn, mx, sm, cnt):
        mean = [s / cnt for s in sm]
        with self.lock:
            self.seq += 1
            self.points.append([self.seq, round(t, 3)] +
                               [round(x, 4) for x in (mn[0], mx[0], mean[0], mn[1], mx[1], mean[1])])
            if len(self.points) > self.KEEP:
                del self.points[:len(self.points) - self.KEEP]
            for ch in (0, 1):
                if self.lowest[ch] is None or mn[ch] < self.lowest[ch][0]:
                    self.lowest[ch] = (mn[ch], t)
                if self.highest[ch] is None or mx[ch] > self.highest[ch][0]:
                    self.highest[ch] = (mx[ch], t)
                below = mn[ch] < DIP[ch]
                d = self._dip[ch]
                if below and d is None:
                    d = {"ch": ch, "rail": RAILS[ch][0], "t0": round(t - self.WIN, 3),
                         "t1": round(t, 3), "min": round(mn[ch], 4)}
                    self._dip[ch] = d
                    self.events.append(d)
                    del self.events[:-200]
                elif below:
                    d["t1"] = round(t, 3)
                    d["min"] = round(min(d["min"], mn[ch]), 4)
                elif d is not None:
                    self._dip[ch] = None

    def _run(self, ready, box):
        try:
            dev.take_scope("rail watch", timeout=10.0)
        except Busy as e:
            box["error"] = e
            ready.set()
            return
        try:
            dev.ensure()
            dev._frontend((50.0, 50.0), (0.0, 0.0))
            with dev.lock:
                dev.call("AnalogInFrequencySet", c_double(self.RATE))
                dev.call("AnalogInAcquisitionModeSet", c_int(3))      # record
                dev.call("AnalogInRecordLengthSet", c_double(0))     # 0 = until stopped
                dev.call("AnalogInTriggerSourceSet", c_byte(0))
                dev.cfg = None
                dev.call("AnalogInConfigure", c_int(1), c_int(1))
                fr = c_double()
                dev.call("AnalogInFrequencyGet", byref(fr))
            rate = fr.value
            per = max(1, int(round(rate * self.WIN)))
            with self.lock:
                self.started = time.time()
                self.error = None
                self.rate = rate
            ready.set()
            bufs = [(c_double * 400000)(), (c_double * 400000)()]
            sts, av, lo, co = c_byte(), c_int(), c_int(), c_int()
            mn, mx, sm, cnt = [9e9, 9e9], [-9e9, -9e9], [0.0, 0.0], 0
            skip = int(rate * 0.1)                 # drop the first 100 ms
            while not self.stop_flag.is_set():
                with dev.lock:
                    dev.call("AnalogInStatus", c_int(1), byref(sts))
                    dev.call("AnalogInStatusRecord", byref(av), byref(lo), byref(co))
                    k = min(av.value, 400000)
                    if k:
                        for ch in (0, 1):
                            dev.call("AnalogInStatusData", c_int(ch), bufs[ch], c_int(k))
                self.total += av.value
                self.lost += lo.value
                self.corrupt += co.value
                if k:
                    a, b = bufs[0][:k], bufs[1][:k]
                    now = time.time()
                    i = 0
                    if skip:
                        i = min(skip, k); skip -= i
                    while i < k:
                        take = min(per - cnt, k - i)
                        for ch, v in ((0, a), (1, b)):
                            seg = v[i:i + take]
                            mn[ch] = min(mn[ch], min(seg)); mx[ch] = max(mx[ch], max(seg))
                            sm[ch] += sum(seg)
                        cnt += take; i += take
                        if cnt >= per:
                            self._emit(now - (k - i) / rate, mn, mx, sm, cnt)
                            mn, mx, sm, cnt = [9e9, 9e9], [-9e9, -9e9], [0.0, 0.0], 0
                time.sleep(0.03)
        except Exception as e:
            with self.lock:
                self.error = str(e)
            box.setdefault("error", e)
            ready.set()
        finally:
            try:
                with dev.lock:
                    if dev.h is not None:
                        dev.call("AnalogInConfigure", c_int(0), c_int(0))
                        dev.call("AnalogInAcquisitionModeSet", c_int(0))
            except DeviceError:
                pass
            dev.cfg = None
            dev.give_scope()

    def snapshot(self, since):
        with self.lock:
            pts = [p for p in self.points[-self.KEEP:] if p[0] > since] if since else list(self.points)
            return {"running": self.running, "started": self.started, "error": self.error,
                    "seq": self.seq, "window_s": self.WIN, "rate": getattr(self, "rate", self.RATE),
                    "total": self.total, "lost": self.lost, "corrupt": self.corrupt,
                    "dip_below": DIP, "events": self.events[-50:], "n_events": len(self.events),
                    "lowest": self.lowest, "highest": self.highest, "points": pts}


watch = Watch()


# --------------------------------------------------------------------------- roll (strip chart)

class Roll:
    """Strip-chart recorder for the live scope: continuous record at 100 kS/s (same approach as
    the rail watch: no gaps, lost samples are counted), reduced to one point per 10 ms window:
    min, max, mean, AC rms and the number of rising edges, for both channels. Kept for 2 minutes."""

    RATE = 1e5
    WIN = 0.01
    KEEP = 12000

    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.stop_flag = threading.Event()
        self.rng = None
        self.clear()

    def clear(self):
        with self.lock:
            self.points = []     # [seq, t, mn1, mx1, mean1, ac1, rc1, mn2, mx2, mean2, ac2, rc2]
            self.seq = 0
            self.total = self.lost = self.corrupt = 0
            self.error = None
            self.clip_t = [0.0, 0.0]
            self.fine = [False, False]
            self.centre = [0.0, 0.0]

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, rng):
        rng = tuple(rng or ("auto", "auto"))
        if self.running and rng == self.rng:
            return
        self.stop()
        self.clear()
        self.rng = rng
        self.stop_flag.clear()
        ready = threading.Event()
        box = {}
        self.thread = threading.Thread(target=self._run, args=(ready, box, rng), daemon=True)
        self.thread.start()
        ready.wait(15)
        if "error" in box:
            raise box["error"]

    def stop(self):
        self.stop_flag.set()
        if self.thread:
            self.thread.join(5)

    def _window(self, t, chunks):
        row = [0, round(t, 3)]
        for ch, c in enumerate(chunks):
            n = len(c)
            mn, mx = min(c), max(c)
            m = sum(c) / n
            ac = math.sqrt(max(0.0, math.sumprod(c, c) / n - m * m))
            rc = 0
            if mx - mn > 0.05:
                lv = (mn + mx) / 2
                rc = sum(1 for a, b in zip(c, c[1:]) if a < lv <= b)
            if self.fine[ch] and (mn < self.centre[ch] - LO_HALF or mx > self.centre[ch] + LO_HALF):
                self.clip_t[ch] = t
            row += [round(mn, 4), round(mx, 4), round(m, 4), round(ac, 5), rc]
        with self.lock:
            self.seq += 1
            row[0] = self.seq
            self.points.append(row)
            if len(self.points) > self.KEEP:
                del self.points[:len(self.points) - self.KEEP]

    def _run(self, ready, box, rng):
        try:
            dev.take_scope("roll scope", timeout=10.0)
        except Busy as e:
            box["error"] = e
            ready.set()
            return
        try:
            dev.ensure()
            fine = [r == "5" for r in rng]
            cen = [0.0, 0.0]
            if any(fine):
                _, probe = dev.acquire(1e6, 10000)
                cen = [round(sum(v) / len(v), 2) for v in probe]
            with self.lock:
                self.fine, self.centre = fine, cen
            dev._frontend(tuple(LO_RANGE if f else 50.0 for f in fine),
                          tuple(c if f else 0.0 for f, c in zip(fine, cen)))
            with dev.lock:
                dev.call("AnalogInFrequencySet", c_double(self.RATE))
                dev.call("AnalogInAcquisitionModeSet", c_int(3))      # record
                dev.call("AnalogInRecordLengthSet", c_double(0))     # 0 = until stopped
                dev.call("AnalogInTriggerSourceSet", c_byte(0))
                dev.cfg = None
                dev.call("AnalogInConfigure", c_int(1), c_int(1))
                fr = c_double()
                dev.call("AnalogInFrequencyGet", byref(fr))
            rate = fr.value
            per = max(10, int(round(rate * self.WIN)))
            with self.lock:
                self.rate = rate
                self.started = time.time()
            ready.set()
            bufs = [(c_double * 400000)(), (c_double * 400000)()]
            sts, av, lo, co = c_byte(), c_int(), c_int(), c_int()
            pend = [[], []]
            skip = int(rate * 0.1)                 # drop the first 100 ms
            while not self.stop_flag.is_set():
                with dev.lock:
                    dev.call("AnalogInStatus", c_int(1), byref(sts))
                    dev.call("AnalogInStatusRecord", byref(av), byref(lo), byref(co))
                    k = min(av.value, 400000)
                    if k:
                        for ch in (0, 1):
                            dev.call("AnalogInStatusData", c_int(ch), bufs[ch], c_int(k))
                self.total += av.value
                self.lost += lo.value
                self.corrupt += co.value
                if k:
                    now = time.time()
                    i = min(skip, k)
                    skip -= i
                    for ch in (0, 1):
                        pend[ch].extend(bufs[ch][i:k])
                    while len(pend[0]) >= per:
                        chunks = [p[:per] for p in pend]
                        for p in pend:
                            del p[:per]
                        self._window(now - len(pend[0]) / rate, chunks)
                time.sleep(0.03)
        except Exception as e:
            with self.lock:
                self.error = str(e)
            box.setdefault("error", e)
            ready.set()
        finally:
            try:
                with dev.lock:
                    if dev.h is not None:
                        dev.call("AnalogInConfigure", c_int(0), c_int(0))
                        dev.call("AnalogInAcquisitionModeSet", c_int(0))
            except DeviceError:
                pass
            dev.cfg = None
            dev.give_scope()

    def snapshot(self, since):
        with self.lock:
            pts = [p for p in self.points if p[0] > since] if since else list(self.points)
            return {"running": self.running, "error": self.error, "seq": self.seq, "win": self.WIN,
                    "rate": getattr(self, "rate", self.RATE), "now": time.time(),
                    "total": self.total, "lost": self.lost, "corrupt": self.corrupt,
                    "rng": list(self.rng or ()), "fine": self.fine, "centre": self.centre,
                    "clip_t": self.clip_t, "points": pts}


roll = Roll()


# --------------------------------------------------------------------------- UART

class Uart:
    """UART decode on a DIO pin (DIO0 = J2 TX). A poller thread reads every 20 ms."""

    MAXBUF = 1 << 20

    def __init__(self):
        self.lock = threading.Lock()          # owns the UART engine (console vs self-test)
        self.buf = bytearray()
        self.base = 0                         # byte count before buf[0]
        self.baud = 115200
        self.pin = 0
        self.running = False
        self.armed = None                     # (gen, baud, pin) the engine is set to
        self.error = None
        self.overflows = 0
        self.parity = 0
        self.thread = None

    def _setup(self, baud, rx, tx=SELFTEST_PIN):
        dev.call("DigitalUartRateSet", c_double(baud))
        dev.call("DigitalUartTxSet", c_int(tx))         # never DIO0: that pin is the ESP32's TX
        dev.call("DigitalUartRxSet", c_int(rx))
        dev.call("DigitalUartBitsSet", c_int(8))
        dev.call("DigitalUartParitySet", c_int(0))
        dev.call("DigitalUartPolaritySet", c_int(0))
        dev.call("DigitalUartStopSet", c_double(1))
        n, par = c_int(), c_int()
        dev.call("DigitalUartRx", None, c_int(0), byref(n), byref(par))   # start receiving

    def start(self, baud=None, pin=None):
        if baud:
            self.baud = int(baud)
        if pin is not None:
            self.pin = int(pin)
        self.armed = None
        self.error = None
        self.running = True
        if not (self.thread and self.thread.is_alive()):
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False

    def clear(self):
        with self.lock:
            self.base += len(self.buf)
            self.buf = bytearray()
            self.overflows = self.parity = 0

    def _run(self):
        rx = create_string_buffer(8193)
        n, par = c_int(), c_int()
        while self.running:
            with self.lock:
                try:
                    dev.ensure()
                    want = (dev.gen, self.baud, self.pin)
                    if self.armed != want:
                        with dev.lock:
                            self._setup(self.baud, self.pin)
                        self.armed = want
                    with dev.lock:
                        dev.call("DigitalUartRx", rx, c_int(8192), byref(n), byref(par))
                    if n.value:
                        self.buf += rx.raw[:n.value]
                        if len(self.buf) > self.MAXBUF:
                            cut = len(self.buf) - self.MAXBUF
                            del self.buf[:cut]
                            self.base += cut
                    if par.value < 0:
                        self.overflows += 1
                    elif par.value > 0:
                        self.parity += 1
                    self.error = None
                except DeviceError as e:
                    self.error = str(e)
                    self.armed = None
            time.sleep(1.0 if self.error else 0.02)

    def read(self, since):
        with self.lock:
            end = self.base + len(self.buf)
            start = max(since, self.base) if since is not None else self.base
            data = bytes(self.buf[start - self.base:]) if start < end else b""
            return {"running": self.running, "baud": self.baud, "pin": self.pin,
                    "start": start, "end": end, "text": data.decode("latin-1"),
                    "overflows": self.overflows, "parity_errors": self.parity,
                    "error": self.error}

    def selftest(self):
        """Loopback on DIO15 (send and receive on the same unconnected pin)."""
        msg = b"AD3 loopback %06d rst: ets \r\n" % random.randrange(10 ** 6)
        if self.running and self.pin == SELFTEST_PIN:
            t0 = time.time()
            while not self.armed and time.time() - t0 < 2:      # console still arming
                time.sleep(0.01)
        if self.running and self.pin == SELFTEST_PIN and self.armed:
            # Console is listening on the loopback pin: send into it and look for the text
            # there, so the test covers the console's own receive path.
            with self.lock:
                mark = self.base + len(self.buf)
                with dev.lock:
                    dev.call("DigitalUartTxSet", c_int(SELFTEST_PIN))
                    dev.call("DigitalUartTx", None, c_int(0))
                    dev.call("DigitalUartTx", msg, c_int(len(msg)))
            t0 = time.time()
            got = ""
            while time.time() - t0 < 0.5 + 20 * len(msg) / self.baud:
                time.sleep(0.02)
                got = self.read(mark)["text"]
                if msg.decode() in got:
                    break
            return {"pass": msg.decode() in got, "sent": msg.decode(), "got": got,
                    "baud": self.baud, "pin": SELFTEST_PIN, "via": "console"}
        with self.lock:
            dev.ensure()
            got = b""
            try:
                with dev.lock:
                    self._setup(self.baud, SELFTEST_PIN, SELFTEST_PIN)
                    dev.call("DigitalUartTx", None, c_int(0))
                    dev.call("DigitalUartTx", msg, c_int(len(msg)))
                buf = create_string_buffer(8193)
                n, par = c_int(), c_int()
                t0 = time.time()
                while time.time() - t0 < 0.3 + 20 * len(msg) / self.baud and len(got) < len(msg):
                    time.sleep(0.01)
                    with dev.lock:
                        dev.call("DigitalUartRx", buf, c_int(8192), byref(n), byref(par))
                    got += buf.raw[:n.value]
            finally:
                self.armed = None                       # the console re-arms on its next poll
                try:
                    with dev.lock:
                        dev.call("DigitalOutReset")         # release DIO15
                        dev.call("DigitalOutConfigure", c_int(0))
                except DeviceError:
                    pass
        return {"pass": got == msg, "sent": msg.decode(), "got": got.decode("latin-1"),
                "baud": self.baud, "pin": SELFTEST_PIN}


uart = Uart()


# --------------------------------------------------------------------------- results

results_lock = threading.Lock()


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def load_results():
    try:
        with open(RESULTS) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"run_started": None, "steps": {}}


def save_results(data):
    os.makedirs(BENCH_DIR, exist_ok=True)
    tmp = RESULTS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, RESULTS)


def save_step(body):
    sid = str(body.get("id", "")).strip()
    if not sid:
        raise ValueError("step id missing")
    with results_lock:
        data = load_results()
        if not data.get("run_started"):
            data["run_started"] = now_iso()
        rec = {k: v for k, v in body.items() if k != "id"}
        rec["ts"] = now_iso()
        data.setdefault("steps", {})[sid] = rec
        save_results(data)
        return {"id": sid, "ts": rec["ts"]}


def reset_run():
    with results_lock:
        data = load_results()
        archived = None
        if data.get("steps"):
            runs = os.path.join(BENCH_DIR, "runs")
            os.makedirs(runs, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            archived = os.path.join(runs, f"results-{stamp}.json")
            with open(archived, "w") as f:
                json.dump(data, f, indent=1)
        save_results({"run_started": now_iso(), "steps": {}})
        return {"archived": os.path.relpath(archived, REPO) if archived else None}


# --------------------------------------------------------------------------- HTTP

def rng_arg(v):
    v = list(v or ("auto", "auto"))
    if len(v) != 2 or any(x not in ("auto", "50", "5") for x in v):
        raise ValueError("rng must be two of auto, 50, 5")
    return v


def scope_request(q):
    """/api/scope?window=0.01&rng=auto,auto&trig=1r&level=0.0&wait=10
    trig: off | 1r | 1f | 2r | 2f (channel, rising/falling). hyst: trigger hysteresis V.
    wait: single shot, seconds."""
    window = float(q.get("window", 0.01))
    rng = rng_arg(q.get("rng", "auto,auto").split(","))
    t = q.get("trig", "off")
    trig = None
    if t != "off":
        if t not in ("1r", "1f", "2r", "2f"):
            raise ValueError("trig must be off, 1r, 1f, 2r or 2f")
        trig = (int(t[0]) - 1, t[1])
    wait = min(max(float(q.get("wait", 0)), 0), 30) or None
    hyst = min(max(float(q.get("hyst", 0.1)), 0.005), 2.0)
    return scope.frame(window, rng, trig, float(q.get("level", 0)), wait, hyst)


class Handler(BaseHTTPRequestHandler):
    server_version = "bench/1"

    def log_message(self, fmt, *args):
        if self.command == "POST" or (len(args) > 1 and not str(args[1]).startswith("2")):
            sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n) or b"{}")

    def _run(self, fn):
        try:
            self._send(200, {"ok": True, **fn()})
        except Busy as e:
            self._send(409, {"ok": False, "busy": True, "error": str(e)})
        except DeviceError as e:
            self._send(503, {"ok": False, "device": False, "error": str(e)})
        except (ValueError, KeyError, TypeError) as e:
            self._send(400, {"ok": False, "error": f"bad request: {e}"})
        except Exception as e:                                       # keep serving
            self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[-1] for k, v in parse_qs(u.query).items()}
        p = u.path
        if p in ("/", "/index.html"):
            try:
                with open(PAGE, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, b"bench_page.html missing", "text/plain")
        elif p == "/debug":
            try:
                with open(os.path.join(HERE, "debug_page.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, b"debug_page.html missing", "text/plain")
        elif p == "/api/board/set":
            # forward a setting (speaker test, mode, mute) to the board's /set
            import urllib.request, urllib.parse
            try:
                with open(os.path.join(REPO, "firmware", ".ota_host")) as f:
                    host = f.read().strip()
                qs = urllib.parse.urlencode({k: v for k, v in q.items() if k in ("test", "mode", "mute", "drive", "sound")})
                with urllib.request.urlopen(f"http://{host}/set?{qs}", timeout=2) as r:
                    self._send(200, {"ok": True, "board": json.loads(r.read().decode())})
            except Exception as e:
                self._send(200, {"ok": False, "error": f"{type(e).__name__}: {e}"})
        elif p == "/api/board":
            # the board's own /status, fetched here so the page needs no cross-origin request
            import urllib.request
            try:
                with open(os.path.join(REPO, "firmware", ".ota_host")) as f:
                    host = f.read().strip()
            except OSError:
                host = "surround"
            try:
                with urllib.request.urlopen(f"http://{host}/status", timeout=1.5) as r:
                    d = json.loads(r.read().decode())
                self._send(200, {"ok": True, "host": host, "board": d})
            except Exception as e:
                self._send(200, {"ok": False, "host": host, "error": f"{type(e).__name__}: {e}"})
        elif p == "/wiring":
            try:
                with open(os.path.join(HERE, "wiring_guide.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, b"wiring_guide.html missing", "text/plain")
        elif p == "/api/status":
            self._run(lambda: {"device": dev.status(), "watch": watch.running,
                               "roll": roll.running, "uart": uart.running, "uart_baud": uart.baud,
                               "results": os.path.relpath(RESULTS, REPO)})
        elif p == "/api/scope":
            self._run(lambda: scope_request(q))
        elif p == "/api/roll":
            self._run(lambda: roll.snapshot(int(q.get("since", 0))))
        elif p == "/api/watch":
            self._run(lambda: watch.snapshot(int(q.get("since", 0))))
        elif p == "/api/uart":
            self._run(lambda: uart.read(int(q["since"]) if "since" in q else None))
        elif p == "/api/results":
            self._run(lambda: load_results())
        else:
            self._send(404, {"ok": False, "error": "no such endpoint"})

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            b = self._body()
        except ValueError:
            return self._send(400, {"ok": False, "error": "body is not JSON"})
        routes = {
            "/api/railcheck": rail_check,
            "/api/ripple": ripple,
            "/api/watch/start": lambda: (watch.start(), {"running": True})[1],
            "/api/watch/stop": lambda: (watch.stop(), {"running": False})[1],
            "/api/watch/clear": lambda: (watch.clear(), {})[1],
            "/api/roll/start": lambda: (roll.start(rng_arg(b.get("rng"))), {"running": True})[1],
            "/api/roll/stop": lambda: (roll.stop(), {"running": False})[1],
            "/api/roll/clear": lambda: (roll.clear(), {})[1],
            "/api/uart/start": lambda: (uart.start(b.get("baud"), b.get("pin")),
                                        {"running": True, "baud": uart.baud, "pin": uart.pin})[1],
            "/api/uart/stop": lambda: (uart.stop(), {"running": False})[1],
            "/api/uart/clear": lambda: (uart.clear(), {})[1],
            "/api/uart/selftest": uart.selftest,
            "/api/results/step": lambda: save_step(b),
            "/api/results/reset": reset_run,
            "/api/device/release": lambda: (dev.drop("released: reopens on the next request"),
                                            {"released": True})[1],
        }
        if p not in routes:
            return self._send(404, {"ok": False, "error": "no such endpoint"})
        if p == "/api/device/release":
            watch.stop(); roll.stop(); uart.stop()
        self._run(routes[p])


def main():
    port = 8791
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    os.makedirs(BENCH_DIR, exist_ok=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True

    def bye(*_):
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, bye)
    signal.signal(signal.SIGINT, bye)
    print(f"bench page on http://127.0.0.1:{port}/  (results: {os.path.relpath(RESULTS, REPO)})",
          flush=True)
    try:
        httpd.serve_forever()
    finally:
        watch.stop()
        roll.stop()
        uart.stop()
        time.sleep(0.1)
        dev.drop()
        httpd.server_close()
        print("AD3 closed, server stopped", flush=True)


if __name__ == "__main__":
    main()
