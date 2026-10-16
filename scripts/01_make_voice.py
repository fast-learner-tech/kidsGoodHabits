#!/usr/bin/env python3
"""Generate one WAV per dialogue line with Kokoro TTS (offline, Apache-2.0).

Usage:  python scripts/01_make_voice.py episodes/ep01_brush_teeth/episode.json
Output: audio/<episode_id>/<line_id>.wav   (24 kHz mono)

"voice" in episode.json is a cast name from [audio.cast] in config/project.toml (pip, tomo, ...),
one of the older names narrator/child/parent, or a raw Kokoro voice id (af_heart, bf_emma, ...).
"""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
project = tomllib.loads((ROOT / "config" / "project.toml").read_text())
cfg = project["audio"]
FFMPEG = project["tools"]["ffmpeg"]
FPS = project["project"]["fps"]
RATE = 24000

VOICES = {
    "narrator": cfg["tts_voice_narrator"],
    "child": cfg["tts_voice_child"],
    "parent": cfg["tts_voice_parent"],
}


def voice_settings(name: str) -> dict:
    """Return {voice, speed, semitones} for a cast name, old voice name or raw Kokoro id."""
    cast = cfg.get("cast", {})
    if name in cast:
        return {"speed": cfg["tts_speed"], "semitones": 0, **cast[name]}
    return {"voice": VOICES.get(name, name), "speed": cfg["tts_speed"], "semitones": 0}


def pitch_shift(path: Path, semitones: float) -> None:
    """Raise/lower pitch without changing speed (the FFmpeg trick from the voice-casting notes)."""
    ratio = 2 ** (semitones / 12)
    tmp = path.with_suffix(".pitch.wav")
    af = f"asetrate={RATE}*{ratio:.5f},aresample={RATE},atempo={1 / ratio:.5f}"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(path), "-af", af, str(tmp)], check=True)
    tmp.replace(path)


def fit_length(path: Path, seconds: float) -> None:
    """Time-stretch a clip to an exact length without changing its pitch."""
    factor = sf.info(path).duration / seconds
    factor = min(max(factor, 0.5), 2.0)  # FFmpeg's atempo range
    tmp = path.with_suffix(".fit.wav")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(path), "-af", f"atempo={factor:.5f}", str(tmp)],
                   check=True)
    tmp.replace(path)


def main(episode_path: str) -> None:
    from kokoro import KPipeline  # imported late so --help works without it

    ep = json.loads(Path(episode_path).read_text())
    out_dir = ROOT / "audio" / ep["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    pipelines = {}  # one per language: 'a' = American English, 'b' = British (from the voice id prefix)

    for shot in ep["shots"]:
        shot_len = (shot["frames"][1] - shot["frames"][0] + 1) / FPS
        for line in shot.get("dialogue", []):
            s = voice_settings(line["voice"])
            lang = s["voice"][0]
            if lang not in pipelines:
                pipelines[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
            chunks = []
            for _, _, audio in pipelines[lang](line["text"], voice=s["voice"], speed=s["speed"]):
                chunks.append(np.asarray(audio))
            if not chunks:
                print(f"[WARN] no audio for {line['id']}")
                continue
            wav = np.concatenate(chunks)
            target = out_dir / f"{line['id']}.wav"
            sf.write(target, wav, RATE)
            if s["semitones"]:
                pitch_shift(target, s["semitones"])
            if line.get("chant_bars"):  # song lines are chanted on the beat: fit them to whole bars
                bar = 4 * 60 / ep["song"]["bpm"]
                fit_length(target, line["chant_bars"] * bar * 0.94)
            length = sf.info(target).duration
            print(f"wrote {target.relative_to(ROOT)} ({length:.1f}s)")
            end = line.get("at", 0.0) + length
            if end > shot_len:
                print(f"[WARN] {line['id']} ends at {end:.1f}s but shot {shot['n']} is only {shot_len:.1f}s long")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
