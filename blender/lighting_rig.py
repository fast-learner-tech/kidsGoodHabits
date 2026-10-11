"""Warm, soft, kid-friendly lighting rig: key + fill + rim, plus a gradient sky.

Run inside Blender (Scripting tab, or headless):
  blender -b scene.blend --python blender/lighting_rig.py -- --mood day
Moods: day, morning, evening, night (night stays bright enough for kids; no scary darkness).
"""
import math
import sys

import bpy

MOODS = {
    #            key colour          key W   fill colour       fill W  sky top           sky horizon
    "day": ((1.0, 0.96, 0.88), 900, (0.75, 0.85, 1.0), 300, (0.45, 0.70, 1.0), (0.85, 0.93, 1.0)),
    "morning": ((1.0, 0.85, 0.65), 800, (0.80, 0.85, 1.0), 350, (0.55, 0.75, 1.0), (1.0, 0.88, 0.75)),
    "evening": ((1.0, 0.70, 0.45), 700, (0.65, 0.65, 0.95), 350, (0.35, 0.40, 0.75), (1.0, 0.65, 0.45)),
    "night": ((0.80, 0.85, 1.0), 500, (1.0, 0.85, 0.65), 350, (0.10, 0.12, 0.30), (0.25, 0.28, 0.50)),
}


def area_light(name, location, target, color, watts, size):
    data = bpy.data.lights.new(name, type="AREA")
    data.color, data.energy, data.size = color, watts, size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    direction = (target - obj.location) if hasattr(target, "x") else None
    if direction is not None:
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


def make_sky(top, horizon):
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    ramp.color_ramp.elements[0].color = (*horizon, 1)
    ramp.color_ramp.elements[1].color = (*top, 1)
    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    mood = argv[argv.index("--mood") + 1] if "--mood" in argv else "day"
    key_c, key_w, fill_c, fill_w, sky_top, sky_hor = MOODS[mood]
    from mathutils import Vector

    centre = Vector((0, 0, 1.0))
    area_light("KEY", Vector((4, -5, 5)), centre, key_c, key_w, 4.0)
    area_light("FILL", Vector((-5, -4, 2.5)), centre, fill_c, fill_w, 6.0)
    area_light("RIM", Vector((0, 5, 4)), centre, (1, 1, 1), 400, 3.0)
    make_sky(sky_top, sky_hor)
    print(f"Lighting rig '{mood}' created")
    if "--save" in argv:
        bpy.ops.wm.save_mainfile()


main()
