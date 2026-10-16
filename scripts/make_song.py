#!/usr/bin/env python3
"""Synthesize the "habit song" backing track and the lullaby version of the theme (original, no samples).

Usage:  python scripts/make_song.py
Output: assets/music/habit_song.wav   1 intro bar + four 2-bar phrases (one per sung line) + 1 tag bar, 96 BPM
        assets/music/lullaby.wav      slow music-box version of the theme's opening, for night endings

The habit song is the same tune in every episode's recap so children learn it. Its melody uses six notes,
C to A (sung at C4-A4); the glockenspiel plays it an octave higher for brightness. At 96 BPM one bar is
exactly 2.5 s = 60 frames at 24 fps, so picture cuts can land on bar lines.
"""
from pathlib import Path

import numpy as np
import soundfile as sf

import make_theme as t  # instruments, note helpers and mixing from the theme

ROOT = Path(__file__).resolve().parent.parent

SONG_BPM = 96
# one chord per bar; the melody is (note, beats) and each phrase adds up to 8 beats (2 bars)
SONG_CHORDS = ["C"] + ["C", "Am", "F", "G", "C", "Am", "F", "C"] + ["C"]
SONG_PHRASES = [
    [("C5", 1), ("E5", 1), ("G5", 1), ("G5", 1), ("A5", 1), ("G5", 1), ("E5", 2)],   # A tiny dot of toothpaste...
    [("F5", 1), ("F5", 1), ("A5", 1), ("A5", 1), ("G5", 1), ("E5", 1), ("D5", 2)],   # Little circles, fronts and backs...
    [("E5", 1), ("E5", 1), ("G5", 1), ("G5", 1), ("A5", 1), ("G5", 1), ("E5", 2)],   # Brush for two whole minutes...
    [("F5", 1), ("A5", 1), ("G5", 1), ("E5", 1), ("D5", 1), ("E5", 1), ("C5", 2)],   # Ptoo! Morning and at bedtime...
]


def render(bpm, chords, melody, start_beat, strum=True, bass=True, shake=True, glock_gain=0.24, tail=1.5):
    beat = 60 / bpm
    total = len(chords) * 4 * beat + tail
    mix = np.zeros(int(t.SR * total))

    def add(sig, at, gain):
        i = int(at * t.SR)
        end = min(len(mix), i + len(sig))
        mix[i:end] += gain * sig[: end - i]

    for b, chord in enumerate(chords):
        t0 = b * 4 * beat
        if strum:
            for k in range(4):
                for j, s in enumerate(t.CHORDS[chord]):
                    add(t.pluck(t.hz(t.note(s)), beat), t0 + k * beat + j * 0.015, 0.09 if k else 0.12)
        if bass:
            for k in (0, 2):
                add(t.marimba(t.hz(t.note(t.ROOTS[chord])), beat), t0 + k * beat, 0.32)
        if shake:
            for e in range(8):
                add(t.shaker(0.12), t0 + e * beat / 2, 0.045 if e % 2 else 0.025)
    at = start_beat * beat
    for name, beats in melody:
        if name:
            add(t.glock(t.hz(t.note(name)), beats * beat), at, glock_gain)
        at += beats * beat
    fade = int(t.SR * tail)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix /= np.max(np.abs(mix)) / 10 ** (-3 / 20)
    return mix


def save(mix, name):
    out = ROOT / "assets" / "music" / name
    sf.write(out, np.column_stack([mix, mix]), t.SR)
    print(f"wrote {out.relative_to(ROOT)} ({len(mix) / t.SR:.1f}s)")


def main():
    melody = [n for phrase in SONG_PHRASES for n in phrase]
    assert all(sum(b for _, b in p) == 8 for p in SONG_PHRASES), "each phrase must be 2 bars"
    save(render(SONG_BPM, SONG_CHORDS, melody, start_beat=4), "habit_song.wav")
    # lullaby: first four bars of the theme, slow, music box only with a soft bass
    lull_melody = t.MEL_A[:15]
    save(render(66, t.PROG_A[:4], lull_melody, start_beat=0, strum=False, shake=False, glock_gain=0.3, tail=3.0),
         "lullaby.wav")


if __name__ == "__main__":
    main()
