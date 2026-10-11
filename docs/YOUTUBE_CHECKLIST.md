# YouTube Publishing Checklist (kids' content)

Before the first upload
- [ ] Create a dedicated Google account and YouTube channel for the project.
- [ ] Verify the channel (phone) so you can upload videos over 15 minutes and custom thumbnails.
- [ ] Studio -> Settings -> Channel -> Advanced settings -> Audience: set **Made for kids**. (Children's content must be labelled; mislabelling is a serious compliance problem.)
- [ ] Understand the trade-off: Made for Kids turns off comments, notifications bell, end screens/cards and personalised ads; contextual ads still run.
- [ ] Do not collect any personal data from children (no contests asking for names/photos, no kid-directed email sign-ups). Direct community features at parents only, off-platform.
- [ ] Read YouTube's current kids' content and COPPA guidance in Studio help; rules change.

Per video
- [ ] 1920x1080, 24 fps, MP4 H.264, AAC audio (output of `04_assemble.py`).
- [ ] Loudness about -16 LUFS (done in assembly), no clipping.
- [ ] No flashing or strobing, no scary scenes.
- [ ] Title: short, benefit-led ("Brush Your Teeth With Pip!"). No clickbait.
- [ ] Description: what the habit is, ages, a line for parents, credits (see below).
- [ ] Thumbnail 1280x720: one big friendly face, 2-3 colors, no text clutter.
- [ ] Audience set to Made for kids (per video if not set channel-wide).
- [ ] Altered/synthetic content disclosure: needed for *realistic* synthetic people or voices that could be mistaken for real. Clearly animated cartoons with a TTS voice do not need it, but answer the Studio question honestly.
- [ ] Captions: upload an .srt of the dialogue (accessibility and international reach).
- [ ] Playlist per habit and one for each language.

Credits block (paste in description, edit to match `assets/LICENSES.csv`)
```
Made with Blender (blender.org). Voices: Kokoro TTS (Apache-2.0). Lip-sync: Rhubarb Lip Sync (MIT).
Music: [Track] by [Artist] ([source], [license]).
```

Upload methods
- **Manual in YouTube Studio** (recommended): upload, set details, publish.
- **API script** `scripts/05_upload_youtube.py`: videos uploaded by an API project that has not passed Google's compliance audit are forced private. Fine for tests, otherwise upload manually.

Growth basics (low cost)
- Consistent upload day, 1 video per week to start.
- 3-5 video "series" per habit ("Pip's Morning", "Pip's Bedtime").
- Add a short 15-second theme at the start of every video (brand recognition).
- Parent-facing page or newsletter (off YouTube) with printable habit charts.
