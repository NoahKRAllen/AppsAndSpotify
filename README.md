# Music + App Launcher Dashboard

A small desktop dashboard: one tab for controlling Spotify, one tab for
launching Steam games and other frequently-used apps.

## Project layout

```
music_app_launcher/
  main.py            entry point / GUI (PySide6)
  spotify_client.py  Spotify Web API wrapper (spotipy)
  app_scanner.py      finds Steam games + Start Menu shortcuts
  launcher.py         actually launches an app/game
  config.py           loads data/config.json
  data/
    config.json        your Spotify credentials (created on first run)
    apps_config.json    curated app/game list (created on first rescan)
    .spotify_cache      cached OAuth token (created after first login)
```

## Setup

1. **Install dependencies** (Windows, since Steam-path lookup and shortcut
   resolution use the Windows registry / COM):

   ```
   pip install -r requirements.txt
   ```

2. **Register a Spotify app** so this project can talk to your account:
   - Go to https://developer.spotify.com/dashboard and log in.
   - Click "Create app". Name/description can be anything.
   - In the app's **Settings**, add this exact Redirect URI:
     `http://127.0.0.1:8888/callback`
   - Save, then copy the **Client ID** and **Client Secret**.

3. **Run once to generate the config file**:

   ```
   python main.py
   ```

   This creates `data/config.json`. Close the app, open that file, and fill in:

   ```json
   {
     "spotify_client_id": "your client id",
     "spotify_client_secret": "your client secret",
     "spotify_redirect_uri": "http://127.0.0.1:8888/callback"
   }
   ```

4. **Run again**: `python main.py`. The first time you open the Spotify tab
   a browser window will pop up asking you to log in and authorize the app.
   After that a token is cached locally and you won't need to log in again.

## Using the Apps & Games tab

- **Rescan Steam Library** finds Steam games via your Steam library folders
  and merges them in — this button only ever touches Steam-sourced entries.
- **Add App…** lets you pick any .exe (dev tools, anything else) and give it
  a display name and category. **Remove Selected** deletes the selected row
  outright. Both are the only ways non-Steam entries get in or out of the
  list — nothing is auto-scanned outside of Steam.
- Every entry lives in `data/apps_config.json` with `enabled`,
  `display_name`, and `category` fields you can also hand-edit directly.
- Unchecking a box hides that app from being launched but keeps it in the
  list. Rescanning never touches manually-added entries, and never
  overwrites your edits on Steam entries — it only adds newly-installed
  games and flags uninstalled ones as `missing`.
- Double-click a row to launch it.

## Known limitations / things to extend

- Windows only right now (Steam path lookup via `winreg`). A Mac/Linux
  version would need a different Steam library lookup path.
- No album art image is rendered yet — `get_now_playing()` already returns
  `album_art_url` if you want to load it into a `QLabel` with `QPixmap`.
- Spotify playback commands target whichever device is active, or the
  first available device if none is — if nothing is open anywhere
  (desktop, mobile, web player), Spotify's API can't launch one for you,
  so you'll get a clear error asking you to open Spotify first.
- Your app is in Spotify's "Development Mode" tier, which as of the
  Feb 2026 API changes has some restrictions (5 allow-listed users, no
  access to other users' playlists, smaller search page sizes, a few
  fields removed from track/album/artist objects). None of that affects
  this app's features, but worth knowing if you extend it later:
  https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide