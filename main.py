"""
Music + App Launcher Dashboard
Run with: python main.py

Two tabs:
  - Spotify: now-playing, transport controls, playlists (double-click to play)
  - Apps & Games: curated launcher populated from Steam, plus manually added
    apps. Select a row and click "Launch Selected" to run it; double-click
    Name/Category to edit in place (saved automatically).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QCheckBox, QTabWidget, QMessageBox, QAbstractItemView,
    QFileDialog, QInputDialog,
)

from spotify_client import SpotifyClient
from app_scanner import (
    rescan_and_merge, load_apps_config, save_apps_config,
    add_manual_entry, remove_entry,
)
from launcher import launch


class NowPlayingWidget(QWidget):
    def __init__(self, spotify: SpotifyClient):
        super().__init__()
        self.spotify = spotify
        self._is_playing = False

        layout = QVBoxLayout(self)

        self.track_label = QLabel("Loading…")
        self.track_label.setWordWrap(True)
        self.track_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.artist_label = QLabel("")
        layout.addWidget(self.track_label)
        layout.addWidget(self.artist_label)

        controls = QHBoxLayout()
        self.prev_btn = QPushButton("⏮")
        self.play_btn = QPushButton("⏯")
        self.next_btn = QPushButton("⏭")
        self.prev_btn.clicked.connect(self._on_prev)
        self.play_btn.clicked.connect(self._on_play_pause)
        self.next_btn.clicked.connect(self._on_next)
        for btn in (self.prev_btn, self.play_btn, self.next_btn):
            btn.setFixedSize(64, 64)
            btn.setStyleSheet("font-size: 28px;")
            controls.addWidget(btn)
        controls.addStretch()
        layout.addLayout(controls)

        layout.addWidget(QLabel("Playlists (double-click to play):"))
        self.playlist_list = QListWidget()
        self.playlist_list.itemDoubleClicked.connect(self._on_playlist_activated)
        layout.addWidget(self.playlist_list)

        self._load_playlists()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_now_playing)
        self.timer.start(5000)
        self.refresh_now_playing()

    def _load_playlists(self):
        try:
            for pl in self.spotify.get_playlists():
                item = QListWidgetItem(f"{pl['name']} ({pl['track_count']} tracks)")
                item.setData(Qt.UserRole, pl["uri"])
                self.playlist_list.addItem(item)
        except Exception as e:
            self.playlist_list.addItem(f"Could not load playlists: {e}")

    def refresh_now_playing(self):
        try:
            now = self.spotify.get_now_playing()
        except Exception as e:
            self.track_label.setText("Spotify error")
            self.artist_label.setText(str(e))
            return

        if not now:
            self.track_label.setText("Nothing playing")
            self.artist_label.setText("")
            self._is_playing = False
            return

        self.track_label.setText(now["track"])
        self.artist_label.setText(f"{now['artist']} — {now['album']}")
        self._is_playing = now["is_playing"]

    def _on_play_pause(self):
        try:
            self.spotify.toggle_playback(self._is_playing)
            self._is_playing = not self._is_playing
        except Exception as e:
            QMessageBox.warning(self, "Spotify", str(e))

    def _on_next(self):
        try:
            self.spotify.next_track()
        except Exception as e:
            QMessageBox.warning(self, "Spotify", str(e))

    def _on_prev(self):
        try:
            self.spotify.previous_track()
        except Exception as e:
            QMessageBox.warning(self, "Spotify", str(e))

    def _on_playlist_activated(self, item: QListWidgetItem):
        uri = item.data(Qt.UserRole)
        if not uri:
            return
        try:
            self.spotify.play_playlist(uri)
        except Exception as e:
            QMessageBox.warning(self, "Spotify", str(e))


class AppLauncherWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        self.launch_btn = QPushButton("Launch Selected")
        self.launch_btn.clicked.connect(self.launch_selected)
        self.rescan_btn = QPushButton("Rescan Steam Library")
        self.rescan_btn.clicked.connect(self.rescan)
        self.add_btn = QPushButton("Add App…")
        self.add_btn.clicked.connect(self.add_app)
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected)
        top_row.addWidget(self.launch_btn)
        top_row.addWidget(self.rescan_btn)
        top_row.addWidget(self.add_btn)
        top_row.addWidget(self.remove_btn)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Enabled", "Name", "Category", "Source"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        hint = QLabel(
            "Select a row and click \"Launch Selected\" to run it. Double-click Name "
            "or Category to edit — changes save automatically. \"Rescan\" only "
            "touches Steam games — use \"Add App…\" / \"Remove Selected\" for "
            "everything else."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        self.apps_config = load_apps_config()
        self._populate_table()

    def rescan(self):
        self.apps_config = rescan_and_merge()
        self._populate_table()

    def add_app(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select an executable", "", "Programs (*.exe)")
        if not path:
            return
        default_name = Path(path).stem
        name, ok = QInputDialog.getText(self, "App name", "Display name:", text=default_name)
        if not ok or not name.strip():
            return
        category, ok = QInputDialog.getText(self, "Category", "Category (e.g. dev, games, other):", text="uncategorized")
        if not ok:
            category = "uncategorized"
        add_manual_entry(name.strip(), path, category.strip() or "uncategorized")
        self.apps_config = load_apps_config()
        self._populate_table()

    def remove_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        key = self.table.item(row, 1).data(Qt.UserRole)
        name = self.table.item(row, 1).text()
        confirm = QMessageBox.question(
            self, "Remove app",
            f"Remove '{name}' from the list? (Steam games will reappear on the next rescan if still installed.)",
        )
        if confirm != QMessageBox.Yes:
            return
        remove_entry(key)
        self.apps_config = load_apps_config()
        self._populate_table()

    def _populate_table(self):
        # Block itemChanged while we build the table so populating rows
        # doesn't get mistaken for the user editing them.
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        visible = {k: v for k, v in self.apps_config.items() if not v.get("missing")}
        for key, entry in sorted(visible.items(), key=lambda kv: kv[1]["display_name"].lower()):
            row = self.table.rowCount()
            self.table.insertRow(row)

            checkbox = QCheckBox()
            checkbox.setChecked(entry.get("enabled", True))
            checkbox.stateChanged.connect(lambda state, k=key: self._on_toggle(k, state))
            self.table.setCellWidget(row, 0, checkbox)

            name_item = QTableWidgetItem(entry["display_name"])
            name_item.setData(Qt.UserRole, key)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("category", "uncategorized")))

            source_item = QTableWidgetItem(entry.get("source", ""))
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, source_item)
        self.table.blockSignals(False)

    def _on_toggle(self, key: str, state: int):
        self.apps_config[key]["enabled"] = bool(state)
        save_apps_config(self.apps_config)

    def _on_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        name_item = self.table.item(row, 1)
        if name_item is None:
            return
        key = name_item.data(Qt.UserRole)
        if key not in self.apps_config:
            return
        entry = self.apps_config[key]

        if item.column() == 1:  # Name
            new_name = item.text().strip()
            if new_name:
                entry["display_name"] = new_name
            else:
                self.table.blockSignals(True)
                item.setText(entry["display_name"])
                self.table.blockSignals(False)
        elif item.column() == 2:  # Category
            entry["category"] = item.text().strip() or "uncategorized"

        save_apps_config(self.apps_config)

    def launch_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Launch", "Select an app first.")
            return
        key = self.table.item(row, 1).data(Qt.UserRole)
        entry = self.apps_config[key]
        if not entry.get("enabled", True):
            QMessageBox.information(self, "Launch", f"'{entry['display_name']}' is disabled — check its box to enable it.")
            return
        try:
            launch(entry)
        except Exception as e:
            QMessageBox.warning(self, "Launch failed", str(e))

    def save_now(self):
        """Explicit flush, called on app close as a final safety net —
        edits already save immediately as you make them."""
        save_apps_config(self.apps_config)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dashboard")
        self.resize(900, 600)

        tabs = QTabWidget()
        try:
            spotify = SpotifyClient()
            tabs.addTab(NowPlayingWidget(spotify), "Spotify")
        except Exception as e:
            tabs.addTab(QLabel(f"Spotify unavailable: {e}"), "Spotify")

        self.app_launcher = AppLauncherWidget()
        tabs.addTab(self.app_launcher, "Apps & Games")
        self.setCentralWidget(tabs)

    def closeEvent(self, event):
        # Edits already save immediately as you make them; this is just a
        # final flush so nothing is lost on close.
        self.app_launcher.save_now()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()