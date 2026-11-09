#!/usr/bin/env python3
"""Characteristic impedance of the traces on this board, and what it implies
for series termination.

The board is DOUBLE SIDED: a signal trace runs on the bottom face with the
ground pour beside it at the netclass clearance, and the top face is a ground
plane 1.6 mm of FR4 away. That is a coplanar waveguide with a ground plane under
it (conductor-backed CPW), not plain microstrip and not the open CPW of the old
single-sided board. With a 0.50 mm gap and a 1.6 mm substrate the side grounds
still carry most of the field, so the plane lowers Z0 only a little; what it
buys is an unbroken return path under every clock.

    k  = a / b,                       a = w/2,   b = w/2 + s
    k1 = tanh(pi a / 2h) / tanh(pi b / 2h)
    q  = K(k')/K(k) * K(k1)/K(k1')
    eps_eff = (1 + eps_r q) / (1 + q)
    Z0 = 60 pi / sqrt(eps_eff) / (K(k)/K(k') + K(k1)/K(k1'))

Wadell, "Transmission Line Design Handbook", section 3.4.3; Simons, "Coplanar
Waveguide Circuits", chapter 3. K is the complete elliptic integral of the first
kind, computed by the arithmetic-geometric mean.

    python3 tools/impedance.py
"""
import math

EPS_R = 4.3          # FR4 at audio/low RF; 4.2-4.6 across suppliers
T_CU = 0.035         # mm, 1 oz copper
H_SUB = 1.6          # mm, bottom-face trace to top-face plane
CLEARANCE = 0.50     # mm, the cnc-fine netclass gap (0.8 mm ball mill, 0.44 mm channel)
TRACK = 0.90         # mm, the ESP netclass: the width of the module's pads


def ellip_k(k):
    """Complete elliptic integral of the first kind, by the AGM."""
    a, g = 1.0, math.sqrt(1.0 - k * k)
    while abs(a - g) > 1e-13:
        a, g = (a + g) / 2.0, math.sqrt(a * g)
    return math.pi / (2.0 * a)


def k_ratio(k):
    """K(k)/K(k')."""
    return ellip_k(k) / ellip_k(math.sqrt(1.0 - k * k))


def z0_cpw(w, s, eps_r=EPS_R, h=H_SUB):
    """Impedance and propagation delay of a coplanar trace over a ground plane."""
    a, b = w / 2.0, w / 2.0 + s
    k = a / b
    k1 = math.tanh(math.pi * a / (2 * h)) / math.tanh(math.pi * b / (2 * h))
    q = k_ratio(k1) / k_ratio(k)
    eps_eff = (1.0 + eps_r * q) / (1.0 + q)
    z0 = 60.0 * math.pi / math.sqrt(eps_eff) / (k_ratio(k) + k_ratio(k1))
    tpd = math.sqrt(eps_eff) / 299.792458 * 1000.0  # ps per mm (c = 299.79 mm/ns)
    return z0, tpd, eps_eff


def r_dc(w, length_mm, t=T_CU):
    """DC resistance of a trace, milliohms."""
    rho = 1.72e-8                                   # ohm.m, annealed copper
    area = w * t * 1e-6                             # m^2
    return rho * (length_mm * 1e-3) / area * 1000.0


if __name__ == "__main__":
    print(f"FR4 eps_r {EPS_R}, {H_SUB} mm thick, coplanar gap {CLEARANCE} mm, ground plane on the far face\n")
    print(f"{'width':>7} {'Z0':>8} {'tpd':>9} {'C':>9}   {'crit. length, tr=2ns':>22}")
    print(f"{'mm':>7} {'ohm':>8} {'ps/mm':>9} {'pF/mm':>9}   {'mm':>22}")
    for w in (0.3, 0.5, 0.9, 1.0, 1.5):
        z0, tpd, _ = z0_cpw(w, CLEARANCE)
        c = tpd / z0                                # pF/mm
        crit = (2000.0 / 6.0) / tpd                 # tr/6 rule
        print(f"{w:7.1f} {z0:8.1f} {tpd:9.2f} {c:9.3f}   {crit:22.0f}")

    print(f"\nMill tolerance on the chosen {TRACK} mm I2S trace:")
    for dw, ds, label in ((0, 0, "nominal"), (-0.03, +0.03, "mill cuts wide"),
                          (+0.03, -0.03, "mill cuts narrow")):
        z0, _, _ = z0_cpw(TRACK + dw, CLEARANCE + ds)
        print(f"  w {TRACK+dw:4.2f}  s {CLEARANCE+ds:4.2f}   Z0 {z0:5.1f} ohm   ({label})")
    lo, _, _ = z0_cpw(TRACK, CLEARANCE, 4.6)
    hi, _, _ = z0_cpw(TRACK, CLEARANCE, 4.2)
    print(f"  eps_r 4.2-4.6                Z0 {hi:5.1f}-{lo:.1f} ohm")

    z0, tpd, _ = z0_cpw(TRACK, CLEARANCE)
    print(f"\nSeries source termination for the {TRACK} mm signal track, "
          f"Z0 = {z0:.0f} ohm  (Rs = Z0 - Zdriver):")
    for name, zout, note in (("DIR9001 CMOS out", 25, "R1/R2/R3, datasheet gives only a DC bound"),
                             ("DIR9001 CMOS out", 40, "  same, if the driver is weaker"),
                             ("ESP32 GPIO, default 20 mA drive", 40, "R4/R5"),
                             ("ESP32 GPIO, 40 mA drive", 25, "  if drive strength is raised")):
        print(f"  {name:34s} Zout {zout:3d}  ->  Rs {z0-zout:5.0f} ohm   {note}")

    print("\nPower rail DC drop, 1.0 mm POWER class, 1 oz copper:")
    for ln in (50, 100, 150):
        r = r_dc(1.0, ln)
        print(f"  {ln:3d} mm  R {r:5.1f} mOhm   drop at 0.5 A: {r*0.5:5.1f} mV")
