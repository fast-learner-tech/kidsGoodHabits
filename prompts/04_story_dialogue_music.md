# Story, Dialogue, Voice and Music Prompts

## A. Episode structure (2.5 to 4 minutes, ages 3-6)
| Time | Beat | Purpose |
|---|---|---|
| 0:00 | Cold open | Pip wakes up / starts the day, a tiny problem appears |
| 0:20 | Hook song or sound motif | 10-15 second tune that returns every time |
| 0:35 | Try it wrong, gently | Pip or Tomo gets it a bit wrong (funny, never shameful) |
| 1:10 | Friend shows how | Zuri or Nana Rue demonstrates in 3 clear steps |
| 1:40 | Do it together | Viewer participation: "Can you do it too?" with pauses |
| 2:20 | Payoff | Good feeling: sparkly smile, cozy sleep, tidy room |
| 2:40 | Recap song | Three-step chorus, original lyrics, slower tempo |

## B. Prompt to write a script (use with any writing assistant)
```
You are a children's TV writer. Write a 3-minute animated episode script for ages 3-6 called "[TITLE]".
Habit taught: [HABIT]. Characters: Pip (6), Zuri (6), Tomo (3), Nana Rue (grown-up), Biscuit (pet, no dialogue).
Rules:
- Positive tone only: no shaming, yelling, scary moments or punishment.
- Culture-neutral: no holidays, religion, flags, brand names, or region-specific foods or customs.
- The habit is taught in exactly 3 simple steps, each repeated 3 times.
- Include 2 moments where a character speaks to the viewer and pauses for 3 seconds.
- Include a 4-line original rhyming chorus that recaps the 3 steps.
- Max 12 words per spoken line. Use concrete, simple words.
- Output as a table: shot number, location, camera (wide/medium/close), action, dialogue (speaker: line), duration in seconds.
Total runtime: 170 seconds.
```

## C. Prompt to convert the script into `episode.json`
```
Convert this shot table into JSON matching this schema:
{ "id": "...", "title": "...", "music": {"file": "...", "volume_db": -16},
  "shots": [ { "n": 1, "description": "...", "blend": "scenes/<id>_shot01.blend", "frames": [1, N],
               "dialogue": [ {"id": "<id>_l01", "voice": "narrator|child|parent", "at": 0.5, "text": "..."} ] } ] }
Rules: frames = duration_seconds * 24. Dialogue ids unique. "at" is seconds from the start of the shot.
```

## D. Original chorus example (brushing teeth; safe to use, written for this project)
```
Up and down, up and down, make the sparkles come out,
Round and round, round and round, wiggle that brush about,
Front and back, front and back, don't forget the sides,
Two whole minutes, every day, and shiny smiles abide!
```

## E. Voice casting (Kokoro voices, offline and Apache-2.0)
| Character | Suggested Kokoro voice | Settings |
|---|---|---|
| Narrator | `af_heart` | speed 0.95, warm, slow |
| Pip | `af_nicole` | speed 1.0, nudge pitch up in Audacity/FFmpeg by about +2 semitones |
| Zuri | `af_bella` | speed 1.0 |
| Tomo | `af_nicole` pitched +5 semitones | speed 0.9, short phrases |
| Nana Rue | `bf_emma` (British) | speed 0.9 |
| Grown-up (male) | `am_michael` | speed 0.95 |

See VOICES.md on the Kokoro model page (huggingface.co/hexgrad/Kokoro-82M) for the current voice list; ids can change between releases, so confirm the names above exist. Listen to a test line for every voice before locking the cast.
Generate each line separately, normalise levels, and keep pauses between lines (0.3 s) for clarity.

### Pitch shift with FFmpeg (for child-like voices)
```bash
ffmpeg -i in.wav -af "asetrate=24000*1.122,aresample=24000,atempo=0.891" out.wav   # ~ +2 semitones, same speed
```

## F. Other languages (reach more families)
Kokoro covers English, Spanish, French, Italian, Portuguese, Hindi, Japanese and Mandarin. To release a second language, translate the dialogue strings, regenerate audio with the matching `lang_code` and voices, and re-assemble. Lip-sync (Rhubarb) is tuned for English, so for other languages keep faces simple (mouth shapes on beats rather than exact phonemes) or hide closeups.
Have a native speaker review each translation before publishing.

## G. Music brief (for free libraries or for composing yourself)
```
Instrumental, 90-110 BPM, major key, gentle ukulele + glockenspiel + soft marimba + light hand percussion,
playful and warm, no vocals, loopable 60-90 seconds, no sudden dynamics, family-friendly.
```
Where to get music safely:
1. **YouTube Studio Audio Library**: free, safe for monetized videos on YouTube.
2. **Pixabay Music**: Pixabay Content License, no attribution required (read the current terms).
3. **Incompetech (Kevin MacLeod)**: CC-BY, attribution line required in the description.
4. **Compose your own** with LMMS or MuseScore (free) for the signature theme; that gives you something no one else has and a clean copyright position.
Log every track in `assets/LICENSES.csv` and paste required credits into the video description.

## H. Sound effects
Freesound (filter for CC0), Kenney audio (CC0), and your own Foley (record with a phone: water, brush, pop, door). Keep sounds soft and short.
