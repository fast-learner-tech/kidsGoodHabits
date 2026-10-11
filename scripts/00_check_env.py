#!/usr/bin/env python3
"""Check that every tool the pipeline needs is installed. Run this first."""
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cfg = tomllib.loads((ROOT / "config" / "project.toml").read_text())
tools = cfg["tools"]


def check_cmd(label, cmd, version_args):
    path = shutil.which(cmd)
    if not path:
        print(f"[MISSING] {label}: '{cmd}' not found on PATH (edit config/project.toml or install it)")
        return False
    try:
        out = subprocess.run([path, *version_args], capture_output=True, text=True, timeout=30)
        first = (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception as exc:  # noqa: BLE001
        first = f"(could not read version: {exc})"
    print(f"[ OK ] {label}: {first}")
    return True


def check_py(label, module):
    try:
        __import__(module)
        print(f"[ OK ] {label}: python module '{module}' importable")
        return True
    except ImportError:
        print(f"[MISSING] {label}: run 'pip install -r requirements.txt'")
        return False


results = [
    check_cmd("Blender", tools["blender"], ["--version"]),
    check_cmd("FFmpeg", tools["ffmpeg"], ["-version"]),
    check_cmd("Rhubarb Lip Sync", tools["rhubarb"], ["--version"]),
    check_py("Kokoro TTS", "kokoro"),
    check_py("soundfile", "soundfile"),
]
if sys.version_info < (3, 11):
    print("[WARN] Python 3.11+ recommended (tomllib is used for config)")
print()
print("All required tools found." if all(results) else "Some tools are missing. See docs/GUIDE.md, Phase 0.")
