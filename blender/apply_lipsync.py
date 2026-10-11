"""Apply Rhubarb mouth cues to a mesh that has shape keys mouth_A ... mouth_H and mouth_X.

Run:
  blender -b scenes/ep01_shot01.blend --python blender/apply_lipsync.py -- \
      --object Mouth --cues audio/ep01/line01.json --fps 24 --start-frame 1

Add --save to write the .blend back after keyframing.
The mouth shapes follow Rhubarb's letters:
  A closed (P B M)   B slightly open (K S T)   C open (E)   D wide open (A)
  E rounded (O)      F puckered (U W)          G teeth on lip (F V)   H tongue up (L)   X rest/silence
"""
import json
import sys

import bpy

SHAPES = ["A", "B", "C", "D", "E", "F", "G", "H", "X"]


def arg(name, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[argv.index(name) + 1] if name in argv else default


def main():
    obj_name = arg("--object")
    cues_path = arg("--cues")
    fps = int(arg("--fps", 24))
    start_frame = int(arg("--start-frame", 1))
    if not obj_name or not cues_path:
        raise SystemExit("--object and --cues are required")

    obj = bpy.data.objects[obj_name]
    keys = obj.data.shape_keys.key_blocks
    blocks = {s: keys.get(f"mouth_{s}") for s in SHAPES}
    missing = [s for s, b in blocks.items() if b is None]
    if missing:
        raise SystemExit(f"Object '{obj_name}' lacks shape keys: {['mouth_' + m for m in missing]}")

    cues = json.load(open(cues_path))["mouthCues"]
    prev = None
    for cue in cues:
        frame = start_frame + round(cue["start"] * fps)
        if prev is not None and frame > start_frame:
            # hold the previous shape until just before the change so mouths snap instead of drifting
            for s, b in blocks.items():
                b.value = 1.0 if s == prev else 0.0
                b.keyframe_insert("value", frame=frame - 1)
        for s, b in blocks.items():
            b.value = 1.0 if s == cue["value"] else 0.0
            b.keyframe_insert("value", frame=frame)
        prev = cue["value"]
    print(f"Applied {len(cues)} mouth cues to {obj_name}")
    if "--save" in sys.argv:
        bpy.ops.wm.save_mainfile()


main()
