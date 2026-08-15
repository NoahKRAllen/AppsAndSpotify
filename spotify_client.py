"""
Spotify integration wrapper using spotipy.

Setup:
1. Go to https://developer.spotify.com/dashboard and create an app.
2. In the app's settings, add this Redirect URI: http://127.0.0.1:8888/callback
3. Copy the Client ID and Client Secret into data/config.json.
4. The first time you open the Spotify tab, a browser window will pop up
   asking you to log in and authorize the app. After that, a token is
   cached in data/.spotify_cache and you won't need to log in again.
"""

from __future__ import annotations

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, CACHE_PATH

SCOPES = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "playlist-read-private "
    "playlist-read-collaborative"
)


class SpotifyClient:
    """Lazily authenticates on first use so the app can still open if
    credentials aren't filled in yet."""

    def __init__(self):
        self._sp: spotipy.Spotify | None = None

    @property
    def sp(self) -> spotipy.Spotify:
        if self._sp is None:
            if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
                raise RuntimeError(
                    "Spotify credentials missing. Fill in spotify_client_id and "
                    "spotify_client_secret in data/config.json (see README.md)."
                )
            auth_manager = SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope=SCOPES,
                cache_path=str(CACHE_PATH),
                open_browser=True,
            )
            self._sp = spotipy.Spotify(auth_manager=auth_manager)
        return self._sp

    def get_now_playing(self) -> dict | None:
        playback = self.sp.current_playback()
        if not playback or not playback.get("item"):
            return None
        item = playback["item"]
        images = item.get("album", {}).get("images") or [{}]
        return {
            "track": item.get("name"),
            "artist": ", ".join(a["name"] for a in item.get("artists", [])),
            "album": item.get("album", {}).get("name"),
            "album_art_url": images[0].get("url"),
            "is_playing": playback.get("is_playing", False),
            "progress_ms": playback.get("progress_ms", 0),
            "duration_ms": item.get("duration_ms", 0),
        }

    def get_playlists(self) -> list[dict]:
        results = self.sp.current_user_playlists(limit=50)
        playlists = []
        for pl in results.get("items", []):
            # Spotify renamed the playlist "tracks" field to "items" in their
            # Feb 2026 Dev Mode API changes. Check both so this keeps working
            # whichever the account/app combo returns.
            track_info = pl.get("items") or pl.get("tracks")
            track_count = track_info.get("total") if isinstance(track_info, dict) else None
            playlists.append({
                "id": pl["id"],
                "name": pl["name"],
                "uri": pl["uri"],
                "track_count": track_count,  # None means Spotify didn't report it
            })
        return playlists

    def get_devices(self) -> list[dict]:
        return self.sp.devices().get("devices", [])

    def _resolve_device_id(self) -> str:
        """Picks a device to target for playback commands. Prefers whichever
        device Spotify already reports as active; otherwise falls back to the
        first available one. The Web API can't launch Spotify for you, so if
        nothing is open anywhere, this raises a clear, actionable error
        instead of the raw 404."""
        devices = self.get_devices()
        if not devices:
            raise RuntimeError(
                "No Spotify device found. Open Spotify (desktop, mobile, or "
                "web player) on any device, then try again."
            )
        for d in devices:
            if d.get("is_active"):
                return d["id"]
        return devices[0]["id"]

    def play_playlist(self, playlist_uri: str) -> None:
        device_id = self._resolve_device_id()
        self.sp.start_playback(context_uri=playlist_uri, device_id=device_id)

    def toggle_playback(self, is_playing: bool) -> None:
        device_id = self._resolve_device_id()
        if is_playing:
            self.sp.pause_playback(device_id=device_id)
        else:
            self.sp.start_playback(device_id=device_id)

    def next_track(self) -> None:
        device_id = self._resolve_device_id()
        self.sp.next_track(device_id=device_id)

    def previous_track(self) -> None:
        device_id = self._resolve_device_id()
        self.sp.previous_track(device_id=device_id)