"""Interference and clearance checks for the enclosure. Run: python3 enclosure/validate.py

Solid against solid (BRep common volume) for the printed parts, the acrylic lid
plate, the KiCad STEP
export of the board, and the stand-in envelopes for everything the STEP lacks.
The envelopes use ASSUMED sizes, so a clean result proves the model is
self-consistent, not that the real parts fit.
"""
import json
import design as m

base, lid, button = m.shapes()
printed = [('Base', base), ('Lid_Plate', lid), ('User_Button', button)]
refs = m.references()
report = {'scope': 'Nominal rigid geometry. Board parts from the KiCad STEP export; modules, terminals, heatsink, '
                   'DIR9001 module, standoffs and panel parts are envelopes with assumed or photo-estimated sizes. Wires are not modelled.',
          'collisions': [], 'pairs_checked': 0}

def check(la, a, lb, b):
    report['pairs_checked'] += 1
    if not a.BoundBox.intersect(b.BoundBox):
        return
    v = a.common(b).Volume
    if v > 1e-3:
        row = {'pair': f'{la} / {lb}', 'volume_mm3': round(v, 3)}
        report['collisions'].append(row); print('COLLISION', row, flush=True)

# 1. printed parts against everything inside and against each other
for pn, ps in printed:
    for rn, rs, _ in refs:
        check(pn, ps, rn, rs)
check('Base', base, 'Lid_Plate', lid); check('Lid_Plate', lid, 'User_Button', button); check('Base', base, 'User_Button', button)

# 2. the things inside against each other: board parts, module, panel parts, envelopes
board = [(n, s) for n, s, g in m.board_solids() + m.carrier_standoffs()]
env = [(n, s) for n, s, g in m.envelopes()]
other = [(n, s) for n, s, g in m.dir_module() + m.panel_parts()]
for i, (an, a) in enumerate(other):
    for bn, b in board + env:
        check(an, a, bn, b)
    for bn, b in other[i + 1:]:
        if an.startswith('DIR9001') and bn.startswith('DIR9001'):
            continue
        if {an, bn} == {'Volume_pot', 'Volume_knob'}:
            continue
        check(an, a, bn, b)
hs = dict(env)['U3_heatsink_envelope']
for bn, b in board:
    # the heatsink is bolted to U3; any other board part it reaches is a clash
    bb = b.BoundBox
    u3 = m.P['U3']['bbox']
    if bn != 'Board' and 'standoff' not in bn and not (bb.XMin > u3[0] - 1 and bb.XMax < u3[2] + 1 and bb.YMax < u3[3] + 1):
        check('U3_heatsink_envelope', hs, bn, b)

# 3. clearances worth knowing
def gap(a, b):
    return round(a.distToShape(b)[0], 2)
inside = m.Part.makeCompound([s for _, s in board + env])
dirc = m.Part.makeCompound([s for n, s, _ in m.dir_module() if 'standoff' not in n])
jacks = m.Part.makeCompound([s for n, s, _ in m.panel_parts() if n.endswith('_jack')])
pot = dict((n, s) for n, s, _ in m.panel_parts())['Volume_pot']
wroom = [s for n, s in board if n == 'WROOM32'][0]
a2 = m.P['A2']['centre']
report['clearance_mm'] = {
    'tallest_carrier_part_to_plate': round(m.Z_LID - inside.BoundBox.ZMax, 2),
    'board_and_parts_to_base_excluding_standoffs': round(min(inside.BoundBox.XMin - m.XW, m.XE - inside.BoundBox.XMax,
                                                               inside.BoundBox.YMin - m.YS, m.YN - inside.BoundBox.YMax), 2),
    'wroom_underside_to_floor': round(wroom.BoundBox.ZMin - m.Z_FLOOR, 2),
    'antenna_tip_to_front_wall_plastic': round(m.XE + (m.WALL - m.ANTENNA_WALL) - wroom.BoundBox.XMax, 2),
    'antenna_to_nearest_lid_insert': round(min((max(m.BOARD_X - x, x - wroom.BoundBox.XMax, 0) ** 2 + max(wroom.BoundBox.YMin - y, y - wroom.BoundBox.YMax, 0) ** 2) ** .5
                                               for x, y in m.LID_POSTS), 2),
    'antenna_to_board_screw_H2': round(((m.BOARD_X - m.HOLES['H2']['xy'][0]) ** 2 + (m.HOLES['H2']['xy'][1] - wroom.BoundBox.YMax) ** 2) ** .5, 2),
    'antenna_to_volume_pot': gap(wroom, pot),
    'heatsink_envelope_to_plate': gap(hs, lid),
    'dir9001_to_carrier_parts_below_it': round(m.DIR_Z0 - max(sh.BoundBox.ZMax for _, sh in board + env if sh.BoundBox.XMin < m.DIR_X1 and sh.BoundBox.YMax > m.DIR_Y0 and sh.BoundBox.YMin < m.DIR_Y1), 2),
    'dir9001_assumed_top_to_plate': gap(dirc, lid),
    'jack_bodies_to_carrier_and_parts': gap(jacks, inside),
    'jack_bodies_to_plate': gap(jacks, lid),
    'jack_bodies_to_dir9001': gap(jacks, dirc),
    'pot_to_heatsink_envelope': gap(pot, hs),
}
i2s = (m.DIR_X1, m.DIR_Y0 + m.DIR_I2S_U)   # I2S-OUT connector: on the east edge after the turn, position scaled from the seller drawing
report['wiring_room_mm'] = {
    'rear_bay_depth_board_edge_to_wall': round(m.REAR_BAY, 2),
    'rear_bay_free_behind_assumed_jack_bodies': round(m.REAR_BAY - m.JACK_BODY_DEPTH, 2),
    'south_bay_depth_board_edge_to_wall': round(-m.YS, 2),
    'free_height_under_module_over_terminals': round(m.DIR_Z0 - (m.Z_BOARD + m.TERMINAL_H), 2),
    'jack_bodies_to_module_pillars': gap(jacks, m.Part.makeCompound([m.cyl(x, y, m.Z_FLOOR, m.PILLAR_D, m.DIR_Z0 - m.Z_FLOOR) for x, y in m.dir_pillars()])),
    'pigtail_straight_line_I2S_OUT_to_A2': round(((a2[0] - i2s[0]) ** 2 + (a2[1] - i2s[1]) ** 2 + (m.DIR_Z0 - m.Z_BOARD) ** 2) ** .5, 1),
    'pot_wire_straight_line_J7_to_pot': round(((m.XE - m.P['J7']['centre'][0]) ** 2 + (m.POT_Y - m.P['J7']['centre'][1]) ** 2) ** .5, 1),
}
report['clearance_mm']['toggle_lever_tip_past_recess_floor'] = round(m.DIR_TOGGLE_TIP_OVERHANG - m.DIR_EDGE_GAP - (m.WALL - m.PANEL_RECESS), 2)
report['clearance_mm']['rca_barrel_past_recess_floor'] = round(m.DIR_CONN_OVERHANG - m.DIR_EDGE_GAP - (m.WALL - m.PANEL_RECESS), 2)
sw3 = m.P['SW3']['centre']
vx = m.vent_xs()
under = [n for n, sh in board + env + [(n, s) for n, s, _ in m.dir_module()]
         if sh.BoundBox.XMax > vx[0] - m.VENT_W / 2 and sh.BoundBox.XMin < vx[-1] + m.VENT_W / 2
         and sh.BoundBox.YMax > m.VENT_Y0 and sh.BoundBox.YMin < m.VENT_Y1 and n != 'Board']
report['lid_plate'] = {
    'plate_bears_on': 'wall top all round and four corner bosses',
    'screw_hole_centre_to_plate_edge': round(m.POST / 2 + m.WALL - m.PLATE_INSET, 2),
    'plastic_round_insert_pilot_min': round((m.POST - m.INSERT_PILOT_D) / 2, 2),
    'acrylic_between_vent_slots': round(m.VENT_PITCH - m.VENT_W, 2),
    'vent_slots_x_range': [round(vx[0] - m.VENT_W / 2, 2), round(vx[-1] + m.VENT_W / 2, 2)],
    'vent_slots_y_range': [m.VENT_Y0, m.VENT_Y1],
    'vent_slot_nearest_to_module_edge': round(vx[0] - m.VENT_W / 2 - m.DIR_X1, 2),
    'vent_slots_to_inside_of_south_wall': round(m.VENT_Y0 - m.YS, 2),
    'parts_under_the_vent_slots': len(under),
    'highest_part_under_the_vent_slots_to_plate': round(m.Z_LID - max([sh.BoundBox.ZMax for n, sh in board + env if n in under] or [0]), 2),
    'user_button_stem_to_plate_hole_radial': round((m.BTN_HOLE_D - m.BTN_D) / 2, 2),
    'user_button_lift_before_collar_meets_plate': m.BTN_LIFT,
    'user_button_skirt_to_board': round(button.BoundBox.ZMin - m.Z_BOARD, 2),
    'pin_hole_to_switch_plunger_drop': round(m.Z_LID - (m.Z_BOARD + m.TACT_TOP_ABOVE_BOARD), 2),
}
report['notes'] = [
    'The DIR9001 module covers the west screw terminals J3 to J6: lift it off to reach their screws.',
    'The vent slots are over the regulators and the south bay, not over the DIR9001 module. The highest part under them (the heatsink allowance) is 10.5 mm below the plate; the bare TO-220 tabs are about 17 mm below.',
    'The module is held at three of its four holes (two printed pillars and the standoff on H3). The fourth hole is over bare board.',
]
report['result'] = 'no interference' if not report['collisions'] else f"{len(report['collisions'])} interfering pairs"
(m.ROOT / 'cad' / 'validation.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
