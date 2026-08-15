"""Central configuration and paths.

On first run this creates data/config.json with empty Spotify credential
fields. Fill those in before the Spotify tab will work — see README.md.
"""

import json
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CONFIG_PATH = DATA_DIR / "config.json"
APPS_CONFIG_PATH = DATA_DIR / "apps_config.json"
CACHE_PATH = DATA_DIR / ".spotify_cache"

_DEFAULT_CONFIG = {
    "spotify_client_id": "",
    "spotify_client_secret": "",
    "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
}


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULT_CONFIG, **data}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(_DEFAULT_CONFIG, f, indent=2)
    return dict(_DEFAULT_CONFIG)


_cfg = _load_config()

SPOTIFY_CLIENT_ID = _cfg["spotify_client_id"]
SPOTIFY_CLIENT_SECRET = _cfg["spotify_client_secret"]
SPOTIFY_REDIRECT_URI = _cfg["spotify_redirect_uri"]
