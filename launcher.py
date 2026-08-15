"""Launches a curated app_scanner entry."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def launch(entry: dict) -> None:
    target = entry["launch_target"]
    if entry["source"] == "steam":
        os.startfile(target)  # steam://rungameid/<appid> — hands off to Steam itself
    else:
        exe_path = Path(target)
        if not exe_path.exists():
            raise FileNotFoundError(f"{exe_path} no longer exists — try rescanning.")
        subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
