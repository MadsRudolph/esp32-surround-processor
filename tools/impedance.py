#!/usr/bin/env python3
"""Characteristic impedance of the traces on this board, and what it implies
for series termination.

The board is SINGLE SIDED: copper on B.Cu only, signal traces with the GND
pour beside them at the netclass clearance, and NOTHING on the other side of
the FR4. So a trace here is a coplanar waveguide WITHOUT a ground plane (CPW),
not microstrip. Using a microstrip formula on this board is the classic wrong
answer; it would predict ~110 ohm for 1 mm on 1.6 mm FR4 and it does not apply,
because there is no return conductor under the trace at all.

For CPW with no backside metal and a substrate much thicker than (w + 2s), half
the field is in air and half in the dielectric:

    eps_eff = (eps_r + 1) / 2
    k  = a / b,   a = w/2,   b = w/2 + s
    Z0 = (30*pi / sqrt(eps_eff)) * K(k') / K(k)

with the complete elliptic integral ratio from Hilberg's closed form, exact to
better than 1e-7 over the whole range. Wadell, "Transmission Line Design
Handbook", section 3.4; Simons, "Coplanar Waveguide Circuits", chapter 2.

    python3 tools/impedance.py
"""
import math

EPS_R = 4.3          # FR4 at audio/low RF; 4.2-4.6 across suppliers
T_CU = 0.035         # mm, 1 oz copper
CLEARANCE = 0.50     # mm, the cnc-fine netclass gap (0.8 mm ball mill, 0.44 mm channel)
TRACK = 0.90         # mm, the ESP netclass: the width of the module's pads


def k_ratio(k):
    """K(k')/K(k) by Hilberg's closed form."""
    kp = math.sqrt(1.0 - k * k)
    if k <= 1 / math.sqrt(2):
        return math.log(2 * (1 + math.sqrt(kp)) / (1 - math.sqrt(kp))) / math.pi
    return math.pi / math.log(2 * (1 + math.sqrt(k)) / (1 - math.sqrt(k)))


def z0_cpw(w, s, eps_r=EPS_R):
    """Impedance and propagation delay of a coplanar trace, no backside metal."""
    eps_eff = (eps_r + 1.0) / 2.0
    a, b = w / 2.0, w / 2.0 + s
    z0 = (30.0 * math.pi / math.sqrt(eps_eff)) * k_ratio(a / b)
    tpd = math.sqrt(eps_eff) / 299.792458 * 1000.0  # ps per mm (c = 299.79 mm/ns)
    return z0, tpd, eps_eff


def r_dc(w, length_mm, t=T_CU):
    """DC resistance of a trace, milliohms."""
    rho = 1.72e-8                                   # ohm.m, annealed copper
    area = w * t * 1e-6                             # m^2
    return rho * (length_mm * 1e-3) / area * 1000.0


if __name__ == "__main__":
    print(f"FR4 eps_r {EPS_R}, coplanar gap {CLEARANCE} mm (0.8 mm ball mill)\n")
    print(f"{'width':>7} {'Z0':>8} {'tpd':>9} {'C':>9}   {'crit. length, tr=2ns':>22}")
    print(f"{'mm':>7} {'ohm':>8} {'ps/mm':>9} {'pF/mm':>9}   {'mm':>22}")
    for w in (0.3, 0.5, 0.8, 1.0, 1.5):
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
