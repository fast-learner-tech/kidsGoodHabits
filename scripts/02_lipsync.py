#!/usr/bin/env python3
"""Run Rhubarb Lip Sync on every dialogue WAV of an episode.

Usage:  python scripts/02_lipsync.py episodes/ep01_brush_teeth/episode.json
Output: audio/<episode_id>/<line_id>.json   (mouth cues A-H, X)

Rhubarb is happiest with the dialogue text as a hint; we pass it for better accuracy.
"""
import json
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rhubarb = tomllib.loads((ROOT / "config" / "project.toml").read_text())["tools"]["rhubarb"]


def main(episode_path: str) -> None:
    ep = json.loads(Path(episode_path).read_text())
    audio_dir = ROOT / "audio" / ep["id"]
    for shot in ep["shots"]:
        for line in shot.get("dialogue", []):
            wav = audio_dir / f"{line['id']}.wav"
            if not wav.exists():
                print(f"[SKIP] missing {wav.name}; run 01_make_voice.py first")
                continue
            out = audio_dir / f"{line['id']}.json"
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
                tf.write(line["text"])
                dialog_file = tf.name
            cmd = [rhubarb, "-f", "json", "-d", dialog_file, "-o", str(out), str(wav)]
            subprocess.run(cmd, check=True)
            Path(dialog_file).unlink(missing_ok=True)
            print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
