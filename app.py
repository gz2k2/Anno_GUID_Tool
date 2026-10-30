"""
app.py
======

Main window of the Anno GUID Tool.

Responsibilities
----------------
* Load the user settings (:class:`AppConfig`) once and ONE GUID database
  (:class:`GuidDatabase`) PER GAME (Anno 117, Anno 1800).
* Show a GitHub button (top right) that opens the project page and,
  left of it, a "Ko-Fi Sponsor" button that opens the author's Ko-fi page.
* Show a game selector above the tabs. The selected game decides
    - which database the "GUID Database" tab shows / imports into,
    - which own / dummy GUID range the "Replace Dummy GUIDs" tab uses.
* Load the GUIDs reserved in the "Free GUIDs" tab (:class:`GuidReservations`),
  also one file per game.
* Create the tab view and the four tabs (order = display order):
    1. "GUID Database"       -> :class:`DatabaseTab`
    2. "Free GUIDs"          -> :class:`ReserveTab`
    3. "Replace Dummy GUIDs" -> :class:`ReplaceTab`
    4. "Settings"            -> :class:`SettingsTab`
* Accept mod folders / ZIPs dragged onto the window (Windows only)
  (:meth:`_poll_dropped_files`): on the "Replace Dummy GUIDs" tab the mod is
  loaded there, on every other tab it is registered in the active database.
* Provide translation (:meth:`tr`) and live language switching.
* Check GitHub for a newer version at startup (background thread) and
  show :class:`UpdateDialog` if one is available.

Tabs communicate with each other only through this object, e.g.
``app.database_tab.register_path(...)`` or ``app.replace_tab.on_ranges_changed()``.

Shortcuts used by the tabs
--------------------------
``app.game`` -> :class:`GameProfile` of the active game (GUID ranges)
``app.db``   -> :class:`GuidDatabase` of the active game
``app.reservations`` -> :class:`GuidReservations` of the active game
"""

import os
import queue
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from core.config_manager import AppConfig
from core.constants import APP_AUTHOR, APP_NAME, GAMES
from core.file_drop import enable_file_drop
from core.guid_database import GuidDatabase, migrate_legacy_database
from core.guid_reservations import GuidReservations
from core.mod_packages import ModPackages
from core.translations import TRANSLATIONS
from core.xml_scanner import split_mod_paths
from core.update_checker import GITHUB_REPO_URL, KOFI_URL, check_for_update_async
from core.version import read_version
from tabs.database_tab import DatabaseTab
from tabs.mod_package_tab import ModPackageTab
from tabs.replace_tab import ReplaceTab
from tabs.reserve_tab import ReserveTab
from dialogs.update_dialog import UpdateDialog
from dialogs.styled_dialogs import install_styled_dialogs
from tabs.settings_tab import SettingsTab

# Internal tab identifiers. CTkTabview uses the tab *name* as key, so fixed
# keys are used and only the visible button text is translated later.
TAB_KEY_DB = "tab_db"
TAB_KEY_PACKAGE = "tab_package"
TAB_KEY_RESERVE = "tab_reserve"
TAB_KEY_ASSIGN = "tab_assign"
TAB_KEY_SETTINGS = "tab_settings"

#: How often (ms) the UI thread checks for files dropped onto the window.
DROP_POLL_MS = 150


class GUIDManagerApp(ctk.CTk):
    """Root window. Holds shared state and wires the tabs together."""

    def __init__(self):
        super().__init__()
        install_styled_dialogs()
        self.geometry("1050x820")

        # Window icon
        for icon_name in ("AnnoGUIDTool.ico", "icon.ico"):
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name)
            if os.path.exists(icon_path):
                try:
                    self.iconbitmap(icon_path)
                    break
                except Exception:
                    pass

        #: Program version from version.txt (read once at startup), e.g. "v1.23.45"
        self.version = read_version()

        # --- Shared state ---------------------------------------------
        #: user settings (config.ini). Named "settings" (not "config")
        #: because tkinter already defines a "config" method on every widget.
        self.settings = AppConfig()

        # One-time migration of the old single database -> Anno 1800.
        self._legacy_migrated = migrate_legacy_database("anno1800")

        #: dict game key -> GuidDatabase (one JSON file per game)
        self.databases = {key: GuidDatabase(info["db_file"]) for key, info in GAMES.items()}

        #: dict game key -> GuidReservations ("Free GUIDs" tab, one JSON file per game)
        self.all_reservations = {key: GuidReservations(info["reserve_file"]) for key, info in GAMES.items()}
        self.all_mod_packages = {
            key: ModPackages(f"mod_packages_{key}.json") for key in GAMES
        }

        # Theme must be applied BEFORE widgets are created.
        ctk.set_appearance_mode(self.settings.appearance_mode)
        ctk.set_default_color_theme(self.settings.color_theme)

        # --- Game selector (above the tabs) ---------------------------
        game_bar = ctk.CTkFrame(self, fg_color="transparent")
        game_bar.pack(padx=20, pady=(15, 0), fill="x")

        self.lbl_game = ctk.CTkLabel(game_bar, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_game.pack(side="left", padx=(0, 10))

        # Segmented button shows the display names; mapping back to the key
        # is done in _on_game_selected().
        self._name_to_key = {info["name"]: key for key, info in GAMES.items()}
        self.seg_game = ctk.CTkSegmentedButton(
            game_bar, values=list(self._name_to_key), command=self._on_game_selected,
        )
        self.seg_game.set(GAMES[self.settings.active_game]["name"])
        self.seg_game.pack(side="left")

        # GitHub button (top right): opens the project page in the default
        # browser. Dark GitHub-style colors in both appearance modes.
        self.btn_github = ctk.CTkButton(
            game_bar, text="GitHub", width=90,
            fg_color=("#24292f", "#333a42"), hover_color=("#3d444d", "#4a525c"),
            text_color="white", font=ctk.CTkFont(weight="bold"),
            command=lambda: webbrowser.open(GITHUB_REPO_URL),
        )
        self.btn_github.pack(side="right")

        # Ko-fi button, left of the GitHub button (packed after it with
        # side="right", so it appears to its left). Ko-fi brand red.
        self.btn_kofi = ctk.CTkButton(
            game_bar, text="Ko-Fi Sponsor", width=120,
            fg_color="#FF5E5B", hover_color="#E04845",
            text_color="white", font=ctk.CTkFont(weight="bold"),
            command=lambda: webbrowser.open(KOFI_URL),
        )
        self.btn_kofi.pack(side="right", padx=(0, 8))

        # --- Tab view -------------------------------------------------
        self.tabview = ctk.CTkTabview(self, command=self._on_tab_changed)
        self.tabview.pack(padx=20, pady=(10, 20), fill="both", expand=True)

        frame_db = self.tabview.add(TAB_KEY_DB)
        frame_package = self.tabview.add(TAB_KEY_PACKAGE)
        frame_reserve = self.tabview.add(TAB_KEY_RESERVE)
        frame_assign = self.tabview.add(TAB_KEY_ASSIGN)
        frame_settings = self.tabview.add(TAB_KEY_SETTINGS)

        self.database_tab = DatabaseTab(self, frame_db)
        self.mod_package_tab = ModPackageTab(self, frame_package)
        self.reserve_tab = ReserveTab(self, frame_reserve)
        self.replace_tab = ReplaceTab(self, frame_assign)
        self.settings_tab = SettingsTab(self, frame_settings)

        # Fill all texts for the configured language.
        self.update_ui_language()
        self._update_title()

        # Inform the user once about the migrated database (after the
        # window is drawn so the message box has a parent).
        if self._legacy_migrated:
            self.after(200, lambda: messagebox.showinfo(
                self.tr("msg_migrated_title"),
                self.tr("msg_migrated_body").format(GAMES["anno1800"]["db_file"]),
            ))

        # Drag & drop of mod folders / ZIPs onto the window.
        self._enable_file_drop()

        # Look for a newer version on GitHub (non-blocking).
        self._start_update_check()

    # ------------------------------------------------------------------
    # Drag & drop
    # ------------------------------------------------------------------
    def _enable_file_drop(self):
        """Register the window as drop target and show the hint if it worked.

        The native handle of the top-level window (``wm_frame``) only exists
        after the window has been created, hence ``update_idletasks`` first.
        """
        #: dropped path lists, filled by the window procedure (see core/file_drop.py
        #: why it must not call Tkinter itself) and emptied by _poll_dropped_files().
        self._drop_queue = queue.Queue()
        self._drop_busy = False
        try:
            self.update_idletasks()
            hwnd = int(self.wm_frame(), 16)
            enabled = enable_file_drop(hwnd, self._drop_queue.put)
        except Exception as e:
            print(f"Drag & drop not available: {e}")
            enabled = False
        if enabled:
            self.database_tab.enable_drop_hint()
            self.replace_tab.enable_drop_hint()
            self.after(DROP_POLL_MS, self._poll_dropped_files)

    def _poll_dropped_files(self):
        """Register dropped mods in the UI thread; re-schedules itself.

        While an import (or its summary dialog, which runs a nested event
        loop) is still open, new drops stay in the queue until it is done.
        """
        if not self._drop_busy:
            try:
                paths = self._drop_queue.get_nowait()
            except queue.Empty:
                paths = None
            if paths:
                self._drop_busy = True
                try:
                    self._handle_drop(paths)
                finally:
                    self._drop_busy = False
        self.after(DROP_POLL_MS, self._poll_dropped_files)

    def _handle_drop(self, paths):
        """Send dropped mod folders / ZIPs to the tab that fits the shown tab.

        * "Replace Dummy GUIDs" shown -> load the mod there for replacement
        * "Free GUIDs" shown          -> register, but stay on that tab so the
                                         reserved GUIDs are seen turning "registered"
        * any other tab               -> switch to "GUID Database" and register

        Other files are ignored; if no folder / ZIP was dropped at all, a
        warning lists what was rejected.
        """
        mods, rejected = split_mod_paths(paths)
        if not mods:
            messagebox.showwarning(self.tr("msg_drop_invalid_title"),
                                   self.tr("msg_drop_invalid_body").format("\n".join(rejected)))
            return
        tab = self.tabview.get()
        if tab == TAB_KEY_ASSIGN:
            self.replace_tab.handle_drop(mods)
        elif tab == TAB_KEY_RESERVE:
            self.database_tab.register_paths(mods)
            self.reserve_tab.refresh_view()
        else:
            self.tabview.set(TAB_KEY_DB)
            self.database_tab.register_paths(mods)

    # ------------------------------------------------------------------
    # Update check
    # ------------------------------------------------------------------
    def _start_update_check(self):
        """Start the GitHub update check and poll for its result.

        Tkinter must only be used from the UI thread. The background thread
        therefore only puts the remote version into a queue; the UI thread
        polls the queue with ``after()`` and opens the popup itself.
        Polling stops after ~15 s (request timeout is 5 s), so no timer keeps
        running if there is no answer.
        """
        self._update_queue = queue.Queue()
        check_for_update_async(self.version, self._update_queue.put)
        self.after(500, self._poll_update_result, 30)

    def _poll_update_result(self, remaining):
        """Show the update popup as soon as the background check reports a newer version."""
        try:
            remote_version = self._update_queue.get_nowait()
        except queue.Empty:
            if remaining > 0:
                self.after(500, self._poll_update_result, remaining - 1)
            return
        UpdateDialog(self, self.version, remote_version)

    # ------------------------------------------------------------------
    # Active game
    # ------------------------------------------------------------------
    @property
    def game(self):
        """:class:`GameProfile` (GUID ranges) of the active game."""
        return self.settings.active

    @property
    def db(self):
        """:class:`GuidDatabase` of the active game."""
        return self.databases[self.settings.active_game]

    @property
    def mod_packages(self):
        """:class:`ModPackages` of the active game."""
        return self.all_mod_packages[self.settings.active_game]

    @property
    def reservations(self):
        """:class:`GuidReservations` (reserved GUIDs) of the active game."""
        return self.all_reservations[self.settings.active_game]

    def reload_active_data(self):
        """Reload the active game's database, reservations and packages from disk."""
        key = self.settings.active_game
        self.databases[key] = GuidDatabase(self.databases[key].path)
        self.all_reservations[key] = GuidReservations(self.all_reservations[key].path)
        self.all_mod_packages[key] = ModPackages(self.all_mod_packages[key].path)

    def show_reserve_tab(self):
        """Switch to the "Free GUIDs" tab (e.g. from the database's right-click menu)."""
        self.tabview.set(TAB_KEY_RESERVE)
        self._on_tab_changed()

    def _on_tab_changed(self):
        """Refresh the "Free GUIDs" tab whenever it is shown.

        Its "registered" state and comments come from the database, which
        the other tabs change (import, delete, move, replace). Likewise the
        database table shows the reserved ranges of the Free GUIDs lists.
        """
        if self.tabview.get() == TAB_KEY_PACKAGE:
            self.mod_package_tab.refresh_view()
        elif self.tabview.get() == TAB_KEY_RESERVE:
            self.reserve_tab.refresh_view()
        elif self.tabview.get() == TAB_KEY_DB:
            self.database_tab.refresh_view()

    def _on_game_selected(self, display_name):
        """Callback of the game selector: switch the active game.

        Persists the choice and refreshes every part of the UI that depends
        on the game (database table, ranges / start GUID / dummy scan in the
        Replace tab, window title).
        """
        key = self._name_to_key[display_name]
        if key == self.settings.active_game:
            return
        self.settings.active_game = key
        self.settings.save()

        self._update_title()
        self.database_tab.refresh_view()
        self.mod_package_tab.refresh_view()
        self.reserve_tab.refresh_view()
        self.replace_tab.on_game_changed()

    def _update_title(self):
        """Set the window title: "Anno GUID Tool v1.23.45 by gz2k2 - Anno 1800".

        Called at startup and whenever the game is switched. Without a
        readable version.txt the version part is simply left out.
        """
        version = f" {self.version}" if self.version else ""
        self.title(f"{APP_NAME}{version} by {APP_AUTHOR} - {self.game.name}")

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------
    def tr(self, key):
        """Return the UI text for ``key`` in the active language.

        Fallback order: active language -> German -> the key itself.
        """
        lang_dict = TRANSLATIONS.get(self.settings.language, TRANSLATIONS["de"])
        return lang_dict.get(key, TRANSLATIONS["de"].get(key, key))

    def set_language(self, lang):
        """Switch the UI language ("de"/"en"), persist it and refresh all texts."""
        self.settings.language = lang
        self.settings.save()
        self.update_ui_language()

    def update_ui_language(self):
        """Refresh the tab captions and let every tab update its own texts."""
        self.lbl_game.configure(text=self.tr("lbl_game"))

        # CTkTabview has no public API to rename a tab, so the internal
        # segmented button is accessed. Wrapped in try/except in case the
        # internal structure changes in a future CustomTkinter version.
        try:
            buttons = self.tabview._segmented_button._buttons_dict
            for key in (TAB_KEY_DB, TAB_KEY_PACKAGE, TAB_KEY_RESERVE, TAB_KEY_ASSIGN, TAB_KEY_SETTINGS):
                if key in buttons:
                    buttons[key].configure(text=self.tr(key))
        except Exception as e:
            print(f"Error updating tab captions: {e}")

        self.database_tab.update_language()
        self.mod_package_tab.update_language()
        self.reserve_tab.update_language()
        self.replace_tab.update_language()
        self.settings_tab.update_language()
