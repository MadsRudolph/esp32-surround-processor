# ESP32 4.0 surround processor -- carrier board placement, as intent.
#
# Flow left -> right:  5 V in + DIR9001 (S/PDIF)  ->  ESP32  ->  two DACs -> panel jacks
#
#   POWER    J1 barrel -> F1 -> C1 bulk -> FB1..3 + C2..4, one filtered 5 V per module
#   SPDIF    A2 DIR9001 socket, R1-R3 33 R series at the driver end
#   MCU      A1 DevKitC upright; audio row (IO32/34/35/36/39 in, IO25/26/27/33 out) is the
#            left socket, control row (IO18/19/21/22/23) the right one, toward the bottom headers
#   OUT      A3 front DAC with R4 + R11, A4 surround DAC with R5 and the 100 R TRS network
#
# Floor, measured before anything moved (place_floor.py --pours): 0 with GND poured.
# The unpoured spine is +5V at 6 pads.  Panel parts (encoder, RCA, TRS) land on a
# header and screw terminals anchored on the bottom and right edges; H1-H4 are locked.

board(flow="x", grid=1.27, gap=1.27, block_gap=3.81, band_gap=3.81,
      margin=7.0, cross_order="barycentre")

lock("H1", "H2", "H3", "H4")

# external I/O on the edges: power left, audio out right, controls bottom
anchor("J1",  edge="left",   at=0.12)
anchor("J3",  edge="right",  at=0.14)
anchor("J4",  edge="right",  at=0.32)
anchor("J5",  edge="right",  at=0.60)
anchor("J6",  edge="right",  at=0.82)
anchor("SW1", edge="bottom", at=0.42)
anchor("J7",  edge="bottom", at=0.62)

# A1 stays upright (rows along y): its audio row is the LEFT socket, facing the
# DIR9001; the DAC nets cross under the module through the 18 mm socket corridor.
# DAC carriers stay upright too: header row on top, wire pads at the bottom.

# --- band 1: power and the S/PDIF receiver -----------------------------------
block("power", core="C1", axis="x",
      dress=[part("F1", at="w")],
      ring=["FB1", "C2", "FB2", "C3", "FB3", "C4"])
block("spdif", core="A2", axis="y",
      dress=[part("R1", at="e"), part("R2", at="e"), part("R3", at="e")])

# --- band 2: the MCU with its status LED -------------------------------------
block("mcu", core="A1", axis="y", dress=[part("R10", at="s"), part("D1", at="s")])

# --- band 3: the DACs, series resistors on the ESP32 side, TRS network on the jack side
block("dac_front", core="A3", axis="y",
      dress=[part("R4", at="w"), part("R11", at="w")])
block("dac_surr", core="A4", axis="y", dress=[part("R5", at="w")])
# the 100 R impedance-balancing network sits against the TRS terminals, in its own band
row("trs_net", parts=["R6", "R7", "R8", "R9"], axis="y")

band("in",  blocks=["power", "spdif"])
band("mcu", blocks=["mcu"])
band("out", blocks=["dac_front", "dac_surr"])
band("trs", blocks=["trs_net"])
