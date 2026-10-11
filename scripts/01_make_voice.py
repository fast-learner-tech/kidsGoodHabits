#!/usr/bin/env python3
"""Generate one WAV per dialogue line with Kokoro TTS (offline, Apache-2.0).

Usage:  python scripts/01_make_voice.py episodes/ep01_brush_teeth/episode.json
Output: audio/<episode_id>/<line_id>.wav   (24 kHz mono)
"""
import json
import sys
import tomllib
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
cfg = tomllib.loads((ROOT / "config" / "project.toml").read_text())["audio"]

VOICES = {
    "narrator": cfg["tts_voice_narrator"],
    "child": cfg["tts_voice_child"],
    "parent": cfg["tts_voice_parent"],
}


def main(episode_path: str) -> None:
    from kokoro import KPipeline  # imported late so --help works without it

    ep = json.loads(Path(episode_path).read_text())
    out_dir = ROOT / "audio" / ep["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    pipeline = KPipeline(lang_code="a")  # 'a' = American English; 'b' = British

    for shot in ep["shots"]:
        for line in shot.get("dialogue", []):
            voice = VOICES.get(line["voice"], line["voice"])  # allow raw Kokoro voice ids
            chunks = []
            for _, _, audio in pipeline(line["text"], voice=voice, speed=cfg["tts_speed"]):
                chunks.append(np.asarray(audio))
            if not chunks:
                print(f"[WARN] no audio for {line['id']}")
                continue
            wav = np.concatenate(chunks)
            target = out_dir / f"{line['id']}.wav"
            sf.write(target, wav, 24000)
            print(f"wrote {target.relative_to(ROOT)} ({len(wav) / 24000:.1f}s)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
