#!/usr/bin/env python3
"""Synthesize the show's original theme loop (no samples, no third-party audio, so it is fully ours).

Usage:  python scripts/make_theme.py [assets/music/theme.mp3]

Follows the music brief in prompts/04_story_dialogue_music.md: 100 BPM, C major, plucked ukulele-style
chords, glockenspiel melody, soft marimba bass, light shaker; 32 bars (~77 s) that loop seamlessly.
"""
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = tomllib.loads((ROOT / "config" / "project.toml").read_text())["tools"]["ffmpeg"]
SR = 44100
BPM = 100
BEAT = 60 / BPM
rng = np.random.default_rng(7)  # fixed seed so the theme is identical every run


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


N = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def note(name):
    """'E5' -> MIDI number."""
    return 12 * (int(name[-1]) + 1) + N[name[:-1]]


CHORDS = {  # ukulele-style voicings (MIDI)
    "C": ["G4", "C5", "E5", "C6"], "G": ["G4", "B4", "D5", "G5"],
    "Am": ["A4", "C5", "E5", "A5"], "F": ["A4", "C5", "F5", "A5"],
    "Dm": ["A4", "D5", "F5", "A5"], "Em": ["G4", "B4", "E5", "G5"],
}
ROOTS = {"C": "C3", "G": "G2", "Am": "A2", "F": "F2", "Dm": "D3", "Em": "E3"}

# 8-bar sections, one chord per bar
PROG_A = ["C", "G", "Am", "F", "C", "G", "F", "C"]
PROG_B = ["F", "C", "Dm", "G", "Em", "Am", "F", "G"]

# melody as (note or None for rest, length in beats); each bar adds up to 4 beats
MEL_A = [
    ("E5", 1), ("G5", 1), ("E5", 1), ("C5", 1),
    ("D5", 1), ("G5", 1), ("B4", 1), ("D5", 1),
    ("C5", 0.5), ("E5", 0.5), ("A5", 1), ("G5", 1), ("E5", 1),
    ("F5", 2), ("E5", 1), ("D5", 1),
    ("E5", 1), ("G5", 1), ("C6", 1.5), ("B5", 0.5),
    ("D6", 1), ("B5", 1), ("G5", 2),
    ("A5", 1), ("F5", 1), ("D5", 1), ("E5", 0.5), ("F5", 0.5),
    ("E5", 2), ("C5", 1), (None, 1),
]
MEL_B = [
    ("A5", 1.5), ("G5", 0.5), ("F5", 1), ("A5", 1),
    ("G5", 1.5), ("E5", 0.5), ("C5", 2),
    ("D5", 1), ("F5", 1), ("A5", 1), ("F5", 1),
    ("G5", 1), ("B5", 1), ("D6", 2),
    ("E6", 1.5), ("D6", 0.5), ("B5", 1), ("G5", 1),
    ("C6", 1), ("A5", 1), ("E5", 2),
    ("F5", 1), ("A5", 1), ("C6", 1), ("A5", 1),
    ("G5", 1), ("D5", 1), ("B4", 1), ("D5", 1),
]


def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(t / attack, 1.0) * np.exp(-t / decay)


def glock(f, dur):
    n = int(SR * (dur + 1.2))
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.15)
    return tone * env(n, 0.002, 0.55)


def marimba(f, dur):
    n = int(SR * (dur + 0.6))
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t / 0.05)
    return tone * env(n, 0.003, 0.35)


def pluck(f, dur):
    """Karplus-Strong plucked string: soft, ukulele-like."""
    n = int(SR * (dur + 0.8))
    period = int(SR / f)
    buf = rng.uniform(-1, 1, period)
    out = np.empty(n)
    for i in range(n):
        out[i] = buf[i % period]
        buf[i % period] = 0.5 * (buf[i % period] + buf[(i + 1) % period]) * 0.996
    return out * env(n, 0.001, 0.9)


def shaker(dur):
    n = int(SR * dur)
    noise = rng.uniform(-1, 1, n)
    noise = np.diff(noise, prepend=0)  # crude high-pass: keeps it airy
    return noise * env(n, 0.004, 0.03)


def add(track, sig, start_s, gain):
    i = int(start_s * SR)
    end = min(len(track), i + len(sig))
    track[i:end] += gain * sig[: end - i]
    if i + len(sig) > len(track):  # wrap the tail to the start so the loop is seamless
        rest = sig[end - i:]
        track[: len(rest)] += gain * rest


def main(out_path: str) -> None:
    progression = PROG_A + PROG_B + PROG_A + PROG_B
    melody = MEL_A + MEL_B + MEL_A + MEL_B
    total = len(progression) * 4 * BEAT
    mix = np.zeros(int(SR * total))

    for bar, chord in enumerate(progression):
        t0 = bar * 4 * BEAT
        # ukulele: gentle down-strum on each beat (strings 15 ms apart), off-beat lift on beat 4
        for beat in range(4):
            for k, s in enumerate(CHORDS[chord]):
                add(mix, pluck(hz(note(s)), BEAT), t0 + beat * BEAT + k * 0.015, 0.10 if beat else 0.13)
        # marimba bass on beats 1 and 3
        for beat in (0, 2):
            add(mix, marimba(hz(note(ROOTS[chord])), BEAT), t0 + beat * BEAT, 0.35)
        # shaker on every eighth, accented on the off-beats
        for e in range(8):
            add(mix, shaker(0.12), t0 + e * BEAT / 2, 0.05 if e % 2 else 0.03)

    t = 0.0
    for name, beats in melody:
        if name:
            add(mix, glock(hz(note(name)), beats * BEAT), t, 0.22)
        t += beats * BEAT

    # small room: two soft echoes, wrapped around for a seamless loop
    wet = 0.18 * np.roll(mix, int(0.11 * SR)) + 0.10 * np.roll(mix, int(0.23 * SR))
    mix = mix + wet
    mix /= np.max(np.abs(mix)) / 10 ** (-3 / 20)  # peak at -3 dBFS; assembly sets the final loudness

    out = ROOT / out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".wav")
    sf.write(wav, np.column_stack([mix, mix]), SR)
    if out.suffix != ".wav":
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "192k", str(out)], check=True)
        wav.unlink()
    print(f"wrote {out.relative_to(ROOT)} ({total:.1f}s, {BPM} BPM, loops seamlessly)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "assets/music/theme.mp3")
