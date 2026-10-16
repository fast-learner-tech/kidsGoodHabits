# kidsGoodHabitsCenter: Production Guide (zero-cost pipeline)

From an empty VSCode window to a finished video on YouTube, using only free tools.

## 0. Read this first: what is realistic

- **Language: Python.** It has the largest free ecosystem for this job, and Blender itself is scripted in Python. One language runs your whole pipeline (voice, lip-sync, rendering, editing, upload).
- **Engine: Blender** (free, open source). Current stable at the time of writing is the 5.1 series (5.1.2 shipped May 2026), with 4.5 LTS as the long-term-support option. You own everything you render.
- **Quality target:** a polished, stylized 3D look (soft lighting, rounded shapes, expressive faces) is very achievable alone with Blender's EEVEE renderer. A feature-film Pixar render comes from hundreds of artists and render farms. Aim for "premium kids' series" quality first, and you can improve per episode.
- **Cost:** $0 in software. Your costs are your computer and your time. Plan on roughly 2-4 weeks for your first episode (most of it is learning and building reusable assets) and about 3-7 days per episode afterwards once characters, sets and rigs exist.
- **Hardware:** any computer from the last 5-6 years with 16 GB RAM and a mid-range GPU (6 GB VRAM or more is comfortable) works with EEVEE. No GPU means use lower resolution drafts and expect long final renders.

## 1. Cost and license ledger (what you actually need)

| Need | Tool | Cost | License note |
|---|---|---|---|
| IDE | VSCode | Free | |
| 3D, rigging, animation, render | Blender 5.1 (or 4.5 LTS) | Free | GPL software; **your renders are yours** |
| Scripting | Python 3.11+ | Free | |
| Blender autocomplete | `fake-bpy-module` | Free | |
| Voices | Kokoro-82M TTS | Free | Apache-2.0 |
| Alternate TTS | Piper | Free | Code is open; **check each voice's license** and which Piper repo/version you use |
| Lip-sync | Rhubarb Lip Sync | Free | MIT |
| Video encode / mix | FFmpeg | Free | |
| Concept art | Local image models (optional) | Free | Read the model's license; FLUX.1 [schnell] is Apache-2.0 per its card, SDXL variants differ |
| Animation library | Mixamo (optional) | Free | Free for commercial use per Adobe's FAQ; you may not redistribute the raw files or use them to train ML models |
| Reference rigs | Blender Studio characters (Rain, Snow, Sprite...) | Free | CC-BY: **credit required** |
| Textures/HDRIs/models | Poly Haven | Free | CC0 |
| Music | YouTube Audio Library / Pixabay / Incompetech | Free | Incompetech needs attribution; see prompts file |
| Sound effects | Freesound (CC0 filter), Kenney | Free | |
| Editing (optional) | DaVinci Resolve free, or Blender VSE | Free | |
| Hosting | YouTube | Free | |

Keep every third-party asset listed in `assets/LICENSES.csv` the day you download it.

## 2. Phase 0: Create the project in VSCode (about 30 minutes)

1. **Install** (all free): VSCode, Python 3.11 or newer, Git, FFmpeg, Blender.
   - Windows: `winget install Microsoft.VisualStudioCode Python.Python.3.13 Git.Git Gyan.FFmpeg BlenderFoundation.Blender`
   - macOS (Homebrew): `brew install --cask visual-studio-code blender` and `brew install python ffmpeg git`
   - Linux: use your package manager for python3, git, ffmpeg; download Blender from blender.org or Flatpak.
2. **Download Rhubarb Lip Sync** from its GitHub releases (DanielSWolf/rhubarb-lip-sync), unzip it somewhere permanent, and note the path to the `rhubarb` executable.
3. **Create the folder and open it in VSCode.**
   ```bash
   mkdir kidsGoodHabitsCenter && cd kidsGoodHabitsCenter
   code .
   ```
   If you received the scaffold zip/folder from me, open that folder instead and skip to step 5.
4. **Create the structure** (skip if you have the scaffold):
   ```bash
   mkdir -p docs prompts config scripts blender episodes assets/{characters,sets,props,music,sfx} scenes audio frames out
   git init
   ```
5. **Python environment** (VSCode terminal):
   ```bash
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   pip install fake-bpy-module        # autocomplete for Blender's bpy in VSCode
   ```
   Then press `Ctrl+Shift+P` -> "Python: Select Interpreter" -> choose `.venv`.
6. **VSCode extensions** (Extensions panel): *Python*, *Pylance*, *Ruff*, **Blender Development** (by Jacques Lucke; starts Blender from VSCode and runs your scripts in it), *GitLens* (optional), *Markdown All in One* (optional).
7. **Point config at your tools:** edit `config/project.toml` `[tools]` with the full path to Blender and Rhubarb if they are not on PATH (on Windows, e.g. `"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"`).
8. **Check everything:** `python scripts/00_check_env.py`. All lines should say OK.
9. **First commit:** `git add . && git commit -m "Initial project scaffold"`.

> Tip: Blender 5.x ships its own Python (3.13). Scripts in `blender/` run inside Blender via `blender -b file.blend --python script.py`. Scripts in `scripts/` run in your normal venv.

## 3. Phase 1: Concept, audience and brand (1-2 days)

1. **Decide the promise:** "Short, joyful 3-minute stories that help children build one good habit at a time."
2. **Target ages:** 3-8. Write so a 3-year-old can follow every line, and give older viewers a little more: one simple "why" behind the habit (e.g. brushing cleans away the germs and bits of food that can hurt our teeth). Keep every fact true, even when simple. Everything (words, pace, visuals) follows from this.
3. **Pick the first 10 habits** (one episode each): brushing teeth, washing hands, bedtime, eating vegetables, tidying toys, saying please and thank you, sharing, drinking water, road/home safety basics, getting dressed.
4. **Write the style bible:** `prompts/01_style_bible.md` already defines look, color script, camera rules and inclusivity rules. Customize it and treat it as law.
5. **Name and brand:** channel name, 15-second theme tune, a logo (make it in Blender or Inkscape, original only).

**Making the content work for every culture, religion and region**
- No text in the story world, no flags, holidays, religious symbols or brand names.
- Diverse cast with neutral everyday clothing; "grown-up" characters readable as parent, grandparent or carer.
- Show habits through universal actions (hands under water, tooth brushing, bed, books).
- Publish subtitles and, over time, dubbed versions (Kokoro supports 8 languages; always have a native speaker review translations).

## 4. Phase 2: Write the episode (half a day)

1. Use the **structure table** and the **script prompt** in `prompts/04_story_dialogue_music.md`.
2. Run the prompt in any writing assistant, then edit by reading it aloud. Rules: max 12 words per line, positive tone, 3 steps repeated 3 times, 2 viewer-participation pauses.
3. Convert the shot table to `episodes/epXX/episode.json` (the second prompt in that file does this). See `episodes/ep01_brush_teeth/episode.json` for a working example.
4. **Storyboard:** one quick sketch per shot (paper or Krita/Inkscape). Time them to the script so you know the length before you build anything. Fixing pacing now costs minutes; fixing it after rendering costs days.

## 5. Phase 3: Characters (about 1 week for the cast, first time)

1. **Concept art** with the prompts in `prompts/02_characters.md` (use a local image generator, or draw it). Generate a turnaround sheet and an expression sheet; pick one and lock it.
2. **Model in Blender** (box modeling plus sculpt):
   - Start from primitives, block out the head, body, hands, feet.
   - Use the concept sheet as a background reference image.
   - Keep topology clean around eyes, mouth and joints (edge loops that follow muscle flow).
   - Add a **mouth shape set** (9 shape keys named `mouth_A` ... `mouth_H`, `mouth_X`) and eyelid/brow shape keys.
3. **Materials:** Principled BSDF with a little subsurface scattering on skin, hand-painted fabric textures, simple eye shader. Soft rounded surfaces and warm colors do most of the "animated film" look.
4. **Hair:** for a simple pipeline use modeled hair cards or sculpted hair shapes; hair particles are much slower to render.
5. **Rigging:** the fastest solid route is Blender's **Rigify** (Add -> Armature -> Human (Meta-Rig), generate rig) or study the CC-BY Blender Studio rigs (Rain, Snow, Sprite) and build to a similar standard.
6. **Test your pipeline cheaply first:** run `blender -b --python blender/make_placeholder_character.py -- --save scenes/test_pip.blend` to get a blockout character with a working 9-shape mouth. Use it to prove lip-sync, lighting and rendering before spending weeks on final characters.

**Shortcut for animation:** Mixamo (free Adobe login) auto-rigs humanoids and offers walk, wave, jump and idle animations. Export FBX, import to Blender, retarget, then add hand-keyed polish (anticipation, overlap). Good for getting moving fast; hand-keyed signature moves give the show its personality.

## 6. Phase 4: Sets and props (about 1 week for the first sets)

1. Follow `prompts/03_backgrounds.md` to generate concept art for the 8 core sets.
2. Build **modular kits** (walls, windows, doors, tables, beds, rugs) so every room reuses the same parts.
3. Texture with painted colors and CC0 materials from Poly Haven. Keep a consistent color script per episode.
4. Create **3 saved cameras per set** (Wide, Medium, Close).
5. Light with `blender/lighting_rig.py` (day, morning, evening, night moods), then tweak by eye.

Run the rig on a scene:
```bash
blender -b scenes/bedroom.blend --python blender/lighting_rig.py -- --mood morning --save
```
Leave off `--save` if you only want to preview the lights from the Blender UI.

## 7. Phase 5: Voices and lip-sync (1 day per episode)

1. Generate dialogue audio, one file per line:
   ```bash
   python scripts/01_make_voice.py episodes/ep01_brush_teeth/episode.json
   ```
   Output goes to `audio/<episode id>/<line id>.wav`. Voice casting and pitch tricks are in `prompts/04_story_dialogue_music.md`.
2. Generate mouth cues with Rhubarb:
   ```bash
   python scripts/02_lipsync.py episodes/ep01_brush_teeth/episode.json
   ```
3. Apply cues to a character's mouth shape keys inside the shot file:
   ```bash
   blender -b scenes/ep01_shot02.blend --python blender/apply_lipsync.py -- \
       --object Mouth --cues audio/ep01_brush_teeth/ep01_l02.json --fps 24 --start-frame 1 --save
   ```
4. Offset the start frame if the line begins a second into the shot (`--start-frame 25` for a 1 second delay at 24 fps).
5. Rhubarb is tuned for English. For other languages keep the mouth shapes simpler and avoid tight closeups.

Alternative TTS: Piper (offline, many voices and languages). Always verify the license of each voice before shipping a video.

## 8. Phase 6: Animation (the longest step)

Work in passes, never polishing before the timing works:
1. **Blocking:** key the main poses only, stepped interpolation. Check against the animatic.
2. **Splining:** switch to Bezier curves, clean the Graph Editor arcs.
3. **Polish:** the 12 principles; anticipation, squash and stretch on soft shapes, overlapping action on ears/hair/clothes, follow-through, eye blinks every 3-5 seconds, small head tilts.
4. **Acting for kids:** big readable poses, held for 0.5-1 second, one clear action per beat.
5. **Camera:** slow pushes and gentle pans only; add a hint of depth of field in close-ups.
6. **Rules of thumb for time:** a 3-minute episode with 25-35 shots and mostly simple actions is a few days of animation once rigs are ready. Use looping idle/walk cycles and reuse them across shots.

## 9. Phase 7: Render (hours to days, mostly unattended)

1. Draft first (50 percent resolution, low samples):
   ```bash
   python scripts/03_render_all.py episodes/ep01_brush_teeth/episode.json --draft
   ```
   Watch the draft, fix problems, then final:
   ```bash
   python scripts/03_render_all.py episodes/ep01_brush_teeth/episode.json
   ```
2. EEVEE is the default (fast, great for stylized work). Use Cycles only for a few hero shots or if you have a strong GPU.
3. Always PNG sequences; the render step is **resumable** (it skips frames that already exist).
4. If your computer is too slow: lower the sample count, simplify lights and hair, render at 720p and upscale, render overnight, or use a free/credit-based cloud notebook GPU **where its terms allow rendering jobs** (check the terms first).

## 10. Phase 8: Music, sound and final edit (half a day)

1. Pick or compose a theme (see the music brief and sources in `prompts/04_story_dialogue_music.md`). Put it in `assets/music/` and set the path in `episode.json`.
2. Add sound effects (soft pops, water, brush) as extra dialogue-type entries or edit them in DaVinci Resolve / Blender VSE.
3. Assemble:
   ```bash
   python scripts/04_assemble.py episodes/ep01_brush_teeth/episode.json
   ```
   Output: `out/ep01_brush_teeth.mp4` (1080p, H.264, AAC, normalised loudness). The step has been tested with synthetic input.
4. **Watch it fully**, on a phone speaker and with headphones. Check: no clipping, voices clear over music, no flashing, every line fits the visuals.
5. **Captions:** write an `.srt` from the dialogue (timecodes from the shot starts plus each line's `at` value).

## 11. Phase 9: Publish on YouTube (1 hour)

Follow `docs/YOUTUBE_CHECKLIST.md`. Key points:
- Set the channel/videos to **Made for kids** (comments, notifications, cards/end screens and personalised ads are turned off; contextual ads can still run).
- Collect no personal data from children.
- Realistic synthetic people/voices need the altered-content label; stylized cartoons with a clearly synthetic voice do not, but answer the Studio question honestly.
- Credits for CC-BY assets go in the description.
- Upload manually in YouTube Studio. The API script exists, but uploads from an API project that has not passed Google's audit are locked to private.

## 12. Phase 10: Repeat and improve

- Episode 1 is slow because you are building assets. Every episode after reuses characters, sets, rigs, music and the pipeline.
- Keep a **retro file** per episode: what took longest, what to automate next.
- After 5 episodes, consider a bundle ("Pip's Morning Routine") for longer watch sessions, and short 30-60 second "habit recap" clips as extra uploads.

## 13. Suggested 30-day plan

| Week | Goal | Deliverable |
|---|---|---|
| 1 | Setup and learning | Environment OK, Blender fundamentals, placeholder character lip-syncing, one test render |
| 2 | Assets | Pip modeled and rigged, bathroom and bedroom sets, lighting presets |
| 3 | Episode 1 | Script, voices, lip-sync, animation of 25 shots |
| 4 | Finish and ship | Render, music, edit, captions, upload, retro |

## 14. Learning resources (free)
- Blender Manual and Blender Studio (training, production files, rigs); Blender Python API documentation (docs.blender.org/api).
- Rigify docs, Rhubarb Lip Sync README, Kokoro model card on Hugging Face.
- Blender-Developer-Tools repository on GitHub: runnable examples for Blender 5.1 and 4.5 (check its license before copying code).
- Poly Haven (CC0 assets), Kenney (CC0 assets), Freesound (filter by CC0).
- YouTube: official Blender channel tutorials, "Animation Fundamentals" and "Character Workflow" series from Blender Studio.

## 15. Known risks and how to handle them

| Risk | Mitigation |
|---|---|
| Blender API changed between versions (EEVEE engine id differs on 4.2-4.5 vs 5.x) | `render_shot.py` auto-detects the id; pin one Blender version per project |
| Characters look inconsistent | Lock turnaround and expression sheets before modeling; reuse the same rig |
| Renders too slow | Draft passes, fewer samples, simpler hair/lights, overnight renders |
| Copyright claims on music | Use only YouTube Audio Library / CC0 / attributed CC-BY tracks and log them |
| Policy changes (kids' content, AI disclosure) | Re-read YouTube's current rules before each season |
| Voice sounds robotic | Write shorter lines, add pauses, tweak speed, record your own for key lines |
| Scope creep | One habit, three steps, three minutes |

## 16. What the scaffold does and does not include
- Tested: FFmpeg assembly (frames + dialogue + looped music, loudness normalisation).
- Syntax-checked only: all Python scripts. The Blender scripts (`render_shot.py`, `lighting_rig.py`, `apply_lipsync.py`, `make_placeholder_character.py`) have not been run inside Blender; expect small fixes on first run and adjust for your Blender version.
- Not included: finished character models, sets or music. Those are your creative work, guided by the prompt files.
