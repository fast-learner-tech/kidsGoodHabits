"""Build the modular sets and shared props for the show (scripted first version).

Run:
  blender -b --factory-startup --python blender/build_sets.py -- --save assets/sets/sets.blend

Follows prompts/03_backgrounds.md: soft rounded shapes, warm colours, no text, one reusable kit.
Collections in the saved file (each set is built around the origin; a shot appends only the ones it needs):
  Bedroom, Bedroom_Day, Bedroom_Night   Pip's bedroom; _Day / _Night hold the window sky and lamp glow
  Bathroom                              sink, step stool, mirror, toothbrush cup, towels, timer shelf, bubbles
  Props                                 Toothbrush_Pip, Toothbrush_Tomo, Toothbrush_Nana, ToothpasteTube,
                                        ToothpasteDot, ToothpasteBlob, SandTimer (parked away from the sets)
Room layout: floor on z=0, back wall at y=+2, side walls at x=+-2.6, open towards -Y where the cameras go.
"""
import math
import sys

import bmesh
import bpy
from mathutils import Vector

ROOM_W, ROOM_D, ROOM_H = 5.2, 4.0, 2.8


def srgb(hex_str):
    h = hex_str.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


_mats = {}


def mat(name, hex_str, rough=0.6, **extra):
    """Principled material. extra: emit, transmission, metal, alpha."""
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = srgb(hex_str)
    b.inputs["Roughness"].default_value = rough
    if "emit" in extra:
        b.inputs["Emission Color"].default_value = srgb(hex_str)
        b.inputs["Emission Strength"].default_value = extra["emit"]
    if "transmission" in extra:
        # see-through by alpha rather than glass transmission: stays clear with few light bounces (fast renders)
        b.inputs["Alpha"].default_value = 1.0 - 0.85 * extra["transmission"]
    if "metal" in extra:
        b.inputs["Metallic"].default_value = extra["metal"]
    if "alpha" in extra:
        b.inputs["Alpha"].default_value = extra["alpha"]
    m.diffuse_color = srgb(hex_str)
    _mats[name] = m
    return m


def textured(name, kind, c1, c2, scale, rough=0.6, mortar=None, vertical=False):
    """Simple procedural surfaces: 'planks', 'tiles', 'patchwork'. vertical=True maps the pattern onto walls."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    coord = nt.nodes.new("ShaderNodeTexCoord")
    tex = nt.nodes.new("ShaderNodeTexBrick")
    tex.inputs["Color1"].default_value = srgb(c1)
    tex.inputs["Color2"].default_value = srgb(c2)
    tex.inputs["Mortar"].default_value = srgb(mortar or c2)
    tex.inputs["Scale"].default_value = scale
    if kind == "planks":
        tex.inputs["Mortar Size"].default_value = 0.004
        tex.inputs["Brick Width"].default_value = 2.0
        tex.inputs["Row Height"].default_value = 0.25
        tex.offset = 0.37
    elif kind == "tiles":
        tex.inputs["Mortar Size"].default_value = 0.012
        tex.inputs["Brick Width"].default_value = 0.5
        tex.inputs["Row Height"].default_value = 0.5
        tex.offset = 0.0
        tex.inputs["Bias"].default_value = -0.4
    else:  # patchwork quilt squares
        tex.inputs["Mortar Size"].default_value = 0.01
        tex.inputs["Brick Width"].default_value = 0.5
        tex.inputs["Row Height"].default_value = 0.5
        tex.offset = 0.0
    if vertical:  # walls run along X (back) or Y (sides): use (x + y, z) so tiles stand upright on every wall
        sep, comb = nt.nodes.new("ShaderNodeSeparateXYZ"), nt.nodes.new("ShaderNodeCombineXYZ")
        add = nt.nodes.new("ShaderNodeMath")
        nt.links.new(coord.outputs["Object"], sep.inputs["Vector"])
        nt.links.new(sep.outputs["X"], add.inputs[0])
        nt.links.new(sep.outputs["Y"], add.inputs[1])
        nt.links.new(add.outputs["Value"], comb.inputs["X"])
        nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
        nt.links.new(comb.outputs["Vector"], tex.inputs["Vector"])
    else:
        nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    m.diffuse_color = srgb(c1)
    return m


class Kit:
    def __init__(self, coll_name):
        self.coll = bpy.data.collections.new(coll_name)
        bpy.context.scene.collection.children.link(self.coll)

    def _own(self, o, m):
        for c in o.users_collection:
            c.objects.unlink(o)
        self.coll.objects.link(o)
        if m:
            o.data.materials.append(m)
        return o

    def box(self, name, loc, size, m, bevel=0.03, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cube_add(location=loc, rotation=[math.radians(a) for a in rot])
        o = bpy.context.active_object
        o.name = name
        o.scale = [s / 2 for s in size]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if bevel:
            mod = o.modifiers.new("Bevel", "BEVEL")
            mod.width, mod.segments, mod.limit_method = bevel, 4, "ANGLE"
            mod.harden_normals = True  # flat faces with smoothly rounded edges
            bpy.ops.object.shade_smooth()
        return self._own(o, m)

    def cyl(self, name, loc, r, depth, m, rot=(0, 0, 0), verts=48, bevel=0.0):
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc,
                                            rotation=[math.radians(a) for a in rot])
        o = bpy.context.active_object
        o.name = name
        if bevel:
            mod = o.modifiers.new("Bevel", "BEVEL")
            mod.width, mod.segments, mod.limit_method = bevel, 4, "ANGLE"
        for p in o.data.polygons:
            p.use_smooth = len(p.vertices) == 4  # smooth sides, flat caps
        return self._own(o, m)

    def ball(self, name, loc, radii, m, seg=32):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, location=loc)
        o = bpy.context.active_object
        o.name = name
        o.scale = radii if isinstance(radii, (tuple, list)) else (radii,) * 3
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.object.shade_smooth()
        return self._own(o, m)

    def cone(self, name, loc, r1, r2, depth, m, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=r1, radius2=r2, depth=depth, location=loc,
                                        rotation=[math.radians(a) for a in rot])
        o = bpy.context.active_object
        o.name = name
        bpy.ops.object.shade_smooth()
        return self._own(o, m)

    def torus(self, name, loc, major, minor, m, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_torus_add(location=loc, major_radius=major, minor_radius=minor, major_segments=64,
                                         minor_segments=16, rotation=[math.radians(a) for a in rot])
        o = bpy.context.active_object
        o.name = name
        bpy.ops.object.shade_smooth()
        return self._own(o, m)

    def plane(self, name, loc, size, m, rot=(90, 0, 0)):
        bpy.ops.mesh.primitive_plane_add(location=loc, rotation=[math.radians(a) for a in rot])
        o = bpy.context.active_object
        o.name = name
        o.scale = (size[0] / 2, size[1] / 2, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        return self._own(o, m)


def room_shell(k, prefix, floor_m, wall_m, skirting_m, window=True):
    """Floor, back wall and two side walls (with an optional window hole on the back wall)."""
    k.box(f"{prefix}_Floor", (0, 0, -0.05), (ROOM_W + 0.4, ROOM_D + 2.0, 0.1), floor_m, bevel=0)
    if window:  # back wall built in four pieces around a 1.3 x 1.1 m window opening
        wx, wz, ww, wh = -0.9, 1.55, 1.3, 1.1
        k.box(f"{prefix}_WallBack_L", ((-ROOM_W / 2 + wx - ww / 2) / 2, ROOM_D / 2 + 0.05, ROOM_H / 2),
              (wx - ww / 2 + ROOM_W / 2, 0.1, ROOM_H), wall_m, bevel=0)
        k.box(f"{prefix}_WallBack_R", ((wx + ww / 2 + ROOM_W / 2) / 2, ROOM_D / 2 + 0.05, ROOM_H / 2),
              (ROOM_W / 2 - wx - ww / 2, 0.1, ROOM_H), wall_m, bevel=0)
        k.box(f"{prefix}_WallBack_B", (wx, ROOM_D / 2 + 0.05, (wz - wh / 2) / 2), (ww, 0.1, wz - wh / 2), wall_m, bevel=0)
        k.box(f"{prefix}_WallBack_T", (wx, ROOM_D / 2 + 0.05, (ROOM_H + wz + wh / 2) / 2), (ww, 0.1, ROOM_H - wz - wh / 2),
              wall_m, bevel=0)
    else:
        k.box(f"{prefix}_WallBack", (0, ROOM_D / 2 + 0.05, ROOM_H / 2), (ROOM_W, 0.1, ROOM_H), wall_m, bevel=0)
    for side, x in (("L", -1), ("R", 1)):
        k.box(f"{prefix}_Wall{side}", (x * (ROOM_W / 2 + 0.05), 0, ROOM_H / 2), (0.1, ROOM_D + 2.0, ROOM_H), wall_m, bevel=0)
        k.box(f"{prefix}_Skirt{side}", (x * (ROOM_W / 2 - 0.01), 0, 0.05), (0.03, ROOM_D + 2.0, 0.1), skirting_m, bevel=0.005)
    k.box(f"{prefix}_Ceiling", (0, 0, ROOM_H + 0.05), (ROOM_W + 0.4, ROOM_D + 2.0, 0.1), mat("Ceiling", "#FBF8F2", 0.9), bevel=0)
    k.box(f"{prefix}_SkirtBack", (0, ROOM_D / 2 - 0.01, 0.05), (ROOM_W, 0.03, 0.1), skirting_m, bevel=0.005)


def window_frame(k, prefix, white):
    wx, wz, ww, wh = -0.9, 1.55, 1.3, 1.1
    y = ROOM_D / 2 + 0.05
    for name, loc, size in (("Top", (wx, y - 0.02, wz + wh / 2), (ww + 0.12, 0.14, 0.08)),
                            ("Bot", (wx, y - 0.06, wz - wh / 2), (ww + 0.2, 0.22, 0.07)),
                            ("L", (wx - ww / 2, y - 0.02, wz), (0.08, 0.14, wh)),
                            ("R", (wx + ww / 2, y - 0.02, wz), (0.08, 0.14, wh)),
                            ("MidV", (wx, y, wz), (0.04, 0.06, wh)),
                            ("MidH", (wx, y, wz), (ww, 0.06, 0.04))):
        k.box(f"{prefix}_Window{name}", loc, size, white, bevel=0.01)
    return wx, wz, ww, wh


def sky_card(k, name, wx, wz, top, bottom, strength):
    """Emissive gradient card behind the window: reads as sky and lights the room softly."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    coord, sep = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp, em, out = nt.nodes.new("ShaderNodeValToRGB"), nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    ramp.color_ramp.elements[0].color = srgb(bottom)
    ramp.color_ramp.elements[1].color = srgb(top)
    em.inputs["Strength"].default_value = strength
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return k.plane(name, (wx, ROOM_D / 2 + 1.2, wz), (4.0, 3.0), m)


# ---------------------------------------------------------------- bedroom

def bedroom():
    k = Kit("Bedroom")
    floor = textured("Wood_Floor", "planks", "#C8955E", "#B98450", 3.0, 0.55, mortar="#8E6236")
    wall = mat("Wall_Cream", "#F6EBD9", 0.9)
    white = mat("Paint_White", "#FBF8F2", 0.5)
    room_shell(k, "Bed", floor, wall, white)
    wx, wz, ww, wh = window_frame(k, "Bed", white)
    curtain = mat("Curtain_Sheer", "#FFFFFF", 0.8, transmission=0.6)
    for side, x in (("L", -1), ("R", 1)):
        k.box(f"Bed_Curtain{side}", (wx + x * (ww / 2 + 0.12), ROOM_D / 2 - 0.08, wz + 0.05), (0.32, 0.05, wh + 0.5), curtain, bevel=0.02)
    k.cyl("Bed_CurtainRod", (wx, ROOM_D / 2 - 0.08, wz + wh / 2 + 0.3), 0.015, ww + 0.9, mat("Wood_Light", "#D9B07A", 0.5), rot=(0, 90, 0))

    # bed against the right wall
    wood = mat("Wood_Light", "#D9B07A", 0.5)
    quilt = textured("Quilt_Patchwork", "patchwork", "#7FD1C7", "#F7C631", 6.0, 0.85, mortar="#F08A6B")
    k.box("Bed_Frame", (1.55, 0.6, 0.18), (1.1, 1.9, 0.3), wood, bevel=0.06)
    k.box("Bed_Headboard", (1.55, 1.58, 0.55), (1.1, 0.08, 0.9), wood, bevel=0.06)
    k.box("Bed_Mattress", (1.55, 0.6, 0.4), (1.0, 1.8, 0.16), mat("Fabric_White", "#F7F4EE", 0.9), bevel=0.06)
    k.box("Bed_Pillow", (1.55, 1.3, 0.53), (0.7, 0.35, 0.12), mat("Fabric_White", "#F7F4EE", 0.9), bevel=0.06)
    k.box("Bed_Quilt", (1.55, 0.35, 0.5), (1.08, 1.3, 0.06), quilt, bevel=0.03)

    # bookshelf with toy blocks, left of the window
    k.box("Bed_Shelf", (-2.15, 1.75, 0.6), (0.7, 0.35, 1.2), wood, bevel=0.03)
    block_cols = ["#E8574A", "#F7C631", "#4FA3E0", "#57B45A", "#9B6BD3", "#F08A6B"]
    for row, z in enumerate((0.42, 0.82)):
        k.box(f"Bed_ShelfBoard{row}", (-2.15, 1.62, z - 0.03), (0.66, 0.3, 0.03), white, bevel=0.005)
        for i in range(4):
            k.box(f"Bed_Block{row}{i}", (-2.4 + i * 0.16, 1.62, z + 0.06), (0.12, 0.12, 0.12),
                  mat(f"Toy_{block_cols[(i + row * 2) % 6]}", block_cols[(i + row * 2) % 6], 0.4), bevel=0.02)

    # round rug and a plush toy
    k.cyl("Bed_Rug", (0.2, -0.2, 0.01), 1.0, 0.02, mat("Rug_Coral", "#F2A28B", 0.95), bevel=0.008)
    plush = mat("Plush_Lilac", "#BBA6E0", 0.95)
    k.ball("Bed_PlushBody", (1.2, 0.0, 0.62), (0.12, 0.1, 0.13), plush)
    k.ball("Bed_PlushHead", (1.2, -0.02, 0.8), 0.09, plush)
    for x in (-0.06, 0.06):
        k.ball(f"Bed_PlushEar{x:+.2f}", (1.2 + x, -0.02, 0.88), 0.035, plush)

    # bedside table with lamp and picture books, door on the left wall
    k.box("Bed_SideTable", (0.75, 1.65, 0.28), (0.45, 0.4, 0.56), wood, bevel=0.03)
    k.cyl("Bed_LampBase", (0.75, 1.7, 0.6), 0.07, 0.08, white, bevel=0.01)
    k.cyl("Bed_LampStem", (0.75, 1.7, 0.72), 0.015, 0.2, white)
    k.cone("Bed_LampShade", (0.75, 1.7, 0.88), 0.16, 0.1, 0.18, mat("Lampshade", "#FFE7B0", 0.8, transmission=0.4))
    for i, col in enumerate(("#4FA3E0", "#F7C631", "#E8574A")):
        k.box(f"Bed_Book{i}", (0.62, 1.58, 0.58 + i * 0.035), (0.2, 0.15, 0.03), mat(f"Book_{col}", col, 0.6),
              bevel=0.004, rot=(0, 0, i * 8))
    k.box("Bed_Door", (-ROOM_W / 2 + 0.02, -0.6, 1.0), (0.04, 0.9, 2.0), mat("Door_Mint", "#9ED9C8", 0.6), bevel=0.02)
    k.ball("Bed_DoorKnob", (-ROOM_W / 2 + 0.07, -0.95, 0.95), 0.035, mat("Brass", "#D8B45A", 0.3, metal=1.0))

    day = Kit("Bedroom_Day")
    sky_card(day, "Bed_SkyDay", wx, wz, "#7EC3F2", "#FFE9C7", 3.0)
    night = Kit("Bedroom_Night")
    sky_card(night, "Bed_SkyNight", wx, wz, "#1C2457", "#3A3F7A", 1.0)
    night.ball("Bed_Moon", (wx + 0.3, ROOM_D / 2 + 1.1, wz + 0.25), 0.12, mat("Moon", "#FFF3C4", 0.5, emit=6.0))
    for i, (dx, dz) in enumerate(((-0.4, 0.3), (-0.2, -0.1), (0.1, 0.4), (0.45, -0.2), (-0.5, -0.3))):
        night.ball(f"Bed_Star{i}", (wx + dx, ROOM_D / 2 + 1.15, wz + dz), 0.02, mat("Star", "#FFFFFF", 0.5, emit=10.0), seg=12)
    bulb = bpy.data.lights.new("Bed_LampGlow", "POINT")
    bulb.energy, bulb.color, bulb.shadow_soft_size = 60, (1.0, 0.8, 0.55), 0.1
    lamp = bpy.data.objects.new("Bed_LampGlow", bulb)
    lamp.location = (0.75, 1.7, 0.86)
    night.coll.objects.link(lamp)


# ---------------------------------------------------------------- bathroom

def bathroom():
    k = Kit("Bathroom")
    tiles = textured("Tiles_Aqua", "tiles", "#9ED9D2", "#8FCFC7", 6.0, 0.25, mortar="#F4FBFA", vertical=True)
    floor = textured("Tiles_Floor", "tiles", "#F2F4F3", "#E4E9E8", 3.0, 0.4, mortar="#C9D3D2")
    white = mat("Ceramic_White", "#FBFBFA", 0.15)
    room_shell(k, "Bath", floor, tiles, white, window=False)

    # low vanity with basin and tap, centred on the back wall
    k.box("Bath_Vanity", (0, 1.72, 0.32), (1.2, 0.5, 0.64), mat("Vanity_Mint", "#BFE8DC", 0.5), bevel=0.04)
    k.box("Bath_Counter", (0, 1.72, 0.66), (1.3, 0.56, 0.05), white, bevel=0.015)
    # vessel basin: the lower half of a squashed sphere, open at the top, given a wall thickness
    basin = k.ball("Bath_Basin", (0, 1.7, 0.8), (0.3, 0.22, 0.12), white, seg=48)
    bm = bmesh.new()
    bm.from_mesh(basin.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.001], context="VERTS")
    bm.to_mesh(basin.data)
    bm.free()
    basin.modifiers.new("Wall", "SOLIDIFY").thickness = 0.02
    tap = mat("Chrome", "#D9DEE2", 0.15, metal=1.0)
    k.cyl("Bath_TapStem", (0, 1.92, 0.76), 0.025, 0.16, tap)
    k.cyl("Bath_TapSpout", (0, 1.85, 0.84), 0.02, 0.15, tap, rot=(90, 0, 0))
    # round mirror (Pip looks into it in shot 24)
    k.torus("Bath_MirrorFrame", (0, ROOM_D / 2 - 0.02, 1.35), 0.38, 0.035, mat("Frame_Coral", "#F08A6B", 0.4), rot=(90, 0, 0))
    k.cyl("Bath_Mirror", (0, ROOM_D / 2 - 0.01, 1.35), 0.37, 0.01, mat("Mirror", "#E8F0F2", 0.02, metal=1.0), rot=(90, 0, 0))
    # step stool
    stool = mat("Stool_Yellow", "#F7C631", 0.45)
    k.box("Bath_Stool", (0, 1.2, 0.1), (0.55, 0.35, 0.2), stool, bevel=0.03)
    # cup of toothbrushes on the counter
    k.cyl("Bath_Cup", (0.48, 1.78, 0.75), 0.05, 0.13, mat("Cup_Coral", "#F08A6B", 0.3), bevel=0.01)
    for i, col in enumerate(("#E8574A", "#4FA3E0", "#57B45A")):
        k.cyl(f"Bath_CupBrush{i}", (0.46 + i * 0.02, 1.78, 0.86), 0.008, 0.2, mat(f"Brush_{col}", col, 0.3), rot=(0, -10 + i * 10, 0))
    # towel rail with fluffy towels on the right wall
    k.cyl("Bath_Rail", (ROOM_W / 2 - 0.08, 0.5, 1.0), 0.015, 1.2, tap, rot=(90, 0, 0))
    for i, (y, col) in enumerate(((0.25, "#F2A28B"), (0.75, "#7FD1C7"))):
        k.box(f"Bath_Towel{i}", (ROOM_W / 2 - 0.1, y, 0.75), (0.08, 0.45, 0.55), mat(f"Towel_{col}", col, 1.0), bevel=0.04)
    # shelf for the sand timer and toothpaste
    k.box("Bath_Shelf", (-0.95, ROOM_D / 2 - 0.12, 1.0), (0.6, 0.22, 0.04), white, bevel=0.01)
    k.box("Bath_ShelfPlant", (-1.1, ROOM_D / 2 - 0.12, 1.07), (0.1, 0.1, 0.1), mat("Pot_Terracotta", "#D9845A", 0.6), bevel=0.02)
    k.ball("Bath_ShelfPlantLeaves", (-1.1, ROOM_D / 2 - 0.12, 1.17), 0.08, mat("Leaves", "#57B45A", 0.7))
    # a few floating soap bubbles (soft, slow, never flashing)
    bubble = mat("Bubble", "#E9F7FF", 0.0, transmission=1.0)
    for i, (x, y, z, r) in enumerate(((-0.7, 1.3, 1.6, 0.05), (0.8, 1.1, 1.8, 0.07), (-1.4, 0.8, 1.3, 0.04), (1.3, 1.4, 1.5, 0.05))):
        k.ball(f"Bath_Bubble{i}", (x, y, z), r, bubble)
    k.box("Bath_Bathmat", (0, 0.8, 0.01), (0.9, 0.6, 0.02), mat("Mat_Mint", "#7FD1C7", 1.0), bevel=0.01)
    return basin


# ---------------------------------------------------------------- props

def props():
    k = Kit("Props")
    park = Vector((0, -20, 0))  # parked out of shot; shots move what they use
    bristle = mat("Bristles", "#F7F7F7", 0.8)
    for i, (who, col) in enumerate((("Pip", "#E8574A"), ("Tomo", "#57B45A"), ("Nana", "#4FA3E0"))):
        o = park + Vector((i * 0.3, 0, 0))
        handle = k.box(f"Toothbrush_{who}", o, (0.025, 0.02, 0.18), mat(f"Brush_{col}", col, 0.3), bevel=0.008)
        head = k.box(f"Toothbrush_{who}_Bristles", o + Vector((0, -0.015, 0.075)), (0.02, 0.02, 0.04), bristle, bevel=0.004)
        head.parent = handle
        head.matrix_parent_inverse = handle.matrix_world.inverted()
    paste = mat("Toothpaste", "#C9F2E9", 0.3)
    tube = k.box("ToothpasteTube", park + Vector((1.2, 0, 0)), (0.05, 0.03, 0.16), mat("Tube_White", "#FBFBFA", 0.3), bevel=0.012)
    cap = k.cyl("ToothpasteTube_Cap", park + Vector((1.2, 0, 0.09)), 0.015, 0.025, mat("Cap_Mint", "#2BB5A0", 0.3))
    cap.parent = tube
    cap.matrix_parent_inverse = tube.matrix_world.inverted()
    k.ball("ToothpasteDot", park + Vector((1.5, 0, 0)), (0.009, 0.009, 0.007), paste, seg=16)  # pea-sized
    k.ball("ToothpasteBlob", park + Vector((1.8, 0, 0)), (0.03, 0.03, 0.05), paste)            # Tomo's "too much"
    glass = mat("TimerGlass", "#FFFFFF", 0.0, transmission=1.0)
    sand = mat("Sand", "#F2C46B", 0.8)
    timer = k.cyl("SandTimer", park + Vector((2.2, 0, 0)), 0.05, 0.015, mat("Wood_Light", "#D9B07A", 0.5))
    for name, dz, geo in (("TimerTop", 0.17, "cyl"), ("TimerGlassUp", 0.125, "coneD"), ("TimerGlassDown", 0.045, "coneU"),
                          ("SandBottom", 0.03, "sand")):
        loc = park + Vector((2.2, 0, dz))
        if geo == "cyl":
            o = k.cyl(f"SandTimer_{name}", loc, 0.05, 0.015, mat("Wood_Light", "#D9B07A", 0.5))
        elif geo == "coneD":
            o = k.cone(f"SandTimer_{name}", loc, 0.008, 0.04, 0.08, glass)
        elif geo == "coneU":
            o = k.cone(f"SandTimer_{name}", loc, 0.04, 0.008, 0.08, glass)
        else:
            o = k.cone(f"SandTimer_{name}", loc, 0.032, 0.01, 0.03, sand)
        o.parent = timer
        o.matrix_parent_inverse = timer.matrix_world.inverted()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bedroom()
    bathroom()
    props()
    if "--save" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(argv[argv.index("--save") + 1]))
        print("saved sets")


main()
