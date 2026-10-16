#!/usr/bin/env python3
"""Assemble rendered frames + dialogue + sound effects + music into a finished MP4 with FFmpeg.

Usage:  python scripts/04_assemble.py episodes/ep01_brush_teeth/episode.json

Per shot, episode.json may contain:
  "dialogue":  [{"id": "l01", "at": 0.5, ...}]          -> audio/<ep>/<id>.wav placed 'at' seconds into the shot
  "sfx_cues":  [{"file": "assets/sfx/pop.wav", "at": 2.2, "volume_db": -6}]
Episode-level:
  "music": {"file": "assets/music/theme.mp3", "volume_db": -14}        one track looped under everything, or
  "music": [{"file": ..., "from_shot": 1, "to_shot": 17, "offset": 0, "volume_db": -18, "loop": true,
             "fade_out": 1.0}, ...]                                     music cues spanning ranges of shots
  "fade":  {"in": 0.5, "out": 1.5}                                      picture and sound fade at the ends
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


def pad_frame_pattern(folder: Path):
    """Return the ffmpeg input pattern for a folder of numbered PNGs (e.g. 0001.png) and the first number."""
    first = sorted(folder.glob("*.png"))[0].stem
    return str(folder / f"%0{len(first)}d.png"), int(first)


def main(episode_path: str) -> None:
    ep = json.loads(Path(episode_path).read_text())
    work = ROOT / "out" / f"_{ep['id']}_work"
    work.mkdir(parents=True, exist_ok=True)

    # 1) video: concatenate every shot's frames
    shot_videos, starts, ends, t = [], {}, {}, 0.0
    for shot in ep["shots"]:
        folder = ROOT / "frames" / ep["id"] / f"shot_{shot['n']:03d}"
        if not folder.exists() or not list(folder.glob("*.png")):
            print(f"[SKIP] no frames for shot {shot['n']}")
            continue
        pattern, first = pad_frame_pattern(folder)
        n_frames = len(list(folder.glob("*.png")))
        clip = work / f"shot_{shot['n']:03d}.mp4"
        run([FFMPEG, "-y", "-loglevel", "error", "-framerate", FPS, "-start_number", first, "-i", pattern,
             "-frames:v", n_frames, "-c:v", "libx264", "-crf", 14, "-pix_fmt", "yuv420p", clip])
        shot_videos.append(clip)
        starts[shot["n"]] = t
        t += n_frames / FPS
        ends[shot["n"]] = t
    if not shot_videos:
        sys.exit("No rendered frames found. Run 03_render_all.py first.")
    total = t

    listing = work / "list.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in shot_videos))
    silent = work / "video_silent.mp4"
    run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", 0, "-i", listing, "-c", "copy", silent])

    # 2) audio: dialogue and sound effects placed on the timeline, plus the music
    inputs, filters, labels = [], [], []

    def place(path, at, gain_db=0.0, label="a"):
        inputs.append(["-i", path])  # input 0 is the silent video, so this one is number len(inputs)
        idx = len(inputs)
        ms = int(at * 1000)
        filters.append(f"[{idx}:a]aresample=48000,adelay={ms}|{ms}:all=1,volume={gain_db}dB[{label}{idx}]")
        labels.append(f"[{label}{idx}]")

    for shot in ep["shots"]:
        if shot["n"] not in starts:
            continue
        start = starts[shot["n"]]
        for line in shot.get("dialogue", []):
            wav = ROOT / "audio" / ep["id"] / f"{line['id']}.wav"
            if wav.exists():
                place(wav, start + line.get("at", 0.0), 0.0, "d")
        for cue in shot.get("sfx_cues", []):
            f = ROOT / cue["file"]
            if f.exists():
                place(f, start + cue["at"], cue.get("volume_db", -6), "s")

    music = ep.get("music")
    if isinstance(music, dict):  # one track looped under everything
        music = [{"file": music["file"], "volume_db": music.get("volume_db", cfg["audio"]["music_duck_db"]), "loop": True}]
    shots_done = sorted(starts)
    for cue in music or []:
        f = ROOT / cue["file"]
        a, b = cue.get("from_shot", shots_done[0]), cue.get("to_shot", shots_done[-1])
        if not f.exists() or a not in starts:
            continue
        m0 = starts[a]
        m1 = ends.get(b, total)
        length = m1 - m0
        inputs.append((["-stream_loop", -1] if cue.get("loop") else []) + ["-ss", cue.get("offset", 0.0), "-i", f])
        idx = len(inputs)
        fade = cue.get("fade_out", 0.0)
        ms = int(m0 * 1000)
        chain = f"[{idx}:a]aresample=48000,atrim=0:{length:.3f},volume={cue.get('volume_db', -16)}dB"
        if fade:
            chain += f",afade=t=out:st={max(0.0, length - fade):.3f}:d={fade}"
        filters.append(chain + f",adelay={ms}|{ms}:all=1[m{idx}]")
        labels.append(f"[m{idx}]")

    fade = ep.get("fade", {})
    final = ROOT / "out" / f"{ep['id']}.mp4"
    vf = []
    if fade.get("in"):
        vf.append(f"fade=t=in:st=0:d={fade['in']}")
    if fade.get("out"):
        vf.append(f"fade=t=out:st={max(0.0, total - fade['out']):.3f}:d={fade['out']}")
    video_codec = ["-c:v", "libx264", "-crf", 16, "-pix_fmt", "yuv420p", "-vf", ",".join(vf)] if vf else ["-c:v", "copy"]
    if labels:
        mix = "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,"
        mix += f"loudnorm=I={cfg['audio']['target_lufs']}:TP=-1.5:LRA=11,atrim=0:{total:.3f}"
        if fade.get("out"):
            mix += f",afade=t=out:st={max(0.0, total - fade['out']):.3f}:d={fade['out']}"
        filters.append(mix + "[aout]")
        script = work / "filter.txt"
        script.write_text(";\n".join(filters))
        run([FFMPEG, "-y", "-loglevel", "error", "-i", silent, *[a for inp in inputs for a in inp],
             "-/filter_complex", script,  # FFmpeg 7+: read the option's value from a file (long filter graphs)
             "-map", "0:v", "-map", "[aout]", *video_codec, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
             final])
    else:
        run([FFMPEG, "-y", "-loglevel", "error", "-i", silent, *video_codec, "-movflags", "+faststart", final])
    print(f"\nDone: {final}  ({total:.1f}s)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
