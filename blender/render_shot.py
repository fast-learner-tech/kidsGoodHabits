"""Headless Eevee render of one shot to a PNG sequence.

Run:
  blender -b scenes/ep01_shot01.blend --python blender/render_shot.py -- \
      --start 1 --end 120 --out frames/ep01/shot_001/ --samples 64 --scale 100

Always render to an image sequence (never straight to video) so a crash never costs you the whole shot.
Re-running skips frames that already exist (overwrite is off), so renders are resumable.
"""
import argparse
import sys

import bpy


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=None)
    p.add_argument("--end", type=int, default=None)
    p.add_argument("--out", required=True, help="output folder (trailing slash)")
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--scale", type=int, default=100, help="resolution percent")
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--engine", default="EEVEE", choices=["EEVEE", "CYCLES"])
    return p.parse_args(argv)


def pick_eevee_id():
    """Blender 5.x uses BLENDER_EEVEE; 4.2-4.5 use BLENDER_EEVEE_NEXT."""
    ids = {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    return "BLENDER_EEVEE" if "BLENDER_EEVEE" in ids else "BLENDER_EEVEE_NEXT"


def main():
    a = parse_args()
    sc = bpy.context.scene
    r = sc.render

    r.fps = a.fps
    r.resolution_x, r.resolution_y, r.resolution_percentage = a.width, a.height, a.scale
    if a.start is not None:
        sc.frame_start = a.start
    if a.end is not None:
        sc.frame_end = a.end

    if a.engine == "CYCLES":
        r.engine = "CYCLES"
        sc.cycles.samples = a.samples
        sc.cycles.use_denoising = True
    else:
        r.engine = pick_eevee_id()
        sc.eevee.taa_render_samples = a.samples

    r.use_motion_blur = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    r.use_overwrite = False  # resumable
    r.use_placeholder = True
    r.filepath = a.out if a.out.endswith(("/", "\\")) else a.out + "/"

    try:
        sc.view_settings.view_transform = "AgX"  # soft highlight roll-off, good for stylized looks
    except TypeError:
        pass

    print(f"Rendering frames {sc.frame_start}-{sc.frame_end} with {r.engine} to {r.filepath}")
    bpy.ops.render.render(animation=True)


main()
