"""Preview renders of the enclosure. Run: python3 enclosure/render_preview.py [view.png ...]

Tessellates the FreeCAD shapes and hands them to Blender (Cycles) as plain
meshes. Writes render/*.png. The lid is drawn as clear acrylic. The DIR9001 module, the heatsink, the DAC modules,
the standoffs and the panel parts are drawn as the ASSUMED envelopes from design.py.
"""
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent
BLENDER = '''
import bpy, json, sys
from mathutils import Vector
job = json.load(open(sys.argv[-2])); out = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
colors = {'base': (.045, .05, .058, 1), 'lid': (.92, .96, .98, 1), 'button': (.80, .33, .08, 1),
          'pcb': (.62, .36, .16, 1), 'part': (.10, .10, .11, 1), 'metal': (.66, .67, .69, 1),
          'module': (.20, .09, .30, 1), 'module_pcb': (.04, .30, .12, 1), 'ghost': (.25, .6, .35, 1),
          'terminal': (.10, .32, .62, 1), 'led': (.9, .15, .1, 1), 'gold': (.83, .62, .22, 1),
          'black': (.02, .02, .022, 1), 'red': (.6, .05, .04, 1), 'ghost_metal': (.66, .67, .69, 1), 'ground': (.42, .42, .42, 1)}
mats = {}
for k, c in colors.items():
    m = bpy.data.materials.new(k); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = c
    b.inputs['Metallic'].default_value = 1 if k in ('metal', 'gold') else 0
    b.inputs['Roughness'].default_value = .3 if k in ('metal', 'gold') else .55
    if k.startswith('ghost'):
        b.inputs['Alpha'].default_value = .3
    if k == 'lid':                       # clear acrylic
        b.inputs['Transmission Weight'].default_value = 1.0; b.inputs['Roughness'].default_value = .03; b.inputs['IOR'].default_value = 1.49
    mats[k] = m
for r in job['rows']:
    d = bpy.data.meshes.new(r['name']); d.from_pydata([[c / 1000 for c in v] for v in r['vertices']], [], r['faces'])
    d.materials.append(mats[r['mat']])
    o = bpy.data.objects.new(r['name'], d); bpy.context.scene.collection.objects.link(o)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, job['ground'] / 1000)); bpy.context.object.data.materials.append(mats['ground'])
s = bpy.context.scene; s.render.engine = 'CYCLES'; s.cycles.samples = 32; s.cycles.use_denoising = True
s.view_settings.view_transform = 'Standard'; s.render.resolution_x, s.render.resolution_y = job['res']
w = bpy.data.worlds.new('w'); s.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (1, 1, 1, 1); w.node_tree.nodes['Background'].inputs[1].default_value = .22
t = Vector(job['target'])
for loc, e, size in [((-.35, -.45, .6), 9, .6), ((.5, .1, .45), 4, .8), ((.0, .55, .3), 2.5, .8)]:
    l = bpy.data.lights.new('l', 'AREA'); l.energy = e; l.size = size
    o = bpy.data.objects.new('l', l); o.location = t + Vector(loc); s.collection.objects.link(o)
    o.rotation_euler = (t - o.location).to_track_quat('-Z', 'Y').to_euler()
cam = bpy.data.objects.new('c', bpy.data.cameras.new('c')); s.collection.objects.link(cam); s.camera = cam
cam.location = job['cam']; cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = job['lens']
s.render.filepath = out; bpy.ops.render.render(write_still=True)
'''

def main():
    import design as m
    base, lid, button, cradle, knob = m.shapes()
    inside = [(n, s, g) for n, s, g in m.references()]
    cx, cy = (m.XW + m.XE) / 2, (m.YS + m.YN) / 2

    def rows(parts):
        out = []
        for n, s, mat in parts:
            vs, fs = s.tessellate(.08)
            out.append({'name': n, 'mat': mat, 'vertices': [[v.x, v.y, v.z] for v in vs], 'faces': fs})
        return out

    def lift(s, dz):
        c = s.copy(); c.translate(m.V(0, 0, dz)); return c

    def view(parts, cam, target=(cx, cy, 14), lens=78, res=(1600, 1100)):
        return {'rows': rows(parts), 'ground': m.Z_BOT, 'cam': [c / 1000 for c in cam], 'target': [c / 1000 for c in target], 'lens': lens, 'res': list(res)}

    shell = [('Base', base, 'base'), ('Lid_Plate', lid, 'lid'), ('User_Button', button, 'button')]
    small = [('Pot_Cradle', cradle, 'button'), ('Knob', knob, 'black')]
    panel = [r for r in inside if r in m.panel_parts() or r[0].endswith(('_jack', '_keep_clear')) or r[0].startswith('Volume')]
    guts = [r for r in inside if r not in panel]
    sockets = [r for r in guts if r[0] in ('DIR9001_toslink', 'DIR9001_rca', 'DIR9001_toggle')]
    # exploded: lid and button up, board and modules half way
    exploded = [('Base', base, 'base'), ('Lid_Plate', lift(lid, 125), 'lid'), ('User_Button', lift(button, 150), 'button')]
    exploded += [(n, lift(s, 60), g) for n, s, g in guts] + panel + small
    # cut-away: everything sliced on the vertical plane through the USER button, seen from the front
    keep = m.box(-500, -500, -100, m.P['SW3']['centre'][0], 500, 200)
    def sliced(parts):
        out = []
        for n, s, g in parts:
            if s.BoundBox.XMax > m.P['SW3']['centre'][0]:
                s = s.common(keep)
            if s.Volume > 1e-6:
                out.append((n, s, g))
        return out
    cut = sliced(shell[:2] + guts + panel) + [shell[2]] + small
    views = {
        'closed-front.png': view(shell + small + guts + panel, (cx + 330, cy - 330, 270)),
        'closed-rear.png': view(shell + small + guts + panel, (cx - 360, cy - 250, 230)),
        'open-top.png': view([shell[0]] + small + guts + panel, (cx - 1, cy - 110, 560), lens=78),
        'open-rear.png': view([shell[0]] + small + guts + panel, (cx - 330, cy - 280, 330)),
        'exploded.png': view(exploded, (cx + 430, cy - 470, 420), target=(cx, cy, 62), lens=95, res=(1500, 1500)),
        'cutaway.png': view(cut, (cx + 420, cy - 110, 170), target=(cx - 30, cy, 14), lens=78),
        'closed-top.png': view(shell + small + guts + panel, (cx - 1, cy - 110, 560), lens=78),
        'pot-mount.png': view([('Base', base.common(m.box(70, -40, -30, 200, 4, 100)), 'base')] + small + [r for r in panel if r[0] == 'Volume_pot'], (m.XE - 75, m.POT_Y + 95, 95), target=(m.XE - 6, m.POT_Y, m.Z_POT - 8), lens=70),
        'rear-panel.png': view(shell + small + guts + panel, (m.XW - 330, cy, 60), target=(m.XW, cy, 14), lens=110, res=(1600, 900)),
        'base-empty.png': view([shell[0]], (cx - 1, cy - 250, 430), lens=70),
    }
    (ROOT / 'render').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        script = Path(t) / 'r.py'; script.write_text(BLENDER)
        for name, job in views.items():
            if sys.argv[1:] and name not in sys.argv[1:]:
                continue
            data = Path(t) / 'd.json'; data.write_text(json.dumps(job))
            subprocess.run(['blender', '-b', '--factory-startup', '--python', str(script), '--', str(data), str(ROOT / 'render' / name)],
                           check=True, stdout=subprocess.DEVNULL)
            print('wrote', name, flush=True)

main()
