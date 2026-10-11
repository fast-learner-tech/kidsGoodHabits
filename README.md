# kidsGoodHabitsCenter

Free, open-source pipeline for making stylized 3D animated kids' videos about daily routines and good habits, from script to YouTube upload.

Everything here uses free tools: Python, Blender, FFmpeg, Kokoro TTS, Rhubarb Lip Sync.

## Read first
`docs/GUIDE.md` is the full step-by-step production guide (setup, characters, backgrounds, scripts, voice, music, render, upload).

## Pipeline at a glance

```
episodes/epXX/episode.json   -> story, shots, dialogue (you write this)
scripts/01_make_voice.py     -> audio/*.wav (Kokoro TTS, offline, Apache-2.0)
scripts/02_lipsync.py        -> audio/*.json (Rhubarb mouth cues)
blender/*.py + your .blend   -> frames/shot_XXX/*.png (Eevee render)
scripts/04_assemble.py       -> out/epXX.mp4 (FFmpeg, 1080p, loudness normalised)
scripts/05_upload_youtube.py -> optional API upload (manual Studio upload also fine)
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/00_check_env.py   # tells you what is still missing
```

Then follow `docs/GUIDE.md` from Phase 1.

## Folder map

| Folder | Purpose |
|---|---|
| `docs/` | Master guide, licensing ledger, YouTube checklist |
| `prompts/` | Style bible, character prompts, background prompts, story prompts |
| `episodes/` | One folder per episode: `episode.json`, script, per-shot notes |
| `assets/` | Characters, sets, props, music, sfx (keep `LICENSES.csv` updated) |
| `blender/` | Headless Blender scripts (render, lighting, lip-sync, placeholder rig) |
| `scripts/` | Python pipeline steps |
| `audio/`, `frames/`, `out/` | Generated output (git-ignored) |

## Status of this scaffold
Python scripts were syntax-checked and the FFmpeg assembly step was tested with synthetic frames. The Blender scripts were written against the current Blender 5.x API but have **not** been run inside Blender yet; expect small fixes on first run.
