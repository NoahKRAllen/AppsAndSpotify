"""
Scans Steam for installed games and merges results into a user-curatable
JSON file at data/apps_config.json. Anything that isn't a Steam game
(dev tools, other regularly-used exes) is added manually via
add_manual_entry() and shows up in the same list.

Design notes:
- Steam games are launched via the `steam://rungameid/<appid>` URI rather
  than a raw exe path — this is what Steam itself uses, and it correctly
  handles anti-cheat/DRM-wrapped games that a direct exe launch would break.
- Rescanning only ever touches entries the scanner itself owns
  (source == "steam"). Manually-added entries are never touched by a
  rescan — they're only added or removed explicitly.
- Entries the scanner used to find but can no longer find are marked
  missing=True instead of deleted, so e.g. temporarily unplugging a drive
  won't silently wipe part of your curated list.
"""

from __future__ import annotations

import json
import re
import winreg
from pathlib import Path

from config import APPS_CONFIG_PATH


def _read_steam_path() -> Path | None:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        path, _ = winreg.QueryValueEx(key, "SteamPath")
        return Path(path)
    except OSError:
        return None


def _parse_vdf_library_folders(vdf_path: Path) -> list[Path]:
    """Minimal VDF parsing — just enough to pull "path" values out of
    libraryfolders.vdf without pulling in a full VDF library dependency."""
    if not vdf_path.exists():
        return []
    text = vdf_path.read_text(encoding="utf-8", errors="ignore")
    raw_paths = re.findall(r'"path"\s*"([^"]+)"', text)
    return [Path(p.replace("\\\\", "\\")) for p in raw_paths]


def _parse_appmanifest(acf_path: Path) -> dict | None:
    text = acf_path.read_text(encoding="utf-8", errors="ignore")
    appid_match = re.search(r'"appid"\s*"(\d+)"', text)
    name_match = re.search(r'"name"\s*"([^"]+)"', text)
    if not appid_match or not name_match:
        return None
    return {"appid": appid_match.group(1), "name": name_match.group(1)}


def scan_steam_games() -> list[dict]:
    steam_path = _read_steam_path()
    if not steam_path:
        return []

    libraries = _parse_vdf_library_folders(steam_path / "steamapps" / "libraryfolders.vdf")
    libraries.append(steam_path)  # the default library isn't listed in the vdf itself

    games = []
    seen_appids = set()
    for lib in libraries:
        steamapps_dir = lib / "steamapps"
        if not steamapps_dir.exists():
            continue
        for acf_file in steamapps_dir.glob("appmanifest_*.acf"):
            info = _parse_appmanifest(acf_file)
            if not info or info["appid"] in seen_appids:
                continue
            seen_appids.add(info["appid"])
            games.append({
                "key": f"steam:{info['appid']}",
                "source": "steam",
                "name": info["name"],
                "launch_target": f"steam://rungameid/{info['appid']}",
            })
    return games


def load_apps_config() -> dict:
    if APPS_CONFIG_PATH.exists():
        with open(APPS_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_apps_config(cfg: dict) -> None:
    with open(APPS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def rescan_and_merge() -> dict:
    """Rescans Steam only. Manually-added entries are left completely alone."""
    existing = load_apps_config()
    discovered = scan_steam_games()
    discovered_keys = {e["key"] for e in discovered}

    for entry in discovered:
        key = entry["key"]
        if key in existing:
            existing[key]["launch_target"] = entry["launch_target"]
            existing[key]["missing"] = False
        else:
            existing[key] = {
                "source": "steam",
                "display_name": entry["name"],
                "launch_target": entry["launch_target"],
                "category": "games",
                "enabled": True,
                "missing": False,
            }

    # Only reconcile the "missing" flag for entries the scanner is actually
    # responsible for. Manual entries are never marked missing by a rescan.
    for key, entry in existing.items():
        if entry.get("source") == "steam" and key not in discovered_keys:
            entry["missing"] = True

    save_apps_config(existing)
    return existing


def add_manual_entry(display_name: str, launch_target: str, category: str = "uncategorized") -> str:
    """Adds a manually-specified exe to the curated list. Returns its key.
    If an entry for this exact path already exists, updates it in place
    instead of creating a duplicate."""
    cfg = load_apps_config()
    key = f"manual:{launch_target.lower()}"
    cfg[key] = {
        "source": "manual",
        "display_name": display_name,
        "launch_target": launch_target,
        "category": category,
        "enabled": True,
        "missing": False,
    }
    save_apps_config(cfg)
    return key


def remove_entry(key: str) -> None:
    """Removes an entry outright, regardless of source. Use this for both
    manual entries and Steam games you no longer want listed — if it's a
    Steam game, a later rescan will just re-add it if it's still installed."""
    cfg = load_apps_config()
    cfg.pop(key, None)
    save_apps_config(cfg)