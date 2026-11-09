#!/usr/bin/env python3
"""Generate hardware/BUILD-NOTES.md from the routed board.

    python3 tools/kpy.py tools/build_notes.py hardware/surround.kicad_pcb

The parts that can drift from the artwork are read off the board: the leads that
have to be soldered on both faces, the top-face runs, the pin map and whether
anything is still open (tools/check_board.py does the proving).
"""
import sys
from pathlib import Path
import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_board
import surround_board as cfg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "hardware/BUILD-NOTES.md"

GPIO = {"1": "GND", "2": "3V3", "3": "EN", "4": "IO36", "5": "IO39", "6": "IO34", "7": "IO35", "8": "IO32",
        "9": "IO33", "10": "IO25", "11": "IO26", "12": "IO27", "13": "IO14", "14": "IO12", "15": "GND",
        "16": "IO13", "23": "IO15", "24": "IO2", "25": "IO0", "26": "IO4", "27": "IO16", "28": "IO17",
        "29": "IO5", "30": "IO18", "31": "IO19", "33": "IO21", "34": "IO3 (RXD0)", "35": "IO1 (TXD0)",
        "36": "IO22", "37": "IO23", "38": "GND"}
SIGNAL = {"DIR_BCK": "DIR9001 BCK in (and both DACs)", "DIR_LRCK": "DIR9001 LRCK in (and both DACs)",
          "Net-(U1-IO35)": "DIR9001 DATA in", "Net-(U1-IO2)": "DIN front DAC", "Net-(U1-IO13)": "DIN surround DAC",
          "XSMT": "XSMT both DACs", "POT": "Pot wiper (ADC1)", "USER": "USER button", "BOOT": "BOOT button",
          "LED": "Status LED", "EN": "RESET", "RXD0": "UART RX", "TXD0": "UART TX"}
WHY = {"R7": "surround left ring resistor", "R9": "surround right ring resistor",
       "R11": "XSMT pull-down: ties the copper between the two sockets",
       "R13": "LM317 divider", "C6": "7805 input cap", "C7": "+5V cap: ties the copper LRCK and BCK fence in",
       "C9": "ESP32 bypass: its ground lead is module pin 1's way to the plane",
       "D1": "status LED cathode", "D4": "power LED cathode: ties the copper between the two data lines",
       "U2": "7805 centre leg", "TP1": "wire loop: ties the reset parts' ground", "TP2": "wire loop: ties module pin 38"}


def top_runs(board):
    runs = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.F_Cu:
            runs[t.GetNetname()] = runs.get(t.GetNetname(), 0.0) + pcbnew.ToMM(t.GetLength())
    return runs


def main(path):
    board = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    problems, twice = check_board.analyse(board, cfg.TOP_OK)
    bb = board.GetBoardEdgesBoundingBox()
    size = f"{pcbnew.ToMM(bb.GetWidth()) - 0.1:.1f} x {pcbnew.ToMM(bb.GetHeight()) - 0.1:.1f} mm"
    by_net = {}
    for ref, num, net in twice:
        by_net.setdefault(net, []).append((ref, num))
    runs = top_runs(board)
    u1 = next(fp for fp in board.GetFootprints() if fp.GetReference() == "U1")
    pins = sorted(((int(p.GetNumber()), p.GetNetname()) for p in u1.Pads()
                   if p.GetNetname() in SIGNAL), key=lambda x: x[0])
    L = []
    w = L.append
    w("# Build notes\n")
    w("Generated from `hardware/surround.kicad_pcb` by `tools/build_notes.py`.")
    w("Do not edit by hand; re-run the tool after any change to the board.\n")
    w(f"The board is {size}, copper on both faces, no vias and no wire links.\n")
    if problems:
        w("## NOT READY TO CUT\n")
        w("`tools/check_board.py` found connections that cannot be made:\n")
        for p in problems:
            w(f"- {p}")
        w("")
    w("## Before cutting\n")
    w("- **WROOM-32 castellations on the ball mill.** Never cut before. Cut")
    w("  `hardware/coupon` first and meter every neighbouring pad pair.")
    w("- **First double-sided board on these rules.** The top face is cut after the flip, so")
    w("  it depends on the dowel registration. The smallest top-face feature is the 0.5 mm")
    w("  ring round a hole, and every ring is cut round a 1.6 mm or larger pad.")
    w("- **DAC modules: measured**, 31.0 x 17.1 mm, 1x6 and 1x9 rows. Only the 3.5 mm jack's")
    w("  overhang (5.5 mm assumed) is a guess; the modules now sit 25.4 mm apart, which leaves")
    w("  8.3 mm for it.")
    w("- **DIR9001 board: from the seller's drawing** (LHY AUDIO DIR9001-I2S). Check the wire")
    w("  order against the board's I2S-OUT silk before soldering the pigtail.\n")
    w("## Milling\n")
    w("SRM-CAM, profile `SRM-20 0.8 mm ball mill`, **Double-sided**, dowel pins. Load")
    w("`hardware/production/gerbers`; do not mirror anything yourself.\n")
    w("1. Air pass, then the two dowel holes.")
    w("2. Bottom face: holes, then traces. This face has the WROOM-32 pads and every signal.")
    w("3. Flip left to right onto the pins, re-zero Z.")
    w("4. Top face: traces. It is a ground plane; the mill cuts a ring round each hole that is")
    w("   not ground, and the supply runs below.")
    w("5. Cut-out last. Then the silkscreen on the laser from")
    w("   `hardware/production/surround_silk_top.dxf`, top face, not mirrored.\n")
    w("## Leads soldered on both faces\n")
    w("The holes are not plated. The two faces meet only where a lead is soldered on the top")
    w("as well as the bottom, so **these joints are the board's vias**. Every other lead is")
    w("soldered on the bottom only. All of them are parts the iron reaches from the top:")
    w("resistors, disc capacitors, LEDs, the 7805 and two wire loops.\n")
    w("| Net | Lead | What it does |")
    w("|---|---|---|")
    for net in sorted(by_net, key=lambda n: (n == "GND", n)):
        for ref, num in sorted(by_net[net]):
            what = WHY.get(ref, "ground tie") if net == "GND" else f"carries {net} between the faces"
            w(f"| `{net}` | {ref} pad {num} | {what} |")
    w("")
    w(f"{len(twice)} joints in all. Solder each one on the top, let it flow round the lead, and")
    w("meter it to the plane (ground leads) or to the far end of its run (supply leads).")
    w("TP1 and TP2 are bare holes: fit a U of solid wire through each as a scope ground loop")
    w("and solder it on both faces.\n")
    w("## Top-face copper\n")
    w("| Net | Length | Route |")
    w("|---|---:|---|")
    route = {"+5V": "from R19 up the east side of the DAC parts to C7, R18 and R17",
             "+3V3": "from C9 over the module to R16, then up to R15"}
    for net in sorted(runs):
        w(f"| `{net}` | {runs[net]:.0f} mm | {route.get(net, '')} |")
    w("")
    w("Everything else on the top is ground. No clock, data or audio net leaves the bottom face.\n")
    w("## Pin map\n")
    w("The GPIOs follow the board: each signal leaves the castellation that faces its copper.\n")
    w("| Signal | GPIO | Module pin |")
    w("|---|---|---:|")
    for n, net in pins:
        w(f"| {SIGNAL[net]} | {GPIO[str(n)]} | {n} |")
    w("")
    w("IO2 and IO15 are strapping pins. IO2 drives only a DAC input, which leaves it low at")
    w("reset as download mode needs. IO15 has only the USER button: do not hold it during")
    w("reset or the ROM boot log is silenced. IO14 (BCK) is JTAG TMS until the firmware")
    w("starts, which is harmless without a clock on IO13.\n")
    w("## Assembly order\n")
    w("1. U1 first, flat on the bottom face. Tack two opposite corners, then drag-solder the")
    w("   castellations. Leave the centre pad unsoldered.")
    w("2. Meter neighbouring pins for bridges, especially 1/2/3, 23/24 and 34/35.")
    w("3. The parts in the table above next, soldered on both faces, while nothing is in the way:")
    w("   R7, R9 and R11 sit under the DAC modules.")
    w("4. Then the low parts, the sockets, the cans and the regulators last. C2, C3 and C4 have")
    w("   their leads formed out to 5 mm; C11 to 3.5 mm.")
    w("5. Power only: 5.0 V at U2, and 3.2 to 3.3 V at U1 pin 2, before any module goes in.")
    w("6. U2 and U3 stand on the south edge with their tabs outward: a heatsink on U3 may")
    w("   overhang the edge. U2 runs without one.")
    w("7. DIR9001 pigtail on A2. Two pairs cross against the cable's order: BCLK with LRCK, and")
    w("   +5V with GND. The silk names each hole; go by the names, not the order.\n")
    w("Flashing: 3.3 V UART cable on J2 (TX, RX, GND as marked; cable RX to TX). Hold BOOT, tap")
    w("RESET, release.\n")
    w("## Module straps\n")
    w("Set these on the modules before fitting them.\n")
    w("| Module | Strap | Value |")
    w("|---|---|---|")
    w("| DIR9001 | FMT DIP switch (FMT0, FMT1) | both H: 24-bit I2S |")
    w("| DIR9001 | PSCK DIP switch | any: MCLK is not used |")
    w("| DIR9001 | input toggle | optical or coax, as wired to the panel |")
    w("| DIR9001 | pigtail to A2 | DATA, BCLK, LRCK, +5V, GND to the holes of the same name; MCLK may stay loose; trim it short |")
    w("| PCM5102 (both) | SCK | to GND via the socket: 3-wire BCK-PLL mode |")
    w("| PCM5102 (both) | FMT | LOW: I2S |")
    w("| PCM5102 (both) | FLT | LOW: normal latency filter |")
    w("| PCM5102 (both) | DEMP | LOW: de-emphasis off |")
    w("| PCM5102 (both) | XSMT | its H jumper removed: meter which one beeps to the XSMT hole |")
    w("| PCM5102 (both) | headers | male 1x6 + 1x9 soldered from the COMPONENT side, spacer on that side: the module mounts face down |")
    w("")
    w("## Parts\n")
    w("Same parts as the single-sided board; only footprints and positions changed.\n")
    w("| Part | Qty | Source |")
    w("|---|---:|---|")
    for row in (("ESP32-WROOM-32", "1", "shop: EKB basement stock, ask for it"),
                ("DIR9001-I2S board (LHY AUDIO / Lobamop), with XH pigtail", "1", "buy: bought, Amazon B0HDT4M8QX"),
                ("M3 standoffs for the DIR9001 board", "4", "shop"),
                ("PCM5102 module (AYWHP)", "2", "buy: bought, 3 in hand with one spare"),
                ("RCA panel jack, TRS panel jack", "2 + 2", "buy: order list"),
                ("9 V 1 A adapter, centre positive", "1", "buy: order list"),
                ("10K potentiometer", "1", "shop"),
                ("LM7805, LM317T, TO-220 heatsink", "1 + 1 + 1", "shop"),
                ("1N5817, 1N4003", "1 + 1", "shop"),
                ("43R2 (R1-R5)", "5", "shop"),
                ("100R (R6-R9)", "4", "shop, 1 at home"),
                ("10k (R11, R14, R15)", "3", "home"),
                ("10R (R17-R19)", "3", "home 2, shop 1"),
                ("1k (R16, R20)", "2", "home 1, shop 1"),
                ("332R, 243R, 392R", "1 each", "shop"),
                ("470 uF (C1)", "1", "home: 16 V, fine on 3V3"),
                ("100 uF (C2-C4)", "3", "shop"),
                ("10 uF 50 V (C5, C8)", "2", "home"),
                ("100 nF disc (C6, C7, C9)", "3", "shop"),
                ("1 uF 50 V (C11)", "1", "shop"),
                ("3 mm LED", "2", "shop"),
                ("6 mm pushbutton", "3", "shop"),
                ("2-pole, 3-pole screw terminal", "3 + 2", "shop"),
                ("Female header 1x6, 1x9", "2 + 2", "shop (1x9 cut from a longer strip)"),
                ("Male header 1x6, 1x9", "2 + 2", "shop, for the DAC modules"),
                ("Male header 1x3", "2", "shop"),
                ("Solid wire for TP1, TP2", "2 loops", "home"),
                ("Double-sided copper-clad, 1.6 mm", "about 115 x 85 mm", "shop: ask; the dowels need 11 mm of waste beyond the outline")):
        w("| " + " | ".join(row) + " |")
    w("")
    w("## Panel parts\n")
    w("J1 takes the 9 V adapter (centre positive; `+9V` and `GND` are marked). J3 and J4 are the")
    w("RCA fronts, J5 and J6 the TRS surrounds. J7 is the volume pot: 3V3, wiper, GND.")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(twice)} double joints, {len(runs)} top-face nets, "
          f"{'NOT READY' if problems else 'ready'}")


if __name__ == "__main__":
    main(sys.argv[1])
