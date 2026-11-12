"""Renders of the surround carrier board as it is built: bare milled copper on top, a
hand-applied green mask underneath, and in one shot the DIR9001 board stacked above it
(Cycles, headless).

    blender -b --factory-startup --python hardware/renders/render.py -- [--shot NAME] [--preview]

Shots: hero, hero_stacked, top_34, bottom_34, top, bottom. No --shot renders all six into this
folder. --preview renders half size at a quarter of the samples into build/.
Needs build/board.glb (render.sh makes it) and board/surround.kicad_pcb.
"""
import bpy, bmesh, sys, math, re, argparse
from pathlib import Path
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'
PCB = HERE / 'board' / 'surround.kicad_pcb'

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ALL = ['hero', 'hero_stacked', 'top_34', 'bottom_34', 'top', 'bottom']
ap.add_argument('--shot', choices=ALL, action='append')
ap.add_argument('--preview', action='store_true')
ap.add_argument('--blend', action='store_true', help='also save build/<shot>.blend')
args = ap.parse_args(argv)

MM = 0.001
MILL_DEPTH = 0.08       # mm, the isolation cut (README: 0.8 mm ball mill at 0.08 mm deep)
T_BOARD = 1.51          # mm, laminate thickness in the export

# Leads soldered on the top face as well (hardware/BUILD-NOTES.md). TP1 and TP2 are
# wire loops that are not modelled, so they get no joint here.
TOP_JOINTS = {('C9', '1'), ('R15', '1'), ('R16', '1'), ('C7', '1'), ('R17', '1'), ('R18', '1'),
              ('R19', '1'), ('C6', '2'), ('C7', '2'), ('C9', '2'), ('D1', '1'), ('D4', '1'),
              ('R11', '2'), ('R13', '2'), ('R7', '2'), ('R9', '2'), ('U2', '2')}
NO_SOLDER = ('MountingHole',)
LED_COLOUR = {'D1': (0.10, 1.0, 0.12), 'D4': (1.0, 0.04, 0.02)}   # status green, power red: a guess
LEAD_STUB = 1.6         # mm of lead left under the board after trimming
# Stock models on a wider hole pitch than they were drawn for (formed leads on the real
# parts): their straight legs would come down beside the holes.
LEGS_OFF_HOLES = {'D1', 'D4', 'C11'}

# From the photos of the built board.
STANDOFF_AF = 5.5       # mm across flats, black M3 hex standoffs (estimate)
FOOT_H = 10.0           # mm, standoffs under the carrier (estimate)
TOP_HEX_H = 8.0         # mm, the hex on top of each mounting hole (estimate)
# DIR9001-I2S board, stacked over the DAC modules on the standoff at H3. All estimates
# scaled from the photos against the 73.2 mm carrier; see README.
DIR_W, DIR_L, DIR_T = 64.0, 48.0, 1.6     # north-south, east-west, thickness
DIR_GAP = 17.0          # mm from the carrier's top face to the underside of the DIR board
DIR_HOLE_SW = (4.0, 4.0)                  # its south-west hole: from the south edge, from the west edge
WIRE_COLOURS = [(0.01, 0.01, 0.01), (0.55, 0.02, 0.02), (0.80, 0.50, 0.02), (0.03, 0.06, 0.40),
                (0.02, 0.22, 0.10), (0.75, 0.75, 0.72)]
# Parts whose real colour differs from the stock model: ref -> (stock colour, material key)
RECOLOUR = {'J1': ((0.095, 0.420, 0.167), 'term_green'), 'J3': ((0.095, 0.420, 0.167), 'term_green'),
            'J4': ((0.095, 0.420, 0.167), 'term_green'), 'J5': ((0.095, 0.420, 0.167), 'term_black'),
            'J6': ((0.095, 0.420, 0.167), 'term_black'), 'C1': ((0.017, 0.134, 0.487), 'cap_blue'),
            'R13': ((0.754, 0.464, 0.207), 'res_tan')}


# ---------------------------------------------------------------- materials
def principled(name, base, metallic=0.0, rough=0.5, coat=0.0, coat_rough=0.05,
               spec=0.5, transmission=0.0, emission=None, strength=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = coat_rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Transmission Weight'].default_value = transmission
    b.inputs['IOR'].default_value = ior
    if emission:
        b.inputs['Emission Color'].default_value = (*emission, 1)
        b.inputs['Emission Strength'].default_value = strength
    return m


def mask_factor(nt, ref):
    """1 where the hand-applied green mask covers the board: the whole bottom face, right up
    to the WROOM-32. Coordinates are the board's own (ref empty), so the mask stays on
    the bottom face when the board is turned over."""
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.object = ref
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    def math(op, a, b=None):
        n = nt.nodes.new('ShaderNodeMath'); n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]
    return math('LESS_THAN', sep.outputs['Z'], 0.0), tc


def add_mask(m, ref, laminate=False):
    """Lay the green mask over a material on the bottom face. Brushed on by hand: glossy,
    uneven, the copper showing through as a lighter green than the milled channels."""
    nt = m.node_tree
    out = nt.nodes['Material Output']
    base = nt.nodes['Principled BSDF']
    fac, tc = mask_factor(nt, ref)
    g = nt.nodes.new('ShaderNodeBsdfPrincipled')
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 45
    n.inputs['Detail'].default_value = 6; n.inputs['Roughness'].default_value = 0.65
    nt.links.new(tc.outputs['Object'], n.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.30; ramp.color_ramp.elements[1].position = 0.72
    if laminate:
        ramp.color_ramp.elements[0].color = (0.000, 0.018, 0.010, 1)
        ramp.color_ramp.elements[1].color = (0.000, 0.035, 0.020, 1)
    else:
        ramp.color_ramp.elements[0].color = (0.000, 0.120, 0.060, 1)
        ramp.color_ramp.elements[1].color = (0.010, 0.360, 0.185, 1)
        g.inputs['Metallic'].default_value = 0.35
    nt.links.new(n.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], g.inputs['Base Color'])
    g.inputs['Roughness'].default_value = 0.28
    g.inputs['Coat Weight'].default_value = 1.0; g.inputs['Coat Roughness'].default_value = 0.10
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.5; bump.inputs['Distance'].default_value = 0.00015
    n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 160
    nt.links.new(tc.outputs['Object'], n2.inputs['Vector'])
    nt.links.new(n2.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], g.inputs['Normal'])
    nt.links.new(bump.outputs['Normal'], g.inputs['Coat Normal'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(fac, mix.inputs[0])
    nt.links.new(base.outputs[0], mix.inputs[1]); nt.links.new(g.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


def textured(name, image, rough=0.3, coat=0.5):
    m = principled(name, (1, 1, 1), rough=rough, coat=coat, coat_rough=0.08)
    nt = m.node_tree
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(str(HERE / 'models' / image))
    t.extension = 'EXTEND'
    nt.links.new(t.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    return m


def copper_material():
    """Bare copper clad as it leaves the mill and a scouring pad: satin, fine random
    scratches, slight tarnish from handling."""
    m = principled('bare_copper', (0.95, 0.47, 0.25), metallic=1, rough=0.30)
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    # tarnish: large soft patches, a little darker and redder
    n1 = nt.nodes.new('ShaderNodeTexNoise')
    n1.inputs['Scale'].default_value = 28; n1.inputs['Detail'].default_value = 5
    n1.inputs['Roughness'].default_value = 0.6
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[0].color = (0.78, 0.33, 0.16, 1)
    ramp.color_ramp.elements[1].position = 0.70; ramp.color_ramp.elements[1].color = (0.96, 0.49, 0.26, 1)
    nt.links.new(tc.outputs['Object'], n1.inputs['Vector'])
    nt.links.new(n1.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    # roughness follows the tarnish, 0.24 .. 0.40
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['To Min'].default_value = 0.40; mr.inputs['To Max'].default_value = 0.24
    nt.links.new(n1.outputs['Fac'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], b.inputs['Roughness'])
    # scratches: noise stretched hard along two directions
    def scratch(angle, scale):
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Rotation'].default_value = (0, 0, angle)
        mp.inputs['Scale'].default_value = (scale, scale * 0.012, scale)
        n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 1.0
        n.inputs['Detail'].default_value = 3
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n
    a, c = scratch(0.5, 60000), scratch(-0.9, 45000)
    add = nt.nodes.new('ShaderNodeMath'); add.operation = 'ADD'
    nt.links.new(a.outputs['Fac'], add.inputs[0]); nt.links.new(c.outputs['Fac'], add.inputs[1])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.12; bump.inputs['Distance'].default_value = 0.00002
    nt.links.new(add.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m


def add_noise_bump(m, scale, strength, distance):
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = 4
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = distance
    nt.links.new(tc.outputs['Object'], n.inputs['Vector'])
    nt.links.new(n.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m


def board_materials(ref):
    mats = {'copper': add_mask(copper_material(), ref)}
    # Laminate where the mill has taken the copper off, and on the cut edge.
    # In the photos the 0.44 mm channels read as dark lines, so the laminate is kept dark.
    mats['fr4'] = add_mask(add_noise_bump(principled('fr4', (0.20, 0.16, 0.07), rough=0.75, spec=0.3),
                                          9000, 0.4, 0.00002), ref, laminate=True)
    # Fiber-laser legend on bare copper: a dark, matte oxide mark.
    mats['silk'] = principled('laser_mark', (0.035, 0.022, 0.018), metallic=0.3, rough=0.75, spec=0.2)
    mats['solder'] = add_noise_bump(principled('solder', (0.80, 0.80, 0.78), metallic=1, rough=0.20),
                                    2500, 0.2, 0.00005)
    # stand-in DAC module
    mats['pcm5102_pcb'] = textured('module_back', 'pcm5102_back.png')
    mats['dir_pcb'] = textured('dir9001_board', 'dir9001_top.png', rough=0.25)
    mats['term_green'] = principled('terminal_green', (0.17, 0.30, 0.13), rough=0.45)
    mats['term_black'] = principled('terminal_black', (0.014, 0.014, 0.015), rough=0.45)
    mats['cap_blue'] = principled('sleeve_blue', (0.02, 0.08, 0.42), rough=0.28, coat=0.7)
    mats['res_tan'] = principled('resistor_tan', (0.60, 0.42, 0.24), rough=0.35, coat=0.4)
    mats['nylon'] = principled('nylon_black', (0.018, 0.018, 0.020), rough=0.5)
    mats['bore'] = principled('bore', (0.002, 0.002, 0.002), rough=0.9)
    mats['black'] = principled('plastic_black', (0.012, 0.012, 0.013), rough=0.42, coat=0.15)
    mats['white'] = principled('plastic_white', (0.80, 0.80, 0.76), rough=0.45)
    mats['red'] = principled('plastic_red', (0.55, 0.02, 0.02), rough=0.35, coat=0.3)
    mats['nickel'] = principled('nickel', (0.80, 0.79, 0.76), metallic=1, rough=0.18)
    mats['can'] = principled('can', (0.75, 0.75, 0.74), metallic=1, rough=0.35)
    mats['pcm5102_plastic'] = principled('module_header', (0.012, 0.012, 0.013), rough=0.42, coat=0.15)
    mats['pcm5102_pins'] = principled('module_pins', (1.0, 0.76, 0.38), metallic=1, rough=0.2)
    mats['pcm5102_parts'] = principled('module_parts', (0.02, 0.02, 0.022), rough=0.45)
    mats['pcm5102_jack'] = principled('module_jack', (0.015, 0.015, 0.017), rough=0.38, coat=0.2)
    return mats


def component_material(m):
    """Proper shading for the colours KiCad's library models carry."""
    b = m.node_tree.nodes.get('Principled BSDF')
    if b is None:
        return
    c = tuple(b.inputs['Base Color'].default_value)[:3]
    def near(t, tol=0.02):
        return all(abs(a - x) < tol for a, x in zip(c, t))
    def set_(base, metallic, rough, coat=0.0, spec=0.5, transmission=0.0):
        b.inputs['Base Color'].default_value = (*base, 1)
        b.inputs['Metallic'].default_value = metallic
        b.inputs['Roughness'].default_value = rough
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = 0.1
        b.inputs['Specular IOR Level'].default_value = spec
        b.inputs['Transmission Weight'].default_value = transmission
    if near((0.019, 0.018, 0.018)):            # black epoxy / plastic
        set_((0.012, 0.012, 0.013), 0, 0.42, coat=0.15)
    elif near((0.645, 0.638, 0.572)):          # tinned leads, tabs, the module's shield
        set_((0.78, 0.78, 0.76), 1, 0.25)
    elif near((0.619, 0.152, 0.019)):          # ceramic disc caps, dipped
        set_((0.70, 0.48, 0.05), 0, 0.38, coat=0.4)
    elif near((0.754, 0.464, 0.207)):          # axial resistors: blue 1 % metal film (E96 values)
        set_((0.16, 0.36, 0.62), 0, 0.33, coat=0.5)
    elif near((0.448, 0.010, 0.004)):          # LED lens, replaced per part below
        set_((0.75, 0.10, 0.02), 0, 0.08, transmission=0.6)
    elif near((0.017, 0.134, 0.487)):          # electrolytic sleeve
        set_((0.012, 0.016, 0.035), 0, 0.30, coat=0.6)
    elif near((0.435, 0.398, 0.316)):          # electrolytic can top
        set_((0.75, 0.75, 0.74), 1, 0.35)
    elif near((0.709, 0.504, 0.210)):          # gold pin plating
        set_((1.0, 0.76, 0.38), 1, 0.18)
    elif near((0.778, 0.770, 0.626)):          # DO-41 band
        set_((0.75, 0.75, 0.72), 0, 0.5)
    elif near((0.095, 0.420, 0.167)):          # screw terminal body
        set_((0.03, 0.18, 0.55), 0, 0.4)
    elif near((0.453, 0.059, 0.008)):          # WROOM-32 antenna trace
        set_((0.85, 0.62, 0.30), 1, 0.3)
    elif near((0.006, 0.013, 0.073)):          # WROOM-32 board
        set_((0.010, 0.012, 0.016), 0, 0.35, coat=0.4)
    else:
        b.inputs['Metallic'].default_value = 0
        b.inputs['Roughness'].default_value = 0.45


def led_material(name, col):
    return principled('led_' + name, col, rough=0.05, transmission=0.5, emission=col,
                      strength=0.12, ior=1.5, coat=0.5, coat_rough=0.02)


# ---------------------------------------------------------------- board
def through_hole_pads():
    """(ref, pad, x, y, min pad size) in mm, page coordinates, from the board copy."""
    s = PCB.read_text(encoding='utf-8')
    out = []
    for blk in re.split(r'\n\t\(footprint "', s)[1:]:
        name = blk.split('"', 1)[0].split(':')[-1]
        if name.startswith(NO_SOLDER):
            continue
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
        m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', blk)
        fx, fy, fa = float(m.group(1)), float(m.group(2)), math.radians(float(m.group(3) or 0))
        for p in re.finditer(r'\(pad "([^"]*)" thru_hole \w+\s*\(at ([-\d.]+) ([-\d.]+)[^)]*\)\s*'
                             r'\(size ([-\d.]+) ([-\d.]+)\)', blk):
            px, py = float(p.group(2)), float(p.group(3))
            x = fx + px * math.cos(fa) + py * math.sin(fa)
            y = fy - px * math.sin(fa) + py * math.cos(fa)
            out.append((ref, p.group(1), x, y, min(float(p.group(4)), float(p.group(5)))))
    return out


def solder_joints(parent, mat, z_top, z_bot):
    """A small fillet at every soldered lead: all of them underneath, and on top the
    leads the build notes list. Generic shapes; the real joints are hand soldered."""
    bm = bmesh.new()
    seg = 20
    def fillet(x, y, r, z, sign):
        h = 0.95
        prof = [(r, 0.0), (r * 0.62, h * 0.22), (0.42, h * 0.62), (0.33, h)]
        rings = []
        for pr, pz in prof:
            rings.append([bm.verts.new(((x + pr * math.cos(2 * math.pi * i / seg)) * MM,
                                        (-y + pr * math.sin(2 * math.pi * i / seg)) * MM,
                                        (z + sign * pz) * MM)) for i in range(seg)])
        for a, b in zip(rings, rings[1:]):
            for i in range(seg):
                j = (i + 1) % seg
                bm.faces.new((a[i], a[j], b[j], b[i]) if sign > 0 else (a[i], b[i], b[j], a[j]))
        bm.faces.new(rings[-1] if sign > 0 else rings[-1][::-1])
    for ref, pad, x, y, size in through_hole_pads():
        r = size * 0.45
        fillet(x, y, r, z_bot, -1)
        if (ref, pad) in TOP_JOINTS:
            fillet(x, y, r, z_top, +1)
    # WROOM-32 castellations: a small bead on each edge pad, bare through the mask
    blk = next(b for b in re.split(r'\n\t\(footprint "', PCB.read_text(encoding='utf-8'))[1:]
               if '"Reference" "U1"' in b)
    m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', blk)
    fx, fy, fa = float(m.group(1)), float(m.group(2)), math.radians(float(m.group(3) or 0))
    for p in re.finditer(r'\(pad "[^"]*" smd \w+\s*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\s*'
                         r'\(size ([-\d.]+) ([-\d.]+)\)', blk):
        px, py, pa = float(p.group(1)), float(p.group(2)), math.radians(float(p.group(3) or 0))
        sx, sy = float(p.group(4)), float(p.group(5))
        if max(sx, sy) > 3:                      # the centre pad is left unsoldered
            continue
        x = fx + px * math.cos(fa) + py * math.sin(fa)
        y = fy - px * math.sin(fa) + py * math.cos(fa)
        # the bead sits on the outer half of the pad and climbs the castellation
        long = Vector((math.cos(pa), math.sin(pa))) if sx > sy else Vector((-math.sin(pa), math.cos(pa)))
        out = Vector((x - fx, -(y - fy)))
        long = long if long.dot(out) > 0 else -long
        c = Vector((x * MM, -y * MM)) + long * (0.28 * max(sx, sy) * MM)
        mx = (Matrix.Translation((c.x, c.y, z_bot * MM)) @ Matrix.Rotation(pa, 4, 'Z')
              @ Matrix.Diagonal((sx * 0.50 * MM, sy * 0.50 * MM, 0.85 * MM, 1)))
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1.0, matrix=mx)
    me = bpy.data.meshes.new('solder')
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    o = bpy.data.objects.new('solder', me)
    bpy.context.scene.collection.objects.link(o)
    o.parent = parent
    return o


def W(x, y, z):
    """Page millimetres (KiCad x, y; z above the carrier's bottom face) to scene metres."""
    return Vector((x * MM, -y * MM, z * MM))


def new_obj(name, bm, mat, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def box(name, x0, y0, z0, x1, y1, z1, mat):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(W((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
                          @ Matrix.Diagonal((abs(x1 - x0) * MM, abs(y1 - y0) * MM, abs(z1 - z0) * MM, 1)))
    return new_obj(name, bm, mat)


def rod(name, a, b, r, mat, segments=28):
    """Cylinder (or hex bar with segments=6) from page point a to page point b, radius r mm."""
    pa, pb = W(*a), W(*b)
    d = pb - pa
    bm = bmesh.new()
    m = Matrix.Translation((pa + pb) / 2) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r * MM, radius2=r * MM,
                          depth=d.length, matrix=m)
    return new_obj(name, bm, mat, smooth=segments > 8)


def set_uv(o, f):
    """UVs from page coordinates: f(x, y) -> (u, v)."""
    uv = o.data.uv_layers.new(name='page') if not o.data.uv_layers else o.data.uv_layers[0]
    for loop in o.data.loops:
        w = o.matrix_world @ o.data.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = f(w.x / MM, -w.y / MM)


def footprints():
    """ref -> (footprint name, x, y) from the board copy."""
    out = {}
    for blk in re.split(r'\n\t\(footprint "', PCB.read_text(encoding='utf-8'))[1:]:
        m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)', blk)
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
        out[ref] = (blk.split('"', 1)[0].split(':')[-1], float(m.group(1)), float(m.group(2)))
    return out


def standoffs(bm, fps, stacked):
    """Black hex standoffs at the four mounting holes: one under the board as a foot and
    a hex on top, as in the photos. Stacked, the one at H3 carries the DIR9001 board."""
    r = STANDOFF_AF / 2 / math.cos(math.pi / 6)
    out = []
    for ref, (name, x, y) in fps.items():
        if not name.startswith('MountingHole'):
            continue
        top = DIR_GAP if (stacked and ref == 'H3') else TOP_HEX_H
        out.append(rod('foot_' + ref, (x, y, -MILL_DEPTH - FOOT_H), (x, y, -MILL_DEPTH), r, bm['nylon'], 6))
        out.append(rod('foot_bore_' + ref, (x, y, -MILL_DEPTH - FOOT_H - 0.03), (x, y, -MILL_DEPTH - FOOT_H + 1), 1.35, bm['bore']))
        out.append(rod('hex_' + ref, (x, y, T_BOARD + MILL_DEPTH), (x, y, T_BOARD + MILL_DEPTH + top), r, bm['nylon'], 6))
        if not (stacked and ref == 'H3'):
            z = T_BOARD + MILL_DEPTH + top
            out.append(rod('hex_bore_' + ref, (x, y, z - 1), (x, y, z + 0.03), 1.35, bm['bore']))
    return out


def dir9001(bm, fps):
    """Stand-in for the LHY AUDIO DIR9001-I2S board, stacked over the DAC modules on the
    standoff at H3, with its pigtail to the XH header at A2. Sizes and positions are
    estimates from the photos."""
    out = []
    _, hx, hy = fps['H3']
    x0, ys = hx - DIR_HOLE_SW[1], hy + DIR_HOLE_SW[0]      # west edge, south edge
    yn = ys - DIR_W
    z0 = T_BOARD + MILL_DEPTH + DIR_GAP
    zt = z0 + DIR_T
    P = lambda n, e: (x0 + e, ys - n)                      # mm from the south edge, from the west edge
    def part(name, n0, n1, e0, e1, h, mat, zb=0.0):
        (xa, ya), (xb, yb) = P(n0, e0), P(n1, e1)
        o = box('dir_' + name, xa, ya, zt + zb, xb, yb, zt + zb + h, mat)
        out.append(o)
        return o
    pcb = box('dir_pcb', x0, yn, z0, x0 + DIR_L, ys, zt, bm['dir_pcb'])
    bpy.context.view_layer.update()
    set_uv(pcb, lambda x, y: ((y - yn) / DIR_W, (x - x0) / DIR_L))
    out.append(pcb)
    part('toslink', 46.5, 56.5, 36.0, 53.0, 10.5, bm['black'])
    part('toslink_port', 48.5, 54.5, 52.6, 53.1, 6.0, bm['bore'], zb=2.5)
    part('toggle', 27.0, 35.0, 36.0, 48.0, 7.0, bm['red'])
    x, y = P(31.0, 48.0)
    out.append(rod('dir_toggle_bush', (x, y, zt + 4), (x + 5, y, zt + 4), 2.6, bm['nickel']))
    out.append(rod('dir_toggle_lever', (x + 5, y, zt + 4), (x + 14, y, zt + 6.5), 1.3, bm['nickel']))
    part('rca_body', 3.0, 13.0, 36.0, 48.5, 12.0, bm['red'])
    x, y = P(8.0, 48.5)
    out.append(rod('dir_rca_barrel', (x, y, zt + 7), (x + 9.5, y, zt + 7), 4.15, bm['nickel']))
    out.append(rod('dir_rca_bore', (x + 8.5, y, zt + 7), (x + 9.53, y, zt + 7), 3.0, bm['bore']))
    part('dip1', 38.0, 44.0, 27.5, 32.5, 2.6, bm['black'])
    part('dip2', 2.5, 8.5, 10.5, 15.5, 2.6, bm['black'])
    part('dir9001', 25.0, 35.0, 12.5, 18.0, 1.1, bm['black'])
    part('buffer', 14.5, 19.5, 12.5, 18.0, 1.1, bm['black'])
    part('regulator', 54.5, 61.0, 19.0, 22.5, 1.6, bm['black'])
    part('diode', 55.0, 59.5, 24.5, 27.0, 1.2, bm['black'])
    part('cap_base', 54.7, 61.3, 10.7, 17.3, 1.0, bm['black'])
    x, y = P(58.0, 14.0)
    out.append(rod('dir_cap', (x, y, zt + 1.0), (x, y, zt + 6.0), 3.15, bm['can']))
    part('xh', 22.3, 39.7, 0.8, 6.6, 7.0, bm['white'])
    part('xh_plug', 23.0, 39.0, 1.6, 5.8, 5.0, bm['white'], zb=5.5)
    x, y = P(*DIR_HOLE_SW)
    r = STANDOFF_AF / 2 / math.cos(math.pi / 6)
    out.append(rod('dir_nut', (x, y, zt), (x, y, zt + 5), r, bm['nylon'], 6))
    out.append(rod('dir_nut_bore', (x, y, zt + 4), (x, y, zt + 5.03), 1.35, bm['bore']))

    # pigtail: six wires from I2S-OUT in a loop over to the header at A2
    _, ax, ay = fps['A2']
    zb = T_BOARD + MILL_DEPTH
    out.append(box('a2_plug', ax - 13.6, ay - 2.3, zb + 6.0, ax + 0.9, ay + 2.3, zb + 12.0, bm['white']))
    for i, col in enumerate(WIRE_COLOURS):
        cu = bpy.data.curves.new('wire%d' % i, 'CURVE'); cu.dimensions = '3D'
        cu.bevel_depth = 0.65 * MM; cu.bevel_resolution = 4; cu.resolution_u = 48
        sp = cu.splines.new('BEZIER'); sp.bezier_points.add(1)
        a = W(*P(24.75 + 2.5 * i, 3.7), zt + 10.0)
        b = W(ax - 0.1 - 2.5 * i, ay, zb + 11.5)
        h = (58 + 2.5 * i) * MM
        pa, pb = sp.bezier_points
        pa.co = a; pa.handle_left = a - Vector((0, 0, 0.01)); pa.handle_right = a + Vector((-0.012, 0.004, h))
        pb.co = b; pb.handle_right = b - Vector((0, 0, 0.01)); pb.handle_left = b + Vector((0.006, 0.010, h))
        cu.materials.append(principled('wire%d' % i, col, rough=0.4))
        o = bpy.data.objects.new('wire%d' % i, cu); bpy.context.scene.collection.objects.link(o)
        out.append(o)
    return out


def trim_leads(parts):
    """The library models carry untrimmed leads (the TO-220's reach 8 mm below the
    board). Cut every through-hole part off LEAD_STUB below the bottom face."""
    bpy.context.view_layer.update()
    for o in parts:
        # legs that miss their holes end at the top face instead of passing through copper
        short = o.parent and o.parent.name in LEGS_OFF_HOLES
        zcut = (T_BOARD + MILL_DEPTH) * MM if short else -LEAD_STUB * MM
        if min((o.matrix_world @ Vector(c)).z for c in o.bound_box) > zcut - 1e-6:
            continue
        if o.data.users > 1:
            o.data = o.data.copy()
        inv = o.matrix_world.inverted()
        bm = bmesh.new(); bm.from_mesh(o.data)
        co = inv @ Vector((0, 0, zcut))
        no = (inv.to_3x3().transposed().inverted() @ Vector((0, 0, -1))).normalized()
        r = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co,
                                   plane_no=no, clear_outer=True)
        edges = [e for e in r['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        if edges:
            bmesh.ops.holes_fill(bm, edges=edges)
        bm.to_mesh(o.data); bm.free()


def build_scene(flipped, stacked=False):
    """Import the board, shade it, and set it on the ground. flipped: bottom face up,
    turned over left to right as on the mill."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(BUILD / 'board.glb'))
    objs = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    body = next(o for o in objs if o.type == 'MESH' and o.data.name.startswith('surround_PCB'))
    bb = [body.matrix_world @ Vector(c) for c in body.bound_box]
    centre = Vector((sum(v.x for v in bb) / 8, sum(v.y for v in bb) / 8, T_BOARD * MM / 2))
    size = (max(v.x for v in bb) - min(v.x for v in bb), max(v.y for v in bb) - min(v.y for v in bb))
    fps = footprints()
    ref = bpy.data.objects.new('REF', None); sc.collection.objects.link(ref)
    bm = board_materials(ref)

    # Copper stands MILL_DEPTH proud of the laminate the mill has exposed: the export
    # gives a 0.04 mm foil on a flat board, so its outer faces move out to match.
    lift = MILL_DEPTH - 0.04
    body = None
    for o in objs:
        if o.type != 'MESH':
            continue
        dn = o.data.name
        if dn.startswith(('surround_copper', 'surround_pad')):
            o.data.materials[0] = bm['copper']
            inv = o.matrix_world.inverted()
            for v in o.data.vertices:
                w = o.matrix_world @ v.co
                if w.z > (T_BOARD + 0.02) * MM:
                    w.z += lift * MM
                elif w.z < -0.02 * MM:
                    w.z -= lift * MM
                else:
                    continue
                v.co = inv @ w
        elif dn.startswith('surround_silkscreen'):
            o.data.materials[0] = bm['silk']
            top = (o.matrix_world @ Vector(o.bound_box[0])).z > 0.5 * T_BOARD * MM
            o.location.z += (lift + 0.012) * MM * (1 if top else -1)
        elif dn.startswith('surround_PCB'):
            o.data.materials[0] = bm['fr4']
        elif dn.startswith('pcm5102_pcb'):
            # the module's back faces up: legend from the photos, placed by its footprint
            _, cx, cy = fps[o.parent.name.split('.')[0]]
            o.data = o.data.copy()
            set_uv(o, lambda x, y: ((y - (cy - 8.49)) / 17.11, (x - (cx - 17.08)) / 30.96))
            o.data.materials.clear()
            o.data.materials.append(bm['pcm5102_pcb'])
        elif o.parent and o.parent.name in RECOLOUR:
            stock, key = RECOLOUR[o.parent.name]
            o.data = o.data.copy()
            for i, m in enumerate(o.data.materials):
                c = m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value
                if all(abs(c[k] - stock[k]) < 0.02 for k in range(3)):
                    o.data.materials[i] = bm[key]
        elif dn.split('.')[0] in bm:
            o.data.materials.clear()
            o.data.materials.append(bm[dn.split('.')[0]])
            for p in o.data.polygons:
                p.use_smooth = False
        elif o.parent and o.parent.name in LED_COLOUR:
            o.data = o.data.copy()
            for i, m in enumerate(o.data.materials):
                c = m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value
                if abs(c[0] - 0.448) < 0.02 and c[1] < 0.05:
                    o.data.materials[i] = led_material(o.parent.name, LED_COLOUR[o.parent.name])
    for m in list(bpy.data.materials):
        if m.name.startswith('mat_'):
            component_material(m)
    trim_leads([o for o in objs if o.type == 'MESH' and not o.data.name.startswith('surround_')
                and not (o.parent and o.parent.name == 'U1')])

    root = bpy.data.objects.new('BOARD', None); sc.collection.objects.link(root)
    ref.parent = root
    tops = [o for o in objs if o.parent is None]
    solder = solder_joints(None, bm['solder'], T_BOARD + MILL_DEPTH, -MILL_DEPTH)
    extra = standoffs(bm, fps, stacked) + (dir9001(bm, fps) if stacked else [])
    for o in tops + [solder] + extra:
        o.parent = root
        o.matrix_parent_inverse = Matrix.Translation(-centre)
    if flipped:
        root.rotation_euler = (0, math.pi, 0)
    bpy.context.view_layer.update()
    # rest on the ground at the lowest point
    zmin = min((o.matrix_world @ Vector(c)).z for o in list(objs) + [solder] + extra if o.type == 'MESH' for c in o.bound_box)
    root.location.z = -zmin
    bpy.context.view_layer.update()
    return root, size


def studio():
    sc = bpy.context.scene
    w = bpy.data.worlds.new('studio'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.012, 0.013, 0.015, 1)
    bg.inputs['Strength'].default_value = 1.0
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    g = bpy.context.object; g.name = 'ground'
    g.data.materials.append(principled('ground', (0.030, 0.032, 0.036), rough=0.6, spec=0.25))
    return g


def area(name, loc, target, size, energy, colour=(1, 1, 1), size_y=None):
    l = bpy.data.lights.new(name, 'AREA'); l.energy = energy; l.color = colour
    l.shape = 'RECTANGLE'; l.size = size; l.size_y = size_y or size
    o = bpy.data.objects.new(name, l); bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def lights(kind, target=(0, 0, 0), card=8):
    if kind == 'flat':
        # Straight-on views: the copper mirrors whatever is overhead, so the light is a
        # wide soft ceiling, with one lower lamp to give the parts a shadow.
        area('ceiling', (0.0, 0.0, 0.60), (0, 0, 0), 1.2, 3.2, size_y=1.0)
        area('key', (-0.40, 0.30, 0.35), (0, 0, 0), 0.5, 6, (1.0, 0.97, 0.92))
        area('fill', (0.45, -0.30, 0.30), (0, 0, 0), 0.5, 2, (0.90, 0.95, 1.0))
        return
    # Bare copper is a mirror with a satin finish: it shows the room, not the lamps'
    # falloff. So the main light is a large soft card placed where the camera sees it
    # reflected in the board, and the key only shapes the parts.
    cam = bpy.context.scene.camera
    view = (Vector(target) - cam.location).normalized()
    mirror = Vector((view.x, view.y, -view.z))
    area('card', Vector(target) + 0.75 * mirror, target, 0.85, card, (1.0, 0.98, 0.95), size_y=0.55)
    area('key', (-0.40, -0.25, 0.50), (0, 0, 0), 0.45, 7, (1.0, 0.96, 0.90), size_y=0.30)
    area('fill', (0.55, -0.35, 0.25), (0, 0, 0), 0.5, 1.5, (0.85, 0.92, 1.0))
    area('top', (0.05, 0.10, 0.80), (0, 0, 0), 0.6, 2.0)


def camera(loc, target, lens, fstop=None, focus=None, ortho=None):
    c = bpy.data.cameras.new('cam'); o = bpy.data.objects.new('cam', c)
    bpy.context.scene.collection.objects.link(o); bpy.context.scene.camera = o
    c.lens = lens; c.sensor_width = 36; c.clip_start = 0.005; c.clip_end = 50
    if ortho:
        c.type = 'ORTHO'; c.ortho_scale = ortho
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if fstop:
        c.dof.use_dof = True; c.dof.aperture_fstop = fstop
        c.dof.focus_distance = focus if focus else d.length
    return o


def orbit(target, azimuth, elevation, distance):
    """Camera position: azimuth in degrees from the south edge, anticlockwise seen from above."""
    az, el = math.radians(azimuth - 90), math.radians(elevation)
    return Vector(target) + distance * Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))


def render_setup(w, h, samples):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    dev = 'CPU'
    for kind in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == kind
                dev = 'GPU'
                break
        except TypeError:
            continue
    sc.cycles.device = dev
    if dev == 'CPU':
        samples = max(32, samples // 3)
    if args.preview:
        w, h, samples = w // 2, h // 2, max(24, samples // 4)
    print(f'render device: {dev} ({prefs.compute_device_type}), samples {samples}')
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 8; sc.cycles.transmission_bounces = 8
    sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
    sc.render.resolution_x = w; sc.render.resolution_y = h; sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.image_settings.compression = 90


# ---------------------------------------------------------------- shots
def shot(name):
    flipped = name.startswith('bottom')
    root, (bw, bh) = build_scene(flipped, stacked=name == 'hero_stacked')
    studio()
    z = root.location.z
    if name == 'hero':
        render_setup(1920, 1280, 320)
        tgt = Vector((0.002, -0.002, z + 0.004))
        loc = orbit(tgt, 38, 28, 0.37)
        camera(loc, tgt, 85, fstop=20, focus=(loc - Vector((0.012, -0.022, z + 0.006))).length)
        lights('hero', tgt)
    elif name == 'hero_stacked':
        render_setup(1920, 1280, 320)
        tgt = Vector((0.000, 0.000, z + 0.024))
        loc = orbit(tgt, 38, 30, 0.50)
        camera(loc, tgt, 85, fstop=20, focus=(loc - Vector((0.0, -0.015, z + 0.015))).length)
        lights('hero', tgt)
    elif name == 'top_34':
        render_setup(1920, 1280, 256)
        tgt = Vector((0.0, 0.0, z + 0.004))
        camera(orbit(tgt, -25, 42, 0.40), tgt, 85)
        lights('hero', tgt, card=4)
    elif name == 'bottom_34':
        render_setup(1920, 1280, 256)
        tgt = Vector((0.0, 0.0, z))
        camera(orbit(tgt, -25, 42, 0.39), tgt, 85)
        lights('hero', tgt, card=3.5)
    else:                                   # top, bottom: straight on, no perspective
        lights('flat')
        render_setup(2000, 1500, 256)
        camera((0, 0, 0.9), (0, 0, 0), 50, ortho=(bw + 0.016))
    out = (BUILD / f'preview-{name}.png') if args.preview else (HERE / f'{name}.png')
    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=str(BUILD / f'{name}.blend'))
    bpy.context.scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    print('wrote', out)


for s in (args.shot or ALL):
    shot(s)
