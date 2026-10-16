#!/usr/bin/env python3
"""Render every shot of an episode by calling Blender headless once per shot.

Usage:
  python scripts/03_render_all.py episodes/ep01_brush_teeth/episode.json --draft
  python scripts/03_render_all.py episodes/ep01_brush_teeth/episode.json            # final quality

Each shot in episode.json needs:  "blend": "scenes/ep01_shot01.blend", "frames": [1, 120]
Frames land in frames/<episode_id>/shot_XXX/ and existing frames are skipped (resumable).
"""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cfg = tomllib.loads((ROOT / "config" / "project.toml").read_text())


def main(episode_path: str, draft: bool) -> None:
    ep = json.loads(Path(episode_path).read_text())
    rc = cfg["render"]
    samples = rc.get("draft_samples", 32) if draft else rc["samples"]
    scale = rc["draft_scale"] if draft else 100
    step = rc.get("draft_step", 1) if draft else 1
    bounces = rc.get("draft_bounces", 4) if draft else rc.get("bounces", 4)
    for shot in ep["shots"]:
        blend = ROOT / shot["blend"]
        if not blend.exists():
            print(f"[SKIP] shot {shot['n']}: {blend} not found yet")
            continue
        out = ROOT / "frames" / ep["id"] / f"shot_{shot['n']:03d}"
        out.mkdir(parents=True, exist_ok=True)
        cmd = [
            cfg["tools"]["blender"], "-b", str(blend),
            "--python", str(ROOT / "blender" / "render_shot.py"), "--",
            "--start", str(shot["frames"][0]), "--end", str(shot["frames"][1]),
            "--out", str(out) + "/", "--samples", str(samples), "--scale", str(scale),
            "--fps", str(cfg["project"]["fps"]),
            "--width", str(cfg["project"]["width"]), "--height", str(cfg["project"]["height"]),
            "--engine", cfg["render"]["engine"], "--bounces", str(bounces), "--step", str(step),
        ] + (["--no-blur"] if draft else [])
        print(">>", " ".join(cmd))
        subprocess.run(cmd, check=True)
        if step > 1:
            hold_frames(out, shot["frames"][0], shot["frames"][1])


def hold_frames(folder: Path, first: int, last: int) -> None:
    """After an 'on twos' render, copy each rendered frame into the gap after it (complete sequence for FFmpeg)."""
    import shutil
    prev = None
    for f in range(first, last + 1):
        png = folder / f"{f:04d}.png"
        if png.exists() and png.stat().st_size > 0:
            prev = png
        elif prev is not None:
            shutil.copyfile(prev, png)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], draft="--draft" in sys.argv)
