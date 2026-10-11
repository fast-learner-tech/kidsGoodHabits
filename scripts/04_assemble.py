#!/usr/bin/env python3
"""Assemble rendered frames + dialogue + music into a finished MP4 with FFmpeg.

Usage:  python scripts/04_assemble.py episodes/ep01_brush_teeth/episode.json [--fps 24]

Per shot, episode.json may contain:
  "dialogue": [{"id": "l01", "at": 0.5, ...}]    -> audio/<ep>/<id>.wav placed at 'at' seconds in that shot
Episode-level:
  "music": {"file": "assets/music/theme.mp3", "volume_db": -14}
Output: out/<episode_id>.mp4   (H.264 CRF 16, AAC 192k, loudness-normalised, yuv420p for YouTube)
"""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cfg = tomllib.loads((ROOT / "config" / "project.toml").read_text())
FFMPEG = cfg["tools"]["ffmpeg"]
FPS = cfg["project"]["fps"]


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def pad_frame_pattern(folder: Path) -> str:
    """Return the ffmpeg input pattern for a folder of numbered PNGs (e.g. 0001.png)."""
    first = sorted(folder.glob("*.png"))[0].stem
    return str(folder / f"%0{len(first)}d.png"), int(first)


def main(episode_path: str) -> None:
    ep = json.loads(Path(episode_path).read_text())
    work = ROOT / "out" / f"_{ep['id']}_work"
    work.mkdir(parents=True, exist_ok=True)

    # 1) video: concatenate every shot's frames
    shot_videos, shot_starts, t = [], [], 0.0
    for shot in ep["shots"]:
        folder = ROOT / "frames" / ep["id"] / f"shot_{shot['n']:03d}"
        if not folder.exists() or not list(folder.glob("*.png")):
            print(f"[SKIP] no frames for shot {shot['n']}")
            continue
        pattern, first = pad_frame_pattern(folder)
        n_frames = len(list(folder.glob("*.png")))
        clip = work / f"shot_{shot['n']:03d}.mp4"
        run([FFMPEG, "-y", "-framerate", FPS, "-start_number", first, "-i", pattern,
             "-frames:v", n_frames, "-c:v", "libx264", "-crf", 14, "-pix_fmt", "yuv420p", clip])
        shot_videos.append(clip)
        shot_starts.append(t)
        t += n_frames / FPS
    if not shot_videos:
        sys.exit("No rendered frames found. Run 03_render_all.py first.")
    total = t

    listing = work / "list.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in shot_videos))
    silent = work / "video_silent.mp4"
    run([FFMPEG, "-y", "-f", "concat", "-safe", 0, "-i", listing, "-c", "copy", silent])

    # 2) audio: place dialogue clips on a timeline, add ducked music
    inputs, filters, labels = [], [], []
    idx = 1  # input 0 is the silent video, audio inputs start at 1
    for shot, start in zip((s for s in ep["shots"]), shot_starts):
        for line in shot.get("dialogue", []):
            wav = ROOT / "audio" / ep["id"] / f"{line['id']}.wav"
            if not wav.exists():
                continue
            delay_ms = int((start + line.get("at", 0.0)) * 1000)
            inputs += ["-i", wav]
            filters.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume=1.0[d{idx}]")
            labels.append(f"[d{idx}]")
            idx += 1
    music = ep.get("music")
    if music and (ROOT / music["file"]).exists():
        inputs += ["-stream_loop", -1, "-i", ROOT / music["file"]]
        filters.append(f"[{idx}:a]atrim=0:{total:.3f},volume={music.get('volume_db', cfg['audio']['music_duck_db'])}dB[m]")
        labels.append("[m]")
        idx += 1

    final = ROOT / "out" / f"{ep['id']}.mp4"
    if labels:
        mix = "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,"
        mix += f"loudnorm=I={cfg['audio']['target_lufs']}:TP=-1.5:LRA=11,atrim=0:{total:.3f}[aout]"
        filters.append(mix)
        run([FFMPEG, "-y", "-i", silent, *inputs, "-filter_complex", ";".join(filters),
             "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", final])
    else:
        run([FFMPEG, "-y", "-i", silent, "-c", "copy", "-movflags", "+faststart", final])
    print(f"\nDone: {final}  ({total:.1f}s)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
