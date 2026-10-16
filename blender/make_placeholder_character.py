"""Build a simple blockout character ("Pip") with a 9-shape lip-sync mouth, to test the whole pipeline
before you invest time in a final character.

Run:
  blender -b --python blender/make_placeholder_character.py -- --save scenes/test_pip.blend

Creates: Body, Head, Eye_L, Eye_R, Mouth (with shape keys mouth_A..mouth_H, mouth_X).
This is a pipeline test rig, not a final design. Replace it with your sculpted character (see docs/GUIDE.md).
"""
import sys

import bpy

# (x scale, z scale) of the mouth for each Rhubarb shape, relative to the closed rest mouth
MOUTH_SHAPES = {
    "A": (1.0, 1.0),    # closed
    "B": (1.0, 2.5),    # slightly open
    "C": (1.1, 4.0),    # open
    "D": (1.2, 6.0),    # wide open
    "E": (0.75, 4.5),   # rounded O
    "F": (0.50, 3.0),   # pucker
    "G": (1.1, 2.0),    # teeth on lip
    "H": (1.0, 3.5),    # tongue up
    "X": (1.0, 1.0),    # rest
}


def make_material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = 0.55
    return mat


def add_sphere(name, loc, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    # bake scale only: keeping the location on the object leaves mesh coords centred on the object,
    # so mouth shape keys scale around the mouth instead of the world origin
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    return o


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    # start from an empty scene (the startup file has a cube, camera and light)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    skin = make_material("Skin", (0.80, 0.55, 0.38))
    shirt = make_material("Shirt", (0.95, 0.55, 0.15))
    white = make_material("EyeWhite", (1, 1, 1))
    dark = make_material("Dark", (0.05, 0.03, 0.03))

    add_sphere("Body", (0, 0, 0.55), (0.45, 0.35, 0.55), shirt)
    head = add_sphere("Head", (0, 0, 1.45), (0.55, 0.50, 0.50), skin)
    for side, x in (("L", -0.2), ("R", 0.2)):
        e = add_sphere(f"Eye_{side}", (x, -0.42, 1.55), (0.12, 0.06, 0.14), white)
        p = add_sphere(f"Pupil_{side}", (x, -0.47, 1.55), (0.06, 0.03, 0.08), dark)
        e.parent = p.parent = head
    for o in head.children:
        o.matrix_parent_inverse = head.matrix_world.inverted()

    mouth = add_sphere("Mouth", (0, -0.47, 1.28), (0.14, 0.05, 0.02), dark)
    mouth.parent = head
    mouth.matrix_parent_inverse = head.matrix_world.inverted()

    mouth.shape_key_add(name="Basis", from_mix=False)
    base = [v.co.copy() for v in mouth.data.vertices]
    for letter, (sx, sz) in MOUTH_SHAPES.items():
        kb = mouth.shape_key_add(name=f"mouth_{letter}", from_mix=False)
        for i, co in enumerate(base):
            kb.data[i].co.x = co.x * sx
            kb.data[i].co.z = co.z * sz
    # mouth_A / mouth_X keep the closed rest mouth; others open it around the mouth centre

    bpy.ops.object.camera_add(location=(0, -5, 1.2), rotation=(1.5708, 0, 0))
    bpy.context.scene.camera = bpy.context.active_object

    if "--save" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(argv[argv.index("--save") + 1]))
        print("saved")


main()
