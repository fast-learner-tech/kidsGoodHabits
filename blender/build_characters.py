"""Build the cast as rounded, toy-like 3D characters with a light rig and a lip-sync mouth.

Run:
  blender -b --factory-startup --python blender/build_characters.py -- --save assets/characters/cast.blend

Designs follow the concept art in assets/characters/concepts/ (pip, zuri, tomo, nana_rue, biscuit .png).
This is a scripted version made from simple shapes, not a sculpted final: refine by hand in Blender as the
show grows.

Each character lives in its own collection (Pip, Zuri, Tomo, NanaRue, Biscuit) with:
  <Name>_rig     armature: root, torso, head, arm.L/R, leg.L/R, eye.L/R (Biscuit: root, body, head, ear.L/R, tail)
  <Name>_Mouth   shape keys mouth_A ... mouth_H, mouth_X for blender/apply_lipsync.py (teeth are part of it)
Characters stand at the origin facing -Y (towards a camera placed at -Y). Their left side is +X.
"""
import math
import sys

import bmesh
import bpy
from mathutils import Euler, Vector

# (x scale, z scale, teeth visible) per Rhubarb mouth shape, relative to the closed rest mouth
MOUTH_SHAPES = {
    "A": (1.0, 1.0, False),   # closed (P B M)
    "B": (1.0, 3.0, True),    # slightly open, teeth (K S T)
    "C": (1.05, 4.2, True),   # open (E)
    "D": (1.1, 6.0, True),    # wide open (A)
    "E": (0.75, 4.6, False),  # rounded (O)
    "F": (0.55, 3.5, False),  # puckered (U W)
    "G": (1.0, 2.5, True),    # upper teeth on lip (F V)
    "H": (1.0, 3.8, True),    # tongue up (L)
    "X": (1.0, 1.0, False),   # rest
}


# ---------------------------------------------------------------- materials

def srgb(hex_str):
    """'#F7C631' -> linear RGBA (Blender colours are linear)."""
    h = hex_str.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


_mats = {}


def mat(hex_str, rough=0.55, sss=0.0, emit=0.0, coat=0.0, metal=0.0, sheen=0.0):
    key = (hex_str, rough, sss, emit, coat, metal, sheen)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(f"M_{hex_str.lstrip('#')}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = srgb(hex_str)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (0.3, 0.15, 0.1)
        b.inputs["Subsurface Scale"].default_value = 0.02
    if emit:
        b.inputs["Emission Color"].default_value = srgb(hex_str)
        b.inputs["Emission Strength"].default_value = emit
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    if sheen:  # soft fabric / fuzz look
        b.inputs["Sheen Weight"].default_value = sheen
    m.diffuse_color = srgb(hex_str)  # viewport colour
    _mats[key] = m
    return m


def tabby(base, stripe, scale=9.0):
    """Orange tabby fur: soft wavy stripes (object space) plus a little sheen."""
    m = bpy.data.materials.new("M_Tabby")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Sheen Weight"].default_value = 0.6
    coord, wave, ramp = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeTexWave"), nt.nodes.new("ShaderNodeValToRGB")
    wave.wave_type, wave.bands_direction = "BANDS", "Z"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 4.0
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.55, 0.8
    ramp.color_ramp.elements[0].color, ramp.color_ramp.elements[1].color = srgb(base), srgb(stripe)
    nt.links.new(coord.outputs["Object"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    m.diffuse_color = srgb(base)
    return m


# ---------------------------------------------------------------- geometry helpers

class Builder:
    def __init__(self, name):
        self.name = name
        self.coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(self.coll)
        self.parts = []  # (object, bone name)

    def ellip(self, part, loc, radii, material, bone, rot=(0, 0, 0), seg=40):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, location=loc)
        o = bpy.context.active_object
        o.name = f"{self.name}_{part}"
        o.scale = radii
        o.rotation_euler = Euler([math.radians(a) for a in rot])
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.object.shade_smooth()
        o.data.materials.append(material)
        return self._own(o, bone)

    def torus(self, part, loc, major, minor, material, bone, rot=(0, 0, 0), scale=(1, 1, 1)):
        bpy.ops.mesh.primitive_torus_add(location=loc, major_radius=major, minor_radius=minor,
                                         major_segments=48, minor_segments=16,
                                         rotation=[math.radians(a) for a in rot])
        o = bpy.context.active_object
        o.name = f"{self.name}_{part}"
        o.scale = scale
        bpy.ops.object.shade_smooth()
        o.data.materials.append(material)
        return self._own(o, bone)

    def cone(self, part, loc, r1, r2, depth, material, bone, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=r1, radius2=r2, depth=depth, location=loc,
                                        rotation=[math.radians(a) for a in rot])
        o = bpy.context.active_object
        o.name = f"{self.name}_{part}"
        mod = o.modifiers.new("Round", "SUBSURF")
        mod.levels = mod.render_levels = 2
        bpy.ops.object.shade_smooth()
        o.data.materials.append(material)
        return self._own(o, bone)

    def box(self, part, loc, size, material, bone, bevel=0.01, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cube_add(location=loc, rotation=[math.radians(a) for a in rot])
        o = bpy.context.active_object
        o.name = f"{self.name}_{part}"
        o.scale = [v / 2 for v in size]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        mod = o.modifiers.new("Bevel", "BEVEL")
        mod.width, mod.segments = bevel, 4
        mod.harden_normals = True
        bpy.ops.object.shade_smooth()
        o.data.materials.append(material)
        return self._own(o, bone)

    def shell(self, part, loc, radii, material, bone, keep, thick=0.006, seg=48):
        """Part of an ellipsoid surface (clothing, hair caps). keep(unit_xyz) -> True for vertices to keep."""
        o = self.ellip(part, loc, radii, material, bone, seg=seg)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        drop = [v for v in bm.verts if not keep(Vector((v.co.x / radii[0], v.co.y / radii[1], v.co.z / radii[2])))]
        bmesh.ops.delete(bm, geom=drop, context="VERTS")
        bm.to_mesh(o.data)
        bm.free()
        sol = o.modifiers.new("Thickness", "SOLIDIFY")
        sol.thickness, sol.offset = thick, 1.0
        return o

    def flat_star(self, part, loc, r, material, bone, depth=0.004):
        bm = bmesh.new()
        verts = []
        for i in range(10):
            a = math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.45
            verts.append(bm.verts.new((rr * math.cos(a), 0, rr * math.sin(a))))
        bm.faces.new(verts)
        bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        for v in bm.verts[10:]:
            v.co.y += depth
        me = bpy.data.meshes.new(part)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(f"{self.name}_{part}", me)
        o.location = loc
        o.data.materials.append(material)
        bpy.context.scene.collection.objects.link(o)
        return self._own(o, bone)

    def _own(self, o, bone):
        for c in o.users_collection:
            c.objects.unlink(o)
        self.coll.objects.link(o)
        self.parts.append((o, bone))
        return o

    def rig(self, bones):
        """bones: {name: (head, tail, parent)} in world space. Parents every part to its bone."""
        arm_data = bpy.data.armatures.new(f"{self.name}_rig")
        rig = bpy.data.objects.new(f"{self.name}_rig", arm_data)
        self.coll.objects.link(rig)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        for bname, (head, tail, _) in bones.items():
            eb = arm_data.edit_bones.new(bname)
            eb.head, eb.tail = Vector(head), Vector(tail)
        for bname, (_, _, parent) in bones.items():
            if parent:
                arm_data.edit_bones[bname].parent = arm_data.edit_bones[parent]
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.update()
        for o, bname in self.parts:
            mw = o.matrix_world.copy()
            o.parent, o.parent_type, o.parent_bone = rig, "BONE", bname
            bpy.context.view_layer.update()
            o.matrix_world = mw  # keep the part where it was built
        rig.show_in_front = True
        return rig


def surface(center, radii, x, dz, out=0.0):
    """Point on the front (-Y) of an ellipsoid at offset x, dz from its centre; out > 0 moves it forward."""
    a, b, c = radii
    k = max(0.0, 1 - (x / a) ** 2 - (dz / c) ** 2)
    return Vector((center[0] + x, center[1] - b * math.sqrt(k) - out, center[2] + dz))


def fib_points(n):
    pts, g = [], math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - z * z)
        pts.append(Vector((math.cos(g * i) * r, math.sin(g * i) * r, z)))
    return pts


def curls(b, center, radii, n, size, material, bone, keep, lift=1.0, jitter=0.25, prefix="Curl"):
    """Clusters of small spheres on an ellipsoid: curly hair, puffs, buns."""
    for i, d in enumerate(fib_points(n)):
        if not keep(d):
            continue
        s = size * (1 - jitter / 2 + jitter * ((i * 7919) % 100) / 100)
        loc = Vector(center) + Vector((d.x * radii[0], d.y * radii[1], d.z * radii[2])) * lift
        b.ellip(f"{prefix}{i:03d}", loc, (s,) * 3, material, bone, seg=16)


def build_mouth(b, loc, w, d, h0, smile, teeth_parts, gap=0.0):
    """One object: dark mouth + teeth, with Rhubarb shape keys. Teeth hide inside the mouth when closed."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    n_mouth = len(bm.verts)
    centers = [0.0] if teeth_parts == 1 else [-0.5, 0.5]
    for _ in centers:
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.0)
    me = bpy.data.meshes.new(f"{b.name}_Mouth")
    bm.to_mesh(me)
    bm.free()
    unit = [v.co.copy() for v in me.vertices]
    n_tooth = (len(unit) - n_mouth) // len(centers)

    def coords(sx, sz, teeth):
        out = []
        for i, u in enumerate(unit):
            if i < n_mouth:
                x, y, z = u.x * w * sx, u.y * d, u.z * h0 * sz
            else:
                k = (i - n_mouth) // n_tooth
                if not teeth:
                    out.append(Vector((0, d * 0.2, 0)) + u * 0.0005)  # tucked away inside the mouth
                    continue
                tw = w * sx * (0.62 if len(centers) == 1 else 0.3)
                cx = centers[k] * (tw * 2 + gap)
                x = cx + u.x * tw
                y = -d * 0.72 + u.y * d * 0.2
                z = h0 * sz * 0.62 + u.z * h0 * sz * 0.3
            z += smile * w * 0.3 * (x / (w * sx)) ** 2  # corners curl up into a smile
            out.append(Vector((x, y, z)))
        return out

    for v, co in zip(me.vertices, coords(1.0, 1.0, False)):
        v.co = co
    for p in me.polygons:
        p.use_smooth = True
        p.material_index = 0 if p.vertices[0] < n_mouth else 1
    o = bpy.data.objects.new(f"{b.name}_Mouth", me)
    o.location = loc
    me.materials.append(mat("#5A1E24", 0.4))
    me.materials.append(mat("#FBF7EE", 0.25))
    bpy.context.scene.collection.objects.link(o)
    b._own(o, "head")
    o.shape_key_add(name="Basis", from_mix=False)
    for letter, (sx, sz, teeth) in MOUTH_SHAPES.items():
        kb = o.shape_key_add(name=f"mouth_{letter}", from_mix=False)
        for i, co in enumerate(coords(sx, sz, teeth)):
            kb.data[i].co = co
    return o


# ---------------------------------------------------------------- humanoid body

def humanoid(name, h, heads, skin, iris, hair_col, brow_col, outfit, hair, extras=None,
             adult=False, mouth_w=1.0, smile=0.6, teeth_parts=1, gap=0.0, ear=1.0):
    b = Builder(name)
    hh = h / heads
    hr = (hh * 0.56, hh * 0.5, hh * 0.5)
    hc = Vector((0, 0, h - hr[2]))
    skin_m = mat(skin, 0.5, sss=0.12)
    P = dict(b=b, hh=hh, hr=hr, hc=hc, skin=skin_m, hair_col=hair_col, adult=adult)

    # head, cheeks, ears, nose
    b.ellip("Head", hc, hr, skin_m, "head")
    if not adult:  # chubby lower face
        for s, x in (("L", 1), ("R", -1)):
            b.ellip(f"CheekFull_{s}", hc + Vector((x * hr[0] * 0.42, -hr[1] * 0.42, -hr[2] * 0.38)),
                    (hr[0] * 0.45, hr[1] * 0.45, hr[2] * 0.42), skin_m, "head")
    blush = mat("#E8907E", 0.6, sss=0.1)
    for s, x in (("L", 1), ("R", -1)):
        b.ellip(f"Blush_{s}", surface(hc, (hr[0] * 1.02, hr[1] * 1.06, hr[2]), x * hr[0] * 0.6, -hr[2] * 0.28, -0.002),
                (hr[0] * 0.15, hr[1] * 0.04, hr[2] * 0.09), blush, "head")
        b.ellip(f"Ear_{s}", (x * hr[0] * 0.97, hc.y + hr[1] * 0.05, hc.z - hr[2] * 0.08),
                (hr[0] * 0.13 * ear, hr[1] * 0.2 * ear, hr[2] * 0.27 * ear), skin_m, "head", rot=(0, 0, x * -15))
    b.ellip("Nose", surface(hc, hr, 0, -hr[2] * 0.13, hr[1] * 0.02), (hr[0] * 0.13, hr[1] * 0.12, hr[2] * 0.11),
            mat(skin, 0.45, sss=0.12), "head")

    # eyes: white, iris, pupil, two glints, lash line; eye bones squash them for blinks
    e_scale = 0.8 if adult else 1.0
    for s, x in (("L", 1), ("R", -1)):
        ex, ez = x * hr[0] * 0.37, hr[2] * 0.1
        er = (hr[0] * 0.25 * e_scale, hr[1] * 0.12, hr[2] * 0.32 * e_scale)
        ec = surface(hc, hr, ex, ez, -er[1] * 0.35)
        b.ellip(f"EyeWhite_{s}", ec, er, mat("#FFFFFF", 0.25), f"eye.{s}")
        fwd = Vector((0, -er[1] * 0.72, -er[2] * 0.05))
        b.ellip(f"Iris_{s}", ec + fwd, (er[0] * 0.78, er[1] * 0.42, er[2] * 0.78), mat(iris, 0.2), f"eye.{s}")
        b.ellip(f"Pupil_{s}", ec + fwd + Vector((0, -er[1] * 0.2, 0)), (er[0] * 0.42, er[1] * 0.32, er[2] * 0.42),
                mat("#120A06", 0.15), f"eye.{s}")
        b.ellip(f"Glint_{s}", ec + Vector((x * er[0] * 0.22, -er[1] * 1.2, er[2] * 0.3)), (er[0] * 0.2,) * 3,
                mat("#FFFFFF", 0.1, emit=2.5), f"eye.{s}", seg=16)
        b.ellip(f"Glint2_{s}", ec + Vector((-x * er[0] * 0.22, -er[1] * 1.15, -er[2] * 0.3)), (er[0] * 0.09,) * 3,
                mat("#FFFFFF", 0.1, emit=2.5), f"eye.{s}", seg=12)
        b.ellip(f"Lash_{s}", ec + Vector((0, -er[1] * 0.45, er[2] * 0.9)), (er[0] * 1.06, er[1] * 0.45, er[2] * 0.13),
                mat("#1A0F0A", 0.5), f"eye.{s}")
        b.ellip(f"Brow_{s}", surface(hc, hr, x * hr[0] * 0.37, ez + er[2] * 1.55, -0.002),
                (er[0] * 1.0, er[1] * 0.35, er[2] * 0.17), mat(brow_col, 0.7), "head", rot=(0, x * -10, 0))
        P[f"eye_{s}"] = (ec, er)

    mouth_c = surface(hc, hr, 0, -hr[2] * 0.52, -hr[1] * 0.02)
    build_mouth(b, mouth_c, hr[0] * 0.3 * mouth_w, hr[1] * 0.1, hr[2] * 0.028, smile, teeth_parts, gap)

    # neck, torso, arms, legs (all skin; outfits recolour or cover them)
    hip = h * (0.42 if adult else 0.36)
    neck_z = hc.z - hr[2] * 0.82
    torso_top, torso_bot = neck_z + hh * 0.02, hip - hh * 0.1
    tr = (hr[0] * (1.15 if adult else 0.8), hr[0] * (0.95 if adult else 0.62), (torso_top - torso_bot) / 2)
    tc = Vector((0, 0, (torso_top + torso_bot) / 2))
    b.ellip("Neck", (0, 0, neck_z + hh * 0.02), (hr[0] * 0.3, hr[0] * 0.3, hh * 0.12), skin_m, "torso")
    torso = b.ellip("Torso", tc, tr, skin_m, "torso")
    sh_z = torso_top - tr[2] * 0.3
    arm_len = (sh_z - hip) * (1.1 if adult else 1.15)
    arm_r = hh * (0.12 if adult else 0.11)
    arms, hands, shoulders = [], [], []
    for s, x in (("L", 1), ("R", -1)):
        start = Vector((x * tr[0] * 0.86, 0, sh_z))
        end = start + Vector((x * arm_len * 0.24, 0, -arm_len * 0.97))
        ang = -math.degrees(math.atan2(end.x - start.x, start.z - end.z))
        arms.append(b.ellip(f"Arm_{s}", (start + end) / 2, (arm_r, arm_r, arm_len / 2 + arm_r * 0.5), skin_m,
                            f"arm.{s}", rot=(0, ang, 0)))
        hands.append(b.ellip(f"Hand_{s}", end + Vector((x * arm_r * 0.2, 0, -arm_r * 0.6)),
                             (arm_r * 1.05, arm_r * 0.8, arm_r * 1.35), skin_m, f"arm.{s}", rot=(0, ang, 0)))
        shoulders.append((start, end, ang))
    leg_r = hh * (0.2 if adult else 0.15)
    legs = []
    for s, x in (("L", 1), ("R", -1)):
        lx = x * tr[0] * 0.48
        legs.append(b.ellip(f"Leg_{s}", (lx, 0, hip / 2 + hh * 0.04), (leg_r, leg_r, hip / 2 + hh * 0.02), skin_m, f"leg.{s}"))
    P.update(torso=torso, tc=tc, tr=tr, hip=hip, neck_z=neck_z, arms=arms, hands=hands, shoulders=shoulders,
             arm_r=arm_r, arm_len=arm_len, legs=legs, leg_r=leg_r)

    outfit(P)
    hair(P)
    if extras:
        extras(P)

    bones = {
        "root": ((0, 0, 0), (0, 0, hh * 0.5), None),
        "torso": ((0, 0, hip), (0, 0, neck_z), "root"),
        "head": ((0, 0, neck_z), (0, 0, h), "torso"),
    }
    for s, x in (("L", 1), ("R", -1)):
        ec, er = P[f"eye_{s}"]
        bones[f"eye.{s}"] = (tuple(ec), tuple(ec + Vector((0, 0, er[2] * 1.5))), "head")
        start, end, _ = shoulders[0 if s == "L" else 1]
        bones[f"arm.{s}"] = (tuple(start), tuple(end), "torso")
        bones[f"leg.{s}"] = ((x * tr[0] * 0.48, 0, hip), (x * tr[0] * 0.48, 0, 0.02), "root")
    b.rig(bones)
    return b


def sleeve(P, s_idx, length_frac, material, puff=1.35, cuff=None):
    """Sleeve over the upper part of an arm (short sleeve) or the whole arm (length_frac=1)."""
    b = P["b"]
    start, end, ang = P["shoulders"][s_idx]
    s = "L" if s_idx == 0 else "R"
    L = P["arm_len"] * length_frac
    direction = (end - start).normalized()
    mid = start + direction * (L / 2 - P["arm_r"] * 0.2)
    b.ellip(f"Sleeve_{s}", mid, (P["arm_r"] * puff, P["arm_r"] * puff, L / 2 + P["arm_r"] * 0.4), material, f"arm.{s}",
            rot=(0, ang, 0))
    if cuff:
        c = start + direction * (L - P["arm_r"] * 0.1)
        b.torus(f"SleeveCuff_{s}", c, P["arm_r"] * puff * 0.95, P["arm_r"] * 0.3, cuff, f"arm.{s}", rot=(0, ang, 0))


def trouser_legs(P, top_z, bottom_z, material, cuff_mat, width=1.3, prefix="Trouser"):
    b = P["b"]
    for s, x in (("L", 1), ("R", -1)):
        lx = x * P["tr"][0] * 0.48
        r = P["leg_r"] * width
        b.ellip(f"{prefix}_{s}", (lx, 0, (top_z + bottom_z) / 2), (r, r, (top_z - bottom_z) / 2 + r * 0.3), material,
                f"leg.{s}")
        if cuff_mat:
            b.torus(f"{prefix}Cuff_{s}", (lx, 0, bottom_z + r * 0.25), r * 0.98, r * 0.32, cuff_mat, f"leg.{s}")


def sneakers(P, upper, sole, toe=None, stripes=None, scale=1.0):
    b, hh = P["b"], P["hh"]
    for s, x in (("L", 1), ("R", -1)):
        lx = x * P["tr"][0] * 0.48
        r = hh * 0.17 * scale
        b.ellip(f"Shoe_{s}", (lx, -r * 0.45, r * 0.7), (r * 0.95, r * 1.45, r * 0.75), upper, f"leg.{s}")
        b.ellip(f"Sole_{s}", (lx, -r * 0.45, r * 0.22), (r * 1.02, r * 1.55, r * 0.3), sole, f"leg.{s}")
        if toe:
            b.ellip(f"Toe_{s}", (lx, -r * 1.35, r * 0.45), (r * 0.7, r * 0.55, r * 0.45), toe, f"leg.{s}")
        if stripes:
            for k, dz in enumerate((0.55, 0.85)):
                b.ellip(f"Stripe{k}_{s}", (lx + x * r * 0.9, -r * 0.4, r * dz), (r * 0.12, r * 0.9, r * 0.07),
                        stripes, f"leg.{s}", rot=(-20, 0, 0))


# ---------------------------------------------------------------- the cast

def pip():
    def outfit(P):
        b, hh, tr, tc = P["b"], P["hh"], P["tr"], P["tc"]
        shirt = mat("#F7C631", 0.8, sheen=0.3)
        denim = mat("#1E7F86", 0.85, sheen=0.2)
        denim_light = mat("#2C979B", 0.85)
        gold = mat("#C99A3C", 0.3, metal=1.0)
        P["torso"].data.materials[0] = shirt
        for i in (0, 1):
            sleeve(P, i, 0.4, shirt)
        # dungarees: seat + bib + pocket + straps with gold buttons
        b.ellip("DungareeSeat", tc + Vector((0, 0, -tr[2] * 0.45)), (tr[0] * 1.06, tr[1] * 1.08, tr[2] * 0.62), denim, "torso")
        bib_c = tc + Vector((0, -tr[1] * 0.86, tr[2] * 0.02))
        bib_h = tr[2] * 0.75
        b.box("DungareeBib", bib_c, (tr[0] * 1.05, tr[1] * 0.25, bib_h), denim, "torso", bevel=0.012)
        b.box("BibPocket", bib_c + Vector((0, -tr[1] * 0.14, -bib_h * 0.05)), (tr[0] * 0.5, tr[1] * 0.06, bib_h * 0.38),
              denim_light, "torso", bevel=0.006)
        for s, x in (("L", 1), ("R", -1)):
            top = bib_c + Vector((x * tr[0] * 0.4, 0, bib_h * 0.42))
            b.box(f"Strap_{s}", top + Vector((0, tr[1] * 0.7, tr[2] * 0.3)), (tr[0] * 0.2, tr[1] * 1.7, tr[2] * 0.07),
                  denim, "torso", bevel=0.006, rot=(-12, 0, 0))
            b.ellip(f"Button_{s}", top + Vector((0, -tr[1] * 0.15, 0)), (hh * 0.024, hh * 0.012, hh * 0.024), gold, "torso", seg=16)
        trouser_legs(P, P["hip"] + hh * 0.05, hh * 0.2, denim, denim_light, width=1.35)
        sneakers(P, mat("#D93B2B", 0.5), mat("#F4F1EA", 0.6), toe=mat("#F4F1EA", 0.6))

    def hair(P):
        hc, hr = P["hc"], P["hr"]
        hm = mat(P["hair_col"], 0.75, sheen=0.4)
        P["b"].shell("HairCap", hc, (hr[0] * 1.04, hr[1] * 1.05, hr[2] * 1.04), hm, "head",
                     keep=lambda u: u.z > (0.3 if u.y < -0.3 else -0.25))
        curls(P["b"], hc, hr, 160, hr[0] * 0.2, hm, "head",
              keep=lambda d: d.z > (0.42 if d.y < -0.3 else -0.2) and abs(d.x) < 0.98, lift=1.1)
        # signature curl on top
        P["b"].torus("TopCurl", hc + Vector((hr[0] * 0.1, -hr[1] * 0.3, hr[2] * 1.18)), hr[0] * 0.13, hr[0] * 0.05, hm, "head",
                     rot=(70, 0, 20))

    def freckles(P):
        hc, hr = P["hc"], P["hr"]
        dot = mat("#7A4429", 0.6)
        for s, x in (("L", 1), ("R", -1)):
            for k, (dx, dz) in enumerate(((0.48, -0.2), (0.58, -0.16), (0.53, -0.26), (0.64, -0.24))):
                P["b"].ellip(f"Freckle{k}_{s}", surface(hc, (hr[0] * 1.03, hr[1] * 1.08, hr[2]), x * hr[0] * dx, hr[2] * dz, 0.0),
                             (hr[0] * 0.018,) * 3, dot, "head", seg=8)

    return humanoid("Pip", 1.15, 3.3, "#A8693F", "#5A3416", "#24160E", "#24160E", outfit, hair, freckles,
                    mouth_w=1.15, smile=0.9, teeth_parts=2, gap=0.004, ear=1.2)


def zuri():
    def outfit(P):
        b, hh, tr, tc = P["b"], P["hh"], P["tr"], P["tc"]
        tee = mat("#F7F6F2", 0.8, sheen=0.3)
        vest = mat("#7E4FC0", 0.75, sheen=0.4)
        shorts = mat("#6E8B3D", 0.85)
        zipper = mat("#C8C8CC", 0.3, metal=1.0)
        P["torso"].data.materials[0] = tee
        for i in (0, 1):
            sleeve(P, i, 0.4, tee)
        # sleeveless hooded vest, open at the front
        b.shell("Vest", tc + Vector((0, 0, tr[2] * 0.05)), (tr[0] * 1.1, tr[1] * 1.12, tr[2] * 1.02), vest, "torso",
                keep=lambda u: not (u.y < -0.2 and abs(u.x) < 0.3) and u.z > -0.85 and u.z < 0.92, thick=0.012)
        b.torus("Hood", (0, tr[1] * 0.3, tc.z + tr[2] * 0.95), tr[0] * 0.62, tr[0] * 0.2, vest, "torso", rot=(15, 0, 0))
        for s, x in (("L", 1), ("R", -1)):
            b.ellip(f"Zip_{s}", tc + Vector((x * tr[0] * 0.33, -tr[1] * 1.0, tr[2] * 0.05)), (tr[0] * 0.025, tr[1] * 0.05, tr[2] * 0.85),
                    zipper, "torso")
        b.ellip("ShortsSeat", tc + Vector((0, 0, -tr[2] * 0.7)), (tr[0] * 1.08, tr[1] * 1.1, tr[2] * 0.45), shorts, "torso")
        trouser_legs(P, P["hip"] + hh * 0.05, P["hip"] - hh * 0.3, shorts, mat("#7E9B4A", 0.85), width=1.45, prefix="Shorts")
        sock = mat("#F7F6F2", 0.85)
        for s, x in (("L", 1), ("R", -1)):
            b.ellip(f"Sock_{s}", (x * tr[0] * 0.48, 0, hh * 0.32), (P["leg_r"] * 1.12, P["leg_r"] * 1.12, hh * 0.2), sock, f"leg.{s}")
        sneakers(P, mat("#F7F6F2", 0.5), mat("#E8E6E0", 0.6), stripes=mat("#8E5CD0", 0.5))

    def hair(P):
        hc, hr = P["hc"], P["hr"]
        hm = mat(P["hair_col"], 0.8, sheen=0.5)
        ribbon = mat("#8E5CD0", 0.35, sheen=0.3)
        P["b"].shell("HairCap", hc, (hr[0] * 1.03, hr[1] * 1.04, hr[2] * 1.03), hm, "head",
                     keep=lambda u: u.z > (0.38 if u.y < -0.3 else -0.2))
        for s, x in (("L", 1), ("R", -1)):
            pc = hc + Vector((x * hr[0] * 0.78, hr[1] * 0.05, hr[2] * 0.95))
            pr = (hr[0] * 0.48, hr[0] * 0.44, hr[0] * 0.46)
            P["b"].ellip(f"Puff_{s}", pc, pr, hm, "head")
            curls(P["b"], pc, pr, 70, hr[0] * 0.11, hm, "head", keep=lambda d: True, lift=1.0, prefix=f"PuffCurl{s}")
            # bow: two loops and a knot, on the inner front of each puff
            bc = pc + Vector((-x * pr[0] * 0.35, -pr[1] * 1.08, -pr[2] * 0.5))
            for k, dx in enumerate((-1, 1)):
                P["b"].ellip(f"BowLoop{k}_{s}", bc + Vector((dx * hr[0] * 0.17, 0, hr[0] * 0.04)),
                             (hr[0] * 0.17, hr[0] * 0.06, hr[0] * 0.11), ribbon, "head", rot=(0, dx * -25, 0))
            P["b"].ellip(f"BowKnot_{s}", bc + Vector((0, -hr[0] * 0.03, 0)), (hr[0] * 0.06,) * 3, ribbon, "head")

    def earrings(P):
        hc, hr = P["hc"], P["hr"]
        for s, x in (("L", 1), ("R", -1)):
            P["b"].ellip(f"Earring_{s}", (x * hr[0] * 1.02, -hr[1] * 0.05, hc.z - hr[2] * 0.3), (hr[0] * 0.035,) * 3,
                         mat("#9B6BD3", 0.2, coat=1.0), "head", seg=12)

    return humanoid("Zuri", 1.15, 3.3, "#6B3F24", "#5A3416", "#1E120C", "#1E120C", outfit, hair, earrings,
                    mouth_w=1.1, smile=0.9, ear=1.0)


def tomo():
    def outfit(P):
        b, hh, tr, tc = P["b"], P["hh"], P["tr"], P["tc"]
        romper = mat("#9ED9BE", 0.85, sheen=0.4)
        romper_cuff = mat("#8ED0B2", 0.85)
        P["torso"].data.materials[0] = romper
        b.ellip("RomperBody", tc + Vector((0, 0, -tr[2] * 0.1)), (tr[0] * 1.08, tr[1] * 1.1, tr[2] * 1.02), romper, "torso")
        for i in (0, 1):
            sleeve(P, i, 0.45, romper, puff=1.5, cuff=romper_cuff)
        trouser_legs(P, P["hip"] + hh * 0.05, P["hip"] - hh * 0.22, romper, romper_cuff, width=1.55, prefix="Shorts")
        # chest pocket with the yellow star, on Tomo's left (+X)
        pc = tc + Vector((tr[0] * 0.42, -tr[1] * 1.04, tr[2] * 0.15))
        b.ellip("Pocket", pc, (tr[0] * 0.3, tr[1] * 0.08, tr[2] * 0.3), romper_cuff, "torso")
        b.flat_star("StarPatch", pc + Vector((0, -tr[1] * 0.1, 0)), tr[0] * 0.2, mat("#F7D44A", 0.5), "torso")
        sock = mat("#F7F6F2", 0.85)
        for s, x in (("L", 1), ("R", -1)):
            b.ellip(f"Sock_{s}", (x * tr[0] * 0.48, 0, hh * 0.18), (P["leg_r"] * 1.1, P["leg_r"] * 1.1, hh * 0.1), sock, f"leg.{s}")
        white = mat("#F7F6F2", 0.5)
        sneakers(P, white, mat("#E8E6E0", 0.6), toe=white, scale=1.05)
        for s, x in (("L", 1), ("R", -1)):  # velcro strap
            r = hh * 0.17 * 1.05
            b.ellip(f"Velcro_{s}", (x * tr[0] * 0.48, -r * 0.6, r * 1.0), (r * 0.98, r * 0.5, r * 0.15), mat("#ECEAE4", 0.6), f"leg.{s}",
                    rot=(-25, 0, 0))

    def hair(P):
        hc, hr = P["hc"], P["hr"]
        hm = mat(P["hair_col"], 0.6, sheen=0.4)
        P["b"].shell("HairCap", hc, (hr[0] * 1.02, hr[1] * 1.03, hr[2] * 1.02), hm, "head",
                     keep=lambda u: u.z > (0.5 if u.y < -0.3 else -0.1))
        # fringe pieces and the messy tuft on top
        for k, (x, rot) in enumerate(((-0.45, 25), (-0.22, 12), (0.0, 0), (0.22, -12), (0.45, -25))):
            P["b"].ellip(f"Fringe{k}", surface(hc, (hr[0] * 1.04, hr[1] * 1.06, hr[2] * 1.03), x * hr[0], hr[2] * 0.5, 0.0),
                         (hr[0] * 0.16, hr[1] * 0.07, hr[2] * 0.24), hm, "head", rot=(20, rot, 0))
        for k, d in enumerate(fib_points(40)):  # soft spiky clumps over the crown and sides
            if d.z > -0.15 and not (d.y < -0.3 and d.z < 0.6):
                P["b"].ellip(f"Clump{k:02d}", hc + Vector((d.x * hr[0], d.y * hr[1], d.z * hr[2])) * 1.02,
                             (hr[0] * 0.12, hr[0] * 0.12, hr[0] * 0.18), hm, "head",
                             rot=(math.degrees(math.atan2(-d.y, d.z)), math.degrees(math.atan2(d.x, d.z)), 0))
        for k, (x, y, rx, ry) in enumerate(((0.0, -0.1, -20, 0), (0.12, 0.05, -10, 25), (-0.12, 0.0, -15, -25),
                                            (0.05, 0.2, 10, 10), (-0.05, -0.25, -35, -5))):
            P["b"].ellip(f"Tuft{k}", hc + Vector((x * hr[0], y * hr[1], hr[2] * 1.05)), (hr[0] * 0.06, hr[0] * 0.05, hr[2] * 0.22),
                         hm, "head", rot=(rx, ry, 0))

    return humanoid("Tomo", 0.95, 2.45, "#E7B48F", "#4A2A14", "#141110", "#3A2A20", outfit, hair,
                    mouth_w=1.0, smile=1.0, ear=1.25)


def nana_rue():
    def outfit(P):
        b, hh, tr, tc = P["b"], P["hh"], P["tr"], P["tc"]
        cardigan = mat("#E07A5F", 0.95, sheen=0.6)
        rib = mat("#D06E55", 0.95, sheen=0.6)
        blouse = mat("#F1E4CC", 0.8, sheen=0.3)
        trousers = mat("#CDB89A", 0.85, sheen=0.2)
        button = mat("#6B4A35", 0.4, coat=0.8)
        gold = mat("#D4A94C", 0.25, metal=1.0)
        P["torso"].data.materials[0] = blouse
        b.shell("Cardigan", tc + Vector((0, 0, -tr[2] * 0.02)), (tr[0] * 1.08, tr[1] * 1.1, tr[2] * 1.04), cardigan, "torso",
                keep=lambda u: not (u.y < -0.2 and abs(u.x) < 0.22 + 0.25 * max(0.0, u.z)) and u.z < 0.95, thick=0.014)
        b.torus("CardiganHem", (0, 0, tc.z - tr[2] * 0.92), 1.0, 0.035, rib, "torso", scale=(tr[0] * 0.98, tr[1] * 1.0, 1.0))
        for i in (0, 1):
            sleeve(P, i, 1.0, cardigan, puff=1.3, cuff=rib)
        for s, x in (("L", 1), ("R", -1)):
            b.ellip(f"Pocket_{s}", tc + Vector((x * tr[0] * 0.62, -tr[1] * 0.92, -tr[2] * 0.5)), (tr[0] * 0.26, tr[1] * 0.1, tr[2] * 0.2),
                    rib, "torso")
        for k in range(4):  # buttons down her right front edge
            z = tc.z + tr[2] * (0.25 - k * 0.32)
            b.ellip(f"Button{k}", (-tr[0] * (0.26 + 0.1 * k / 3), -tr[1] * 1.06, z), (hh * 0.022,) * 3, button, "torso", seg=16)
        # embroidered flowers on the blouse near the collar
        for k, (dx, dz, col) in enumerate(((-0.12, 0.62, "#E8664A"), (0.12, 0.62, "#E8664A"), (-0.2, 0.55, "#7FA35A"),
                                           (0.2, 0.55, "#7FA35A"), (-0.06, 0.52, "#F08A6B"), (0.06, 0.52, "#F08A6B"))):
            b.ellip(f"Flower{k}", tc + Vector((dx * tr[0], -tr[1] * 0.96, dz * tr[2])), (hh * 0.02,) * 3, mat(col, 0.6), "torso", seg=12)
        # necklace and pendant
        b.torus("Necklace", (0, -tr[1] * 0.1, P["neck_z"] - hh * 0.03), hh * 0.2, hh * 0.008, gold, "torso", rot=(20, 0, 0))
        b.ellip("Pendant", (0, -tr[1] * 0.92, tc.z + tr[2] * 0.62), (hh * 0.03, hh * 0.008, hh * 0.03), gold, "torso", seg=16)
        trouser_legs(P, P["hip"] + hh * 0.05, hh * 0.12, trousers, mat("#C2AC8D", 0.85), width=1.25)
        loafer = mat("#8B5A3C", 0.35, coat=0.5)
        sneakers(P, loafer, mat("#6B4A35", 0.5), scale=0.95)
        for s, x in (("L", 1), ("R", -1)):
            r = hh * 0.17 * 0.95
            b.ellip(f"ShoeFlower_{s}", (x * P["tr"][0] * 0.48, -r * 1.25, r * 0.95), (r * 0.18, r * 0.1, r * 0.18), mat("#E8664A", 0.5),
                    f"leg.{s}")

    def hair(P):
        hc, hr = P["hc"], P["hr"]
        hm = mat(P["hair_col"], 0.55, sheen=0.5)
        P["b"].shell("HairCap", hc, (hr[0] * 1.03, hr[1] * 1.04, hr[2] * 1.03), hm, "head",
                     keep=lambda u: u.z > (0.42 if u.y < -0.3 else -0.35))
        curls(P["b"], hc, hr, 170, hr[0] * 0.17, hm, "head",
              keep=lambda d: d.z > (0.45 if d.y < -0.35 else -0.45), lift=1.08)
        bun_c = hc + Vector((0, hr[1] * 0.1, hr[2] * 1.2))
        bun_r = (hr[0] * 0.45, hr[0] * 0.42, hr[0] * 0.36)
        P["b"].ellip("Bun", bun_c, bun_r, hm, "head")
        curls(P["b"], bun_c, bun_r, 60, hr[0] * 0.12, hm, "head", keep=lambda d: d.z > -0.5, prefix="BunCurl")

    def accessories(P):
        hc, hr = P["hc"], P["hr"]
        gold = mat("#D4A94C", 0.25, metal=1.0)
        for s, x in (("L", 1), ("R", -1)):
            ec, er = P[f"eye_{s}"]
            P["b"].torus(f"Glasses_{s}", ec + Vector((0, -er[1] * 1.6, 0)), er[0] * 1.35, hr[0] * 0.012, gold, "head", rot=(90, 0, 0))
            P["b"].ellip(f"Earring_{s}", (x * hr[0] * 1.0, -hr[1] * 0.05, hc.z - hr[2] * 0.33), (hr[0] * 0.04,) * 3, gold, "head", seg=12)
        P["b"].ellip("Glasses_Bridge", surface(hc, hr, 0, hr[2] * 0.12, er[1] * 1.6), (hr[0] * 0.1, hr[0] * 0.012, hr[0] * 0.012),
                     gold, "head")

    return humanoid("NanaRue", 1.55, 4.2, "#B97D55", "#4A2E1A", "#E4E2E6", "#B8B4B8", outfit, hair, accessories,
                    adult=True, mouth_w=0.95, smile=0.8)


def biscuit():
    b = Builder("Biscuit")
    fur = tabby("#E8A25A", "#D0803A")
    white = mat("#FBF3E6", 0.9, sheen=0.6)
    pink = mat("#F2A0A0", 0.5)
    dark = mat("#120A06", 0.15, coat=1.0)
    bc = Vector((0, 0.03, 0.13))
    b.ellip("Body", bc, (0.1, 0.12, 0.13), fur, "body")
    b.ellip("Chest", bc + Vector((0, -0.07, 0.02)), (0.075, 0.06, 0.1), white, "body")
    for s, x in (("L", 1), ("R", -1)):
        b.ellip(f"Haunch_{s}", bc + Vector((x * 0.07, 0.04, -0.06)), (0.06, 0.08, 0.07), fur, "body")
        b.ellip(f"FrontLeg_{s}", (x * 0.04, -0.06, 0.07), (0.032, 0.034, 0.07), fur, "body")
        b.ellip(f"FrontPaw_{s}", (x * 0.04, -0.085, 0.018), (0.034, 0.042, 0.022), white, "body")
        b.ellip(f"BackPaw_{s}", (x * 0.1, -0.02, 0.016), (0.03, 0.045, 0.02), white, "body")
    hc = Vector((0, -0.04, 0.33))
    hr = (0.14, 0.12, 0.125)
    b.ellip("Head", hc, hr, fur, "head")
    for s, x in (("L", 1), ("R", -1)):
        b.ellip(f"CheekFluff_{s}", hc + Vector((x * 0.08, -0.04, -0.06)), (0.075, 0.07, 0.06), white, "head")
    b.ellip("Muzzle", surface(hc, hr, 0, -0.05, -0.015), (0.06, 0.04, 0.04), white, "head")
    b.ellip("Nose", surface(hc, hr, 0, -0.03, 0.012), (0.014, 0.01, 0.01), pink, "head")
    for s, x in (("L", 1), ("R", -1)):  # little "w" mouth and whiskers
        b.ellip(f"MouthLine_{s}", surface(hc, hr, x * 0.012, -0.058, 0.014), (0.012, 0.004, 0.003), mat("#6B3A2A", 0.5), "head",
                rot=(0, x * 25, 0))
        for k, (dz, rot) in enumerate(((-0.04, 8), (-0.055, 0), (-0.07, -8))):
            b.ellip(f"Whisker{k}_{s}", surface(hc, hr, x * 0.09, dz, -0.01) + Vector((x * 0.05, 0, 0)), (0.06, 0.0015, 0.0015),
                    mat("#FFFFFF", 0.4), "head", rot=(0, x * rot, 0), seg=8)
        ec = surface(hc, hr, x * 0.058, 0.02, -0.012)
        b.ellip(f"Iris_{s}", ec, (0.036, 0.022, 0.04), mat("#7A4A22", 0.15, coat=1.0), "head")
        b.ellip(f"Pupil_{s}", ec + Vector((0, -0.01, 0)), (0.026, 0.016, 0.03), dark, "head")
        b.ellip(f"Glint_{s}", ec + Vector((x * 0.01, -0.024, 0.014)), (0.008,) * 3, mat("#FFFFFF", 0.1, emit=2.5), "head", seg=12)
        b.ellip(f"Glint2_{s}", ec + Vector((-x * 0.01, -0.022, -0.014)), (0.004,) * 3, mat("#FFFFFF", 0.1, emit=2.5), "head", seg=8)
        b.ellip(f"BrowFur_{s}", surface(hc, hr, x * 0.06, 0.075, -0.004), (0.025, 0.006, 0.006), mat("#C9783A", 0.8), "head",
                rot=(0, x * -12, 0))
        # pointed ears with pink insides
        ear_base = hc + Vector((x * 0.085, 0.0, 0.085))
        b.cone(f"Ear_{s}", ear_base + Vector((0, 0, 0.04)), 0.05, 0.004, 0.1, fur, f"ear.{s}", rot=(-5, x * 28, 0))
        b.cone(f"EarInner_{s}", ear_base + Vector((x * -0.004, -0.018, 0.035)), 0.032, 0.003, 0.075, pink, f"ear.{s}", rot=(-5, x * 28, 0))
    # mint collar with a gold bell
    b.torus("Collar", (0, -0.03, 0.225), 0.075, 0.01, mat("#8FD1B8", 0.5), "body", scale=(1.0, 0.9, 1.0), rot=(10, 0, 0))
    b.ellip("Bell", (0, -0.105, 0.2), (0.016,) * 3, mat("#D9A93E", 0.2, metal=1.0), "body", seg=20)
    # fluffy tail curling up behind
    for k in range(9):
        t = k / 8
        a = math.radians(-60 + 210 * t)
        loc = (0.12 + 0.06 * math.sin(a), 0.16 + 0.05 * t, 0.06 + 0.16 * t + 0.03 * math.cos(a))
        b.ellip(f"Tail{k}", loc, (0.032 - 0.008 * t,) * 3, white if k == 8 else fur, "tail", seg=16)
    b.rig({
        "root": ((0, 0, 0), (0, 0, 0.06), None),
        "body": ((0, 0.1, 0.12), (0, -0.05, 0.2), "root"),
        "head": ((0, -0.03, 0.22), (0, -0.04, 0.46), "body"),
        "ear.L": ((0.08, -0.04, 0.4), (0.12, -0.04, 0.5), "head"),
        "ear.R": ((-0.08, -0.04, 0.4), (-0.12, -0.04, 0.5), "head"),
        "tail": ((0.1, 0.13, 0.06), (0.14, 0.2, 0.22), "body"),
    })
    return b


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    nana_rue()
    tomo()
    biscuit()
    pip()
    zuri()
    # line-up in the order of the concept sheet, for previews; shots re-place everyone anyway
    for name, x in (("NanaRue", -1.7), ("Tomo", -0.85), ("Biscuit", -0.2), ("Pip", 0.5), ("Zuri", 1.35)):
        bpy.data.objects[f"{name}_rig"].location.x = x
    if "--save" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(argv[argv.index("--save") + 1]))
        print("saved cast")


main()
