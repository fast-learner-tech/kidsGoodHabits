"""Build one animated shot (.blend) from episode.json and the episode's staging script.

Run (one Blender process per shot, always starting from the sets file):
  blender -b assets/sets/sets.blend --python blender/build_shot.py -- \
      --episode episodes/ep01_brush_teeth/episode.json --shot 6

The staging script (default: staging.py next to episode.json) defines shot_01(s) ... shot_NN(s), each taking a
blender/shotlib.py Shot. The result is saved to the shot's "blend" path and rendered by scripts/03_render_all.py.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "blender"))
import shotlib  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--episode", required=True)
    p.add_argument("--shot", type=int, required=True)
    p.add_argument("--staging", default=None)
    a = p.parse_args(argv)

    ep_path = (ROOT / a.episode).resolve()
    ep = json.loads(ep_path.read_text())
    staging_path = Path(a.staging) if a.staging else ep_path.parent / "staging.py"
    spec = importlib.util.spec_from_file_location("staging", staging_path)
    staging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(staging)

    s = shotlib.Shot(ep, a.shot)
    getattr(staging, f"shot_{a.shot:02d}")(s)
    s.finish()
    out = ROOT / s.data["blend"]
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), relative_remap=True, compress=True)
    print(f"built shot {a.shot}: {out.relative_to(ROOT)} ({s.end} frames)")


main()
