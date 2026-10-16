#!/usr/bin/env python3
"""Make the placeholder sound effects (original: synthesized, or spoken by the show's Kokoro voices).

Usage:  python scripts/make_sfx.py
Output: assets/sfx/*.wav (44.1 kHz mono). Swap any of them for CC0 recordings later and log those in
assets/LICENSES.csv. Everything stays soft and short: no sudden loud sounds for young viewers.
"""
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import make_theme as t  # noqa: E402  (glockenspiel/pluck instruments for the sting, chime and sparkle)

CFG = tomllib.loads((ROOT / "config" / "project.toml").read_text())
FFMPEG = CFG["tools"]["ffmpeg"]
SR = 44100
OUT = ROOT / "assets" / "sfx"
rng = np.random.default_rng(11)


def env(n, attack, decay):
    x = np.arange(n) / SR
    return np.minimum(x / max(attack, 1e-4), 1.0) * np.exp(-x / decay)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def noise(seconds):
    return rng.uniform(-1, 1, int(SR * seconds))


def save(name, x, peak_db=-6):
    x = x / (np.max(np.abs(x)) + 1e-9) * 10 ** (peak_db / 20)
    sf.write(OUT / f"{name}.wav", x.astype(np.float32), SR)
    print(f"wrote assets/sfx/{name}.wav ({len(x) / SR:.2f}s)")


# ---------------------------------------------------------------- synthesized

def chime():
    x = np.zeros(int(SR * 2.2))
    for i, n in enumerate(("E6", "G6", "C7")):
        s = t.glock(t.hz(t.note(n)), 0.8)
        o = int(i * 0.12 * SR)
        x[o:o + len(s)] += s[: len(x) - o] * 0.5
    return x


def sparkle():
    x = np.zeros(int(SR * 1.2))
    for i, n in enumerate(("C7", "E7", "G7", "C8")):
        s = t.glock(t.hz(t.note(n)), 0.3) * 0.35
        o = int(i * 0.07 * SR)
        x[o:o + len(s)] += s[: len(x) - o]
    return x


def sting():
    """Short bright theme sting: ukulele strum + glockenspiel flourish."""
    x = np.zeros(int(SR * 2.4))
    for j, s_ in enumerate(t.CHORDS["C"]):
        p = t.pluck(t.hz(t.note(s_)), 0.6) * 0.5
        o = int(j * 0.02 * SR)
        x[o:o + len(p)] += p[: len(x) - o]
    for i, n in enumerate(("C5", "E5", "G5", "C6")):
        g = t.glock(t.hz(t.note(n)), 0.4) * 0.6
        o = int((0.05 + i * 0.09) * SR)
        x[o:o + len(g)] += g[: len(x) - o]
    return x


def pop():
    n = int(SR * 0.12)
    f = np.linspace(1400, 500, n)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.025)


def squish():
    n = int(SR * 0.45)
    wob = 1 + 0.5 * np.sin(2 * np.pi * 18 * np.arange(n) / SR)
    return lowpass(noise(0.45), 900) * env(n, 0.03, 0.18) * wob


def flop():
    n = int(SR * 0.35)
    thud = np.sin(2 * np.pi * np.cumsum(np.linspace(180, 70, n)) / SR) * env(n, 0.002, 0.08)
    return thud + 0.4 * lowpass(noise(0.35), 600) * env(n, 0.002, 0.05)


def brush_fast(seconds=2.2, rate=9.0):
    n = int(SR * seconds)
    hiss = noise(seconds) - lowpass(noise(seconds), 2500)  # crude high-pass: bristly
    stroke = 0.5 + 0.5 * np.abs(np.sin(np.pi * rate * np.arange(n) / SR))
    return hiss * stroke * env(n, 0.05, seconds)


def crunch():
    x = np.zeros(int(SR * 0.3))
    for k in range(5):
        o = int(k * 0.045 * SR)
        b = noise(0.03) * env(int(SR * 0.03), 0.001, 0.008)
        x[o:o + len(b)] += b
    return lowpass(x, 3500)


def spit():
    n = int(SR * 0.35)
    burst = (noise(0.35) - lowpass(noise(0.35), 1800)) * env(n, 0.005, 0.07)
    splash = lowpass(noise(0.35), 1200) * env(n, 0.08, 0.1) * 0.5
    return burst + splash


def purr(seconds=1.8):
    n = int(SR * seconds)
    rumble = lowpass(noise(seconds), 300)
    am = 0.55 + 0.45 * np.sin(2 * np.pi * 26 * np.arange(n) / SR)  # ~26 Hz flutter
    breath = 0.6 + 0.4 * np.sin(2 * np.pi * 0.9 * np.arange(n) / SR)
    return rumble * am * breath * env(n, 0.15, seconds)


def snore(seconds=2.4):
    n = int(SR * seconds)
    x = np.arange(n) / SR
    breath = np.clip(np.sin(2 * np.pi * x / seconds), 0, None)  # one gentle in-breath
    rasp = lowpass(noise(seconds), 400) * (0.6 + 0.4 * np.sin(2 * np.pi * 32 * x))
    return rasp * breath


def lip_smack():
    n = int(SR * 0.12)
    return (noise(0.12) - lowpass(noise(0.12), 2000)) * env(n, 0.001, 0.015)


# ---------------------------------------------------------------- spoken by the cast's voices (Kokoro)

def voiced():
    from kokoro import KPipeline

    cast = CFG["audio"]["cast"]
    pipes = {}
    lines = {  # name: (cast member or raw voice, text, extra semitones, speed)
        "giggle_pip": ("pip", "Hee hee hee!", 0, 1.1),
        "giggle_tomo": ("tomo", "Hee hee!", 0, 1.1),
        "laugh_nana": ("nana_rue", "Ha ha ha!", 0, 1.0),
        "yawn_pip": ("pip", "Aaaaahhh.", 0, 0.8),
        "mew": ("af_sky", "Mew?", 9, 1.0),
        "sneeze_biscuit": ("af_sky", "Chu!", 10, 1.2),
    }
    for name, (who, text, semis, speed) in lines.items():
        voice = cast[who]["voice"] if who in cast else who
        semis += cast[who]["semitones"] if who in cast else 0
        lang = voice[0]
        if lang not in pipes:
            pipes[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
        audio = np.concatenate([np.asarray(a) for _, _, a in pipes[lang](text, voice=voice, speed=speed)])
        tmp = OUT / f"{name}.24k.wav"
        sf.write(tmp, audio, 24000)
        ratio = 2 ** (semis / 12)
        af = f"asetrate=24000*{ratio:.5f},aresample={SR},atempo={1 / ratio:.5f}" if semis else f"aresample={SR}"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(tmp), "-af", af, str(OUT / f"{name}.wav")],
                       check=True)
        tmp.unlink()
        print(f"wrote assets/sfx/{name}.wav (voiced)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("chime", chime), ("sparkle", sparkle), ("sting", sting), ("bubble_pop", pop), ("squish", squish),
                     ("flop", flop), ("brush_fast", brush_fast), ("crunch", crunch), ("spit", spit), ("purr", purr),
                     ("snore", snore), ("lip_smack", lip_smack)):
        save(name, fn())
    voiced()


if __name__ == "__main__":
    main()
