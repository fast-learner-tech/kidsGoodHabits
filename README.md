# kidsGoodHabitsCenter

Free, open-source pipeline for making stylized 3D animated kids' videos about daily routines and good habits, from script to YouTube upload.

Every tool is free: Python, Blender, FFmpeg, Kokoro TTS, Rhubarb Lip Sync.

> **Read first:** [docs/GUIDE.md](docs/GUIDE.md) is the full step-by-step production guide (setup, characters, backgrounds, scripts, voice, music, render, upload). This README is the quick reference.

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| Python 3.11+ | Pipeline scripts (uses `tomllib`) | python.org or your package manager |
| Blender 4.2+ (5.x recommended) | Modelling, animation, Eevee rendering | https://www.blender.org/download/ |
| FFmpeg | Final video assembly | https://ffmpeg.org/download.html |
| Rhubarb Lip Sync | Mouth shapes from dialogue audio | https://github.com/DanielSWolf/rhubarb-lip-sync/releases |

If any of these are not on your `PATH`, set their full paths under `[tools]` in [config/project.toml](config/project.toml).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/00_check_env.py   # reports anything still missing
```

To test the whole pipeline before you design real characters, build the placeholder character "Pip":

```bash
blender -b --python blender/make_placeholder_character.py -- --save scenes/test_pip.blend
```

## Pipeline at a glance

```
episodes/<ep>/episode.json      -> story, shots, dialogue (you write this)
scripts/01_make_voice.py        -> audio/<ep>/*.wav   (Kokoro TTS, offline)
scripts/02_lipsync.py           -> audio/<ep>/*.json  (Rhubarb mouth cues)
blender/apply_lipsync.py        -> keyframes mouth shape keys in each shot's .blend
scripts/03_render_all.py        -> frames/<ep>/shot_XXX/*.png (headless Blender)
scripts/04_assemble.py          -> out/<ep>.mp4 (FFmpeg, 1080p, loudness-normalised)
scripts/05_upload_youtube.py    -> optional API upload (manual Studio upload is fine)
```

## Making an episode

Using the sample episode `ep01_brush_teeth`:

```bash
EP=episodes/ep01_brush_teeth/episode.json

python scripts/01_make_voice.py   $EP          # one WAV per dialogue line
python scripts/02_lipsync.py      $EP          # one mouth-cue JSON per line

# Apply mouth cues to a character in a shot (repeat per line/shot)
blender -b scenes/ep01_shot01.blend --python blender/apply_lipsync.py -- \
    --object Mouth --cues audio/ep01_brush_teeth/ep01_l01.json --fps 24 --start-frame 1 --save

python scripts/03_render_all.py   $EP --draft  # fast, half-resolution preview
python scripts/03_render_all.py   $EP          # final quality
python scripts/04_assemble.py     $EP          # -> out/ep01_brush_teeth.mp4
```

Renders go to PNG sequences and skip existing frames, so an interrupted render can be resumed by re-running the same command. Shots whose `.blend` file doesn't exist yet are skipped with a message.

For lighting, `blender/lighting_rig.py` adds a soft key/fill/rim rig and gradient sky:

```bash
blender -b scenes/ep01_shot01.blend --python blender/lighting_rig.py -- --mood morning
```

Moods: `day`, `morning`, `evening`, `night`.

### Episode file format

Each episode lives in `episodes/<id>/episode.json`:

```json
{
  "id": "ep01_brush_teeth",
  "title": "Pip and the Sparkly Smile",
  "music": { "file": "assets/music/theme.mp3", "volume_db": -16 },
  "shots": [
    {
      "n": 1,
      "description": "Wide: sunny bedroom, Pip wakes up and stretches.",
      "blend": "scenes/ep01_shot01.blend",
      "frames": [1, 96],
      "dialogue": [
        { "id": "ep01_l01", "voice": "narrator", "at": 0.5, "text": "Good morning, sunshine!" }
      ]
    }
  ]
}
```

- `voice` is `narrator`, `child` or `parent` (mapped to Kokoro voices in the config), or a raw Kokoro voice id.
- `at` is the time in seconds, relative to the start of the shot, at which the line is placed.
- `frames` is the inclusive Blender frame range to render for that shot.

## Configuration

[config/project.toml](config/project.toml) holds the shared settings:

- `[project]`: fps, resolution, made-for-kids flag
- `[tools]`: paths to `blender`, `ffmpeg`, `rhubarb`
- `[render]`: engine (`EEVEE` / `CYCLES`), samples, draft scale
- `[audio]`: loudness target (LUFS), music ducking, TTS voices and speed

## Folder map

| Folder | Purpose |
|---|---|
| `docs/` | Production guide and YouTube publishing checklist |
| `prompts/` | Style bible, character, background and story/dialogue/music prompts |
| `episodes/` | One folder per episode containing `episode.json` |
| `scenes/` | Per-shot `.blend` files |
| `assets/` | Characters, sets, props, music, sfx, and the `LICENSES.csv` ledger |
| `blender/` | Scripts that run inside Blender (render, lighting, lip-sync, placeholder character) |
| `scripts/` | Numbered Python pipeline steps |
| `audio/`, `frames/`, `out/` | Generated output (git-ignored) |

## Licensing your assets

Record every third-party asset (models, textures, music, sound effects) in [assets/LICENSES.csv](assets/LICENSES.csv) with its source, license, and attribution text. Before publishing, check that each one allows commercial use, because a monetised YouTube channel counts as commercial. Keep original downloads in `assets/_downloads/`, which is git-ignored.

## Publishing

Work through [docs/YOUTUBE_CHECKLIST.md](docs/YOUTUBE_CHECKLIST.md) before each upload. Uploading manually through YouTube Studio is the simplest option. `scripts/05_upload_youtube.py` needs a Google Cloud OAuth client (`client_secret.json` in the project root), and its uploads stay **private** until your API project passes Google's audit. Setup steps are in the script's header.

## Status

The Python scripts have been syntax-checked, and the FFmpeg assembly step has been tested with synthetic frames. The Blender scripts target the Blender 5.x API but have **not** yet been run inside Blender, so expect small fixes on first run.
