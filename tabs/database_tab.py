"""
database_tab.py
===============

Tab "GUID Database" – shows, searches, imports, exports and deletes the
GUIDs registered in the database of the ACTIVE game
(``guid_database_anno1800.json`` or ``guid_database_anno117.json``).
Switching the game in the game selector reloads the table via
:meth:`DatabaseTab.refresh_view`; ``app.db`` always points to the active
game's database, so every action below works on that game only.

Features
--------
* **Register Folder / Register ZIP**: scans all XML files of a mod and adds
  every GUID defined in ``<GUID>`` / ``<LineId>`` tags that lies inside the
  OWN GUID range of the active game (Settings) to that game's database, together with the file
  it was found in.
* **Drag & drop** (Windows): mod folders / ZIPs dropped onto the window
  (while this or the Settings tab is shown) are registered the same way
  via :meth:`DatabaseTab.register_paths`.
* **Comment column**: shows the comment of a GUID, read from XML comments
  in the format ``GUID - comment`` (e.g. ``2144009900 - Praefectus Name``)
  while registering a mod.
* **Reserved ranges** ("Show reserved"): GUIDs reserved in the Free GUIDs
  lists and not registered yet are shown as blue rows, one per continuous
  range and project, with the project name as comment. These rows are
  read-only (Delete / Move ignore them); right-click jumps to the project.
* **Search field**: live filter by GUID, comment or file path (on every key release).
* **Sorting**: click the GUID or Location heading to sort by it; click
  again to reverse (▲ ascending / ▼ descending).
* **Export .csv**: writes the whole database (GUID ; Comment ; Location) to a ``;``-separated CSV
  (UTF-8 with BOM so Excel shows umlauts correctly).
* **Delete**: via button, ``Del`` key or right-click context menu;
  multi-selection supported, ``Ctrl+A`` selects all visible rows.
* **Move to <other game>** (right-click menu): moves the selected entries
  into the database of another game – useful if a mod was registered while
  the wrong game was selected.
* **GUID collisions**: if an imported mod defines a GUID that the database
  lists for ANOTHER mod, that it defines more than once itself, or that is
  reserved in the Free GUIDs list of another project,
  :class:`CollisionDialog` asks per GUID whether to migrate the imported mod
  to a free GUID (its files are rewritten) or to accept the risk. Colliding
  GUIDs are shown in red with "!" in the table.
* **Migrate a mod to a free GUID…** (right-click on a red GUID): moves one of
  the mods that define the GUID to the next free GUID later on
  (:meth:`DatabaseTab.migrate_collision`).
* **Check Collisions**: scans a folder with many mods (folders and ZIPs) for
  GUIDs defined in more than one mod, or in a mod other than the one the
  database lists – without importing anything (:class:`CollisionReport`).
"""

import csv
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from core.collisions import find_import_collisions, guids_by_mod, mods_of_locations, scan_folder_collisions
from core.guid_database import guid_sort_key
from core.xml_scanner import apply_dummy_map, mod_of_location, rewrite_xml_files, scan_mod
from dialogs.collision_dialog import DECISION_ACCEPT, DECISION_MIGRATE, CollisionDialog
from dialogs.collision_report import CollisionReport
from dialogs.migrate_dialog import SOURCE_ZIP, MigrateDialog

#: Font of the table rows; also used to measure text widths for auto-sizing.
TREE_FONT = ("Consolas", 10)
# ---------------------------------------------------------------------------
# Column widths of the GUID table (all values in pixels)
# ---------------------------------------------------------------------------
# *_WIDTH     = initial width when the table is created
# *_MINWIDTH  = smallest width the user can drag the column to
#
# GUID column: fixed width (GUIDs always have about the same length).
GUID_COL_WIDTH = 90
GUID_COL_MINWIDTH = 80

# Comment column: sized automatically to the longest visible comment after
# every refresh, limited to COMMENT_COL_MIN ... COMMENT_COL_MAX.
COMMENT_COL_MIN = 150
COMMENT_COL_MAX = 450
COMMENT_COL_MINWIDTH = 80

# Location column: sized automatically to the longest visible path, but at
# least the remaining visible width and never smaller than LOCATION_COL_MIN.
LOCATION_COL_WIDTH = 600
LOCATION_COL_MIN = 200
LOCATION_COL_MINWIDTH = 200

# Extra space (pixels) added to measured text widths for the cell margins.
COL_TEXT_PADDING = 20

#: Marker behind the GUID of a row whose GUID is defined in more than one mod.
COLLISION_MARK = " !"
#: Text color of such rows: (light mode, dark mode).
COLLISION_COLOR = ("#c92a2a", "#ff6b6b")
#: Text color of the reserved-range rows (Free GUIDs): (light mode, dark mode).
RESERVED_COLOR = ("#1c64b4", "#74b0f0")
#: Row id prefix of reserved-range rows: "res:<index>" (see _reserved_rows).
RESERVED_IID = "res:"


def guid_ranges(guids):
    """Group numeric GUID strings into ``[(first, last, [guids]), ...]`` of consecutive numbers."""
    runs = []
    for guid in sorted((g for g in guids if g.isdigit()), key=int):
        if runs and int(guid) == int(runs[-1][1]) + 1:
            runs[-1][1] = guid
            runs[-1][2].append(guid)
        else:
            runs.append([guid, guid, [guid]])
    return [tuple(run) for run in runs]


class ImportCancelled(Exception):
    """The user cancelled the import of a mod in the collision dialog."""


class DatabaseTab:
    """Builds and controls the "GUID Database" tab.

    :param app:    the main :class:`GUIDManagerApp` (gives access to
                   ``app.game``, ``app.db``, ``app.tr`` …)
    :param parent: the CTkTabview frame this tab is drawn into
    """

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        #: Sort order of the table: column key ("guid" / "location") + direction.
        self._sort_column = "guid"
        self._sort_desc = False
        self._build_ui()
        self.refresh_view()

    # ==================================================================
    # UI construction
    # ==================================================================
    def _build_ui(self):
        """Create all widgets: toolbar, statistics bar and GUID table."""
        # --- Toolbar (buttons left, search field right) ---------------
        top_frame = ctk.CTkFrame(self.parent)
        top_frame.pack(padx=10, pady=10, fill="x")

        self.btn_import_folder = ctk.CTkButton(top_frame, text="", command=self.import_folder)
        self.btn_import_folder.pack(side="left", padx=5, pady=10)

        self.btn_import_zip = ctk.CTkButton(top_frame, text="", command=self.import_zip)
        self.btn_import_zip.pack(side="left", padx=5, pady=10)

        self.btn_check_collisions = ctk.CTkButton(
            top_frame, text="", fg_color="#e67700", hover_color="#c25e00",
            command=self.check_collisions,
        )
        self.btn_check_collisions.pack(side="left", padx=5, pady=10)

        self.btn_export_csv = ctk.CTkButton(
            top_frame, text="", fg_color="#2b8a3e", hover_color="#216a2f",
            command=self.export_to_csv,
        )
        self.btn_export_csv.pack(side="left", padx=5, pady=10)

        self.btn_delete = ctk.CTkButton(
            top_frame, text="", fg_color="#d9534f", hover_color="#c9302c",
            command=self.delete_selected,
        )
        self.btn_delete.pack(side="left", padx=5, pady=10)

        self.entry_search = ctk.CTkEntry(top_frame, placeholder_text="", width=220)
        self.entry_search.pack(side="right", padx=10, pady=10)
        # Re-filter the table on every key stroke.
        self.entry_search.bind("<KeyRelease>", self.refresh_view)

        # --- Statistics bar ("Registered GUIDs: N") -------------------
        stats_frame = ctk.CTkFrame(self.parent)
        stats_frame.pack(padx=10, pady=(5, 5), fill="x")

        self.lbl_stats = ctk.CTkLabel(stats_frame, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_stats.pack(side="left", anchor="w", padx=15, pady=8)

        self.var_show_reserved = tk.BooleanVar(value=self.app.settings.show_reserved_in_db)
        self.chk_show_reserved = ctk.CTkCheckBox(
            stats_frame, text="", variable=self.var_show_reserved,
            command=self._on_show_reserved_toggled,
        )
        self.chk_show_reserved.pack(side="left", padx=15, pady=8)
        #: list name per reserved-range row id (for the right-click jump)
        self._reserved_lists = {}

        # Drag & drop hint (right). Only packed by enable_drop_hint() once the
        # app has activated drag & drop, so it never promises a missing feature.
        self.lbl_drop_hint = ctk.CTkLabel(stats_frame, text="", text_color="gray")

        # --- GUID table (ttk.Treeview, because CTk has no table widget)
        table_container = ctk.CTkFrame(self.parent)
        table_container.pack(padx=10, pady=(0, 10), fill="both", expand=True)

        self.tree = ttk.Treeview(
            table_container, columns=("guid", "comment", "location"),
            show="headings", selectmode="extended",
        )
        self.apply_treeview_style()
        # stretch=False is required for horizontal scrolling: a stretching
        # column always shrinks to the visible width, so the content would
        # never become wider than the table and the x-scrollbar stays inactive.
        # Column order: GUID | Comment | Location.
        # Comment and location widths are adapted to their content after
        # every refresh (see refresh_view / _fit_location_column).
        self.tree.column("guid", width=GUID_COL_WIDTH, minwidth=GUID_COL_MINWIDTH,
                         anchor="w", stretch=False)
        self.tree.column("comment", width=COMMENT_COL_MIN, minwidth=COMMENT_COL_MINWIDTH,
                         anchor="w", stretch=False)
        self.tree.column("location", width=LOCATION_COL_WIDTH, minwidth=LOCATION_COL_MINWIDTH,
                         anchor="w", stretch=False)

        # Keyboard / mouse bindings
        self.tree.bind("<Delete>", lambda e: self.delete_selected())
        self.tree.bind("<Button-3>", self.show_context_menu)   # right click
        self.tree.bind("<Control-a>", self.select_all)

        # Vertical + horizontal scrollbars, both linked to the Treeview.
        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout:  [ tree | vsb ]
        #               [ hsb  |     ]
        # Only cell (0, 0) grows when the window is resized.
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=(5, 0))
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=(5, 0))
        hsb.grid(row=1, column=0, sticky="ew", padx=(5, 0), pady=(0, 5))
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Shift + mouse wheel scrolls horizontally (Windows: event.delta = ±120).
        self.tree.bind("<Shift-MouseWheel>",
                       lambda e: self.tree.xview_scroll(int(-e.delta / 120), "units"))
        # Re-fit the location column when the table is resized, so it always
        # fills at least the visible area (no empty gap on the right).
        self.tree.bind("<Configure>", lambda e: self._fit_location_column())
        self._location_text_width = 0

    def apply_treeview_style(self):
        """Style the ttk.Treeview to match the current CTk appearance mode.

        ttk widgets do not follow CustomTkinter's light/dark mode
        automatically, so colors are set manually. Called on startup and
        whenever the appearance mode is changed in the Settings tab.
        """
        style = ttk.Style()
        style.theme_use("clam")  # "clam" allows custom heading/background colors

        is_dark = ctk.get_appearance_mode() == "Dark"
        heading_bg = "#2b2b2b" if is_dark else "#e0e0e0"
        text_fg = "#ffffff" if is_dark else "#000000"
        field_bg = "#1e1e1e" if is_dark else "#ffffff"

        style.configure(
            "Treeview", background=field_bg, foreground=text_fg,
            fieldbackground=field_bg, rowheight=25, font=TREE_FONT,
        )
        style.configure(
            "Treeview.Heading", background=heading_bg, foreground=text_fg,
            font=("Arial", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", "#1f538d")])

    def update_language(self):
        """Set all texts of this tab according to the active UI language."""
        tr = self.app.tr
        self.btn_import_folder.configure(text=tr("btn_import_folder"))
        self.btn_import_zip.configure(text=tr("btn_import_zip"))
        self.btn_check_collisions.configure(text=tr("btn_check_collisions"))
        self.btn_export_csv.configure(text=tr("btn_export_csv"))
        self.btn_delete.configure(text=tr("btn_delete"))
        self.entry_search.configure(placeholder_text=tr("search_ph"))
        self.lbl_drop_hint.configure(text=tr("drop_hint"))
        self.chk_show_reserved.configure(text=tr("chk_show_reserved"))
        self._update_headings()
        self._update_stats()

    def _update_headings(self):
        """Set the column headings; the sorted column gets an ▲ / ▼ arrow.

        Clicking the GUID or Location heading sorts by that column
        (see :meth:`sort_by`); the Comment column is not sortable.
        """
        tr = self.app.tr
        arrow = " ▼" if self._sort_desc else " ▲"

        def text(column, key):
            return tr(key) + (arrow if column == self._sort_column else "")

        # anchor="w" -> column headings left-aligned (ttk default is centered)
        self.tree.heading("guid", text=text("guid", "tree_guid"), anchor="w",
                          command=lambda: self.sort_by("guid"))
        self.tree.heading("comment", text=tr("tree_comment"), anchor="w")
        self.tree.heading("location", text=text("location", "tree_loc"), anchor="w",
                          command=lambda: self.sort_by("location"))

    def sort_by(self, column):
        """Heading click: sort by ``column``; clicking it again reverses the order.

        A newly chosen column always starts ascending. The order is kept
        while searching, importing etc. (it is applied in :meth:`refresh_view`).
        """
        if column == self._sort_column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_column, self._sort_desc = column, False
        self._update_headings()
        self.refresh_view()

    # ==================================================================
    # Table view
    # ==================================================================
    def _update_stats(self):
        """Refresh the "Registered GUIDs (<game>): N" label (+ number of collisions)."""
        db = self.app.db
        text = self.app.tr("guids_count").format(self.app.game.name, len(db))
        res = self.app.reservations
        collisions = sum(1 for guid in db.entries if db.is_collision(guid, res))
        if collisions:
            text += self.app.tr("guids_collisions").format(collisions)
        self.lbl_stats.configure(text=text)

    def refresh_view(self, event=None):
        """Rebuild the table from the database, applying the search filter.

        A row is shown if the (case-insensitive) search text is contained in
        the GUID, the comment or the comma-separated list of file locations.
        ``event`` is unused; it exists so the method can be bound to key events.
        """
        query = self.entry_search.get().lower().strip()
        self._update_stats()

        self.tree.delete(*self.tree.get_children())

        # Rows: (sort key, values, tags, list name for reserved rows).
        rows = []
        for guid, comment, locations in self.app.db.sorted_items():
            location_str = ", ".join(locations)
            if query and not any(query in text.lower() for text in (guid, comment, location_str)):
                continue
            # Colliding GUIDs: red, with "!" behind the GUID.
            if self.app.db.is_collision(guid, self.app.reservations):
                rows.append((guid_sort_key(guid), (guid + COLLISION_MARK, comment, location_str),
                             ("collision",), None))
            else:
                rows.append((guid_sort_key(guid), (guid, comment, location_str), (), None))
        if self.var_show_reserved.get():
            for row in self._reserved_rows():
                if not query or any(query in text.lower() for text in row[1]):
                    rows.append(row)

        # GUID order first (ranges sort by their first GUID). Location sorting
        # is case-insensitive; Python's sort is stable (also with
        # reverse=True), so rows with the same location stay in GUID order.
        rows.sort(key=lambda row: row[0])
        if self._sort_column == "location":
            rows.sort(key=lambda row: row[1][2].lower(), reverse=self._sort_desc)
        elif self._sort_desc:
            rows.reverse()

        dark = 1 if ctk.get_appearance_mode() == "Dark" else 0
        self.tree.tag_configure("collision", foreground=COLLISION_COLOR[dark])
        self.tree.tag_configure("reserved", foreground=RESERVED_COLOR[dark])
        self._reserved_lists = {}
        for index, (_, values, tags, list_name) in enumerate(rows):
            if list_name is None:
                self.tree.insert("", "end", values=values, tags=tags)
            else:
                iid = f"{RESERVED_IID}{index}"
                self._reserved_lists[iid] = list_name
                self.tree.insert("", "end", iid=iid, values=values, tags=tags)

        # Measure the longest visible texts (pixels, Treeview font).
        font = tkfont.Font(family=TREE_FONT[0], size=TREE_FONT[1])
        items = self.tree.get_children()

        def longest(column):
            return max((font.measure(self.tree.set(i, column)) for i in items), default=0)

        # GUID column: wide enough for reserved ranges ("first – last").
        self.tree.column("guid", width=max(GUID_COL_WIDTH, longest("guid") + COL_TEXT_PADDING))

        # Comment column: fit to the longest comment, but within limits so a
        # very long comment does not push the locations far to the right.
        comment_width = min(max(longest("comment") + COL_TEXT_PADDING, COMMENT_COL_MIN), COMMENT_COL_MAX)
        self.tree.column("comment", width=comment_width)

        self._location_text_width = longest("location")
        self._fit_location_column()

    def _reserved_rows(self):
        """Rows for the GUIDs reserved in the Free GUIDs lists that are NOT registered yet.

        One row per continuous range and list: GUID column "first – last",
        the list (mod project) name as comment, and the number of reserved /
        used GUIDs as location. Format: (sort key, values, tags, list name).
        """
        tr = self.app.tr
        rows = []
        for name, items in self.app.reservations.lists.items():
            open_guids = [g for g in items if g not in self.app.db]
            for first, last, guids in guid_ranges(open_guids):
                used = sum(1 for g in guids if items[g]["used"])
                rows.append((
                    guid_sort_key(first),
                    (first if first == last else f"{first} – {last}",
                     tr("db_reserved_comment").format(name),
                     tr("db_reserved_location").format(len(guids), used)),
                    ("reserved",), name,
                ))
        return rows

    def _on_show_reserved_toggled(self):
        """Persist the "Show reserved" checkbox and refresh the table."""
        self.app.settings.show_reserved_in_db = bool(self.var_show_reserved.get())
        self.app.settings.save()
        self.refresh_view()

    def show_in_free_guids(self, list_name):
        """Switch to the Free GUIDs tab and select the project ``list_name``."""
        self.app.reservations.set_active(list_name)
        self.app.reservations.save()
        self.app.show_reserve_tab()

    def _fit_location_column(self):
        """Size the location column so that long paths can be scrolled horizontally.

        Width = max(longest text + padding, remaining visible width).
        * Longer than the view -> the horizontal scrollbar becomes active.
        * Shorter than the view -> the column fills the free space on the right.
        """
        visible = (self.tree.winfo_width()
                   - self.tree.column("guid", "width")
                   - self.tree.column("comment", "width"))
        needed = self._location_text_width + COL_TEXT_PADDING
        self.tree.column("location", width=max(needed, visible, LOCATION_COL_MIN))

    def enable_drop_hint(self):
        """Show the "drop a mod here" hint (called by the app if drag & drop works)."""
        self.lbl_drop_hint.pack(side="right", padx=15, pady=8)

    def select_all(self, event=None):
        """Select all visible rows (Ctrl+A). Returns "break" to stop default handling."""
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children)
        return "break"

    def show_context_menu(self, event):
        """Show the right-click menu for the selected rows.

        Entries:
          * "Copy GUID" – copies the selected database GUIDs to the clipboard
          * "Migrate a mod to a free GUID…" – only for ONE selected red
            (colliding) GUID, see :meth:`migrate_collision`
          * "Move to <game>" – one entry for every game except the active one
          * separator
          * "Delete selected entries"


        If the clicked row is not part of the current selection, the
        selection is replaced by that row (standard explorer behaviour).
        The menu label shows the number of rows when more than one is selected.
        """
        item = self.tree.identify_row(event.y)
        if not item:
            return
        # Reserved-range row: only the jump to its project.
        if item in self._reserved_lists:
            self.tree.selection_set(item)
            name = self._reserved_lists[item]
            menu = tk.Menu(self.app, tearoff=0)
            menu.add_command(label=self.app.tr("ctx_show_in_free").format(name),
                             command=lambda: self.show_in_free_guids(name))
            menu.post(event.x_root, event.y_root)
            return
        if item not in self.tree.selection():
            self.tree.selection_set(item)

        guids = self._selected_guids()
        count = len(guids)
        suffix = f" ({count})" if count > 1 else ""

        menu = tk.Menu(self.app, tearoff=0)
        menu.add_command(
            label=self.app.tr("ctx_copy_guid") + suffix,
            command=self.copy_selected_guids,
        )
        menu.add_separator()

        if len(guids) == 1 and self.app.db.is_collision(guids[0], self.app.reservations):
            menu.add_command(label=self.app.tr("ctx_migrate"),
                             command=lambda g=guids[0]: self.migrate_collision(g))
            menu.add_separator()

        # One "Move to ..." entry per OTHER game. "k=key" binds the current
        # loop value to the lambda (otherwise every entry would use the last key).
        for key, game in self.app.settings.games.items():
            if key == self.app.settings.active_game:
                continue
            menu.add_command(
                label=self.app.tr("ctx_move_to").format(game.name) + suffix,
                command=lambda k=key: self.move_selected(k),
            )
        menu.add_separator()
        menu.add_command(label=self.app.tr("btn_delete") + suffix, command=self.delete_selected)
        menu.post(event.x_root, event.y_root)

    # ==================================================================
    # Move / Delete / Export
    # ==================================================================
    def _selected_guids(self):
        """Return the GUID strings of all selected table rows (without the "!" marker).

        Reserved-range rows are left out (they are not database entries).
        """
        return [
            str(self.tree.item(item, "values")[0]).removesuffix(COLLISION_MARK)
            for item in self.tree.selection()
            if self.tree.item(item, "values") and item not in self._reserved_lists
        ]

    def copy_selected_guids(self):
        """Copy the selected database GUIDs to the clipboard, one per line."""
        guids = self._selected_guids()
        if not guids:
            return
        self.app.clipboard_clear()
        self.app.clipboard_append("\n".join(guids))

    def move_selected(self, target_key):
        """Move the selected GUIDs from the active game's database to ``target_key``.

        Steps:
          1. Ask for confirmation (Yes / No). The dialog also shows how many
             of the GUIDs lie outside the target game's OWN GUID range,
             because such GUIDs would normally never be registered there.
          2. Move the entries (existing entries in the target are merged).
          3. Save BOTH databases and refresh the table.
          4. Show a summary (moved / merged).
        """
        guids = self._selected_guids()
        if not guids:
            return

        tr = self.app.tr
        source = self.app.game
        target = self.app.settings.games[target_key]
        target_db = self.app.databases[target_key]

        outside = sum(1 for g in guids if not target.is_own_guid(g))
        body = tr("msg_confirm_move_body").format(len(guids), source.name, target.name)
        if outside:
            body += "\n\n" + tr("msg_move_outside_range").format(
                outside, target.name, target.own_ranges_text)

        if not messagebox.askyesno(tr("msg_confirm_move_title"), body, icon=messagebox.WARNING):
            return

        moved, merged = self.app.db.move_to(guids, target_db)
        self.app.db.save()
        target_db.save()
        self.refresh_view()

        messagebox.showinfo(tr("msg_move_done_title"),
                            tr("msg_move_done_body").format(target.name, moved, merged))

    def delete_selected(self):
        """Delete the selected GUIDs from the database after a confirmation."""
        guids = self._selected_guids()
        if not guids:
            return

        tr = self.app.tr
        if messagebox.askyesno(tr("msg_confirm_delete_title"),
                               tr("msg_confirm_delete_body").format(len(guids))):
            self.app.db.delete(guids)
            self.app.db.save()
            self.refresh_view()

    def export_to_csv(self):
        """Export the complete database (not only the filtered view) to CSV.

        Columns: GUID ; Location(s). Encoding ``utf-8-sig`` adds a BOM so
        Microsoft Excel detects UTF-8 correctly.
        """
        tr = self.app.tr
        if len(self.app.db) == 0:
            messagebox.showwarning(tr("msg_export_empty_title"), tr("msg_export_empty_body"))
            return

        # Suggest a file name containing the game, e.g. "guid_database_anno1800.csv"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"guid_database_{self.app.game.key}.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
            title="Export GUID database as CSV",
        )
        if not file_path:  # dialog cancelled
            return

        try:
            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file, delimiter=";")
                writer.writerow([tr("tree_guid"), tr("tree_comment"), tr("tree_loc")])
                for guid, comment, locations in self.app.db.sorted_items():
                    writer.writerow([guid, comment, ", ".join(locations)])
            messagebox.showinfo(tr("msg_export_success_title"), tr("msg_export_success_body"))
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    # ==================================================================
    # Import (register GUIDs of a mod)
    # ==================================================================
    def import_folder(self):
        """Let the user pick a mod FOLDER and register its GUIDs."""
        path = filedialog.askdirectory(title="Select mod folder")
        if path:
            self.register_path(path)

    def import_zip(self):
        """Let the user pick a mod ZIP archive and register its GUIDs."""
        path = filedialog.askopenfilename(
            title="Select mod file (.zip)",
            filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")],
        )
        if path:
            self.register_path(path)

    def register_path(self, path):
        """Register all OWN-range GUIDs of a mod folder or ZIP in the ACTIVE game's database.

        Shortcut for :meth:`register_paths` with a single mod. Also called by
        the "Replace Dummy GUIDs" tab after a replacement.
        """
        if path:
            self.register_paths([path])

    def register_paths(self, paths, header=""):
        """Register several mod folders / ZIPs and show ONE combined summary.

        Used by the buttons (one mod) and by drag & drop (one or more mods).
        Every mod is registered with :meth:`_register_one`; the counts of all
        mods are added up. Mods that cannot be read (e.g. corrupt ZIP) are
        skipped and listed in an error message after the summary.
        ``header`` is put in front of the summary text (e.g. by
        :meth:`migrate_collision`).
        """
        tr = self.app.tr
        totals = [0] * 7   # xml, new, comments found, changed, unchanged, skipped, names
        registered = 0
        accepted = 0
        migrated = []      # [(mod, old GUID, new GUID)]
        errors = []

        for path in paths:
            try:
                counts, mod_accepted, mod_migrated = self._register_one(path)
            except ImportCancelled:
                continue
            except Exception as e:  # e.g. corrupt ZIP archive
                errors.append(f"{path}\n{e}")
                continue
            totals = [t + c for t, c in zip(totals, counts)]
            accepted += mod_accepted
            migrated += mod_migrated
            registered += 1

        if registered:
            self.app.db.save()
            self.refresh_view()
            body = tr("msg_import_body").format(self.app.game.name, *totals)
            if len(paths) > 1:
                body = tr("msg_import_mods").format(registered) + "\n" + body
            if accepted or migrated:
                body += "\n\n" + tr("msg_import_collisions").format(accepted, len(migrated))
                body += "".join(f"\n  {old} → {new}   ({mod})" for mod, old, new in migrated)
            if header:
                body = header + "\n\n" + body
            messagebox.showinfo(tr("msg_import_title"), body)
        if errors:
            messagebox.showerror(tr("msg_err_zip"), "\n\n".join(errors))

    def _register_one(self, path):
        """Register one mod folder / ZIP in the active database (without saving).

        Steps:
          1. Scan every XML file and collect GUIDs that pass
             ``app.game.is_own_guid`` (numeric and inside the active game's
             own GUID range).
             At the same time, "GUID - comment" lines inside XML comments
             (``<!-- 2144009900 - Praefectus Name -->``) and fallback names
             (asset ``<Name>`` / text of texts_*.xml) are collected.
          2. Colliding GUIDs are shown in the collision dialog: GUIDs that
             the database lists for ANOTHER mod (or that two mods of this
             import define), GUIDs the mod defines more than once, and GUIDs
             reserved in the Free GUIDs list of another project. Per GUID:
             migrate (files rewritten, mod scanned again) or accept (see
             :meth:`_resolve_collisions`). Cancel stops this mod.
          3. Add each GUID with its file location(s) to the active database
             and store its comment, if one was found. A found comment
             overwrites the stored one (the mod is the current source);
             GUIDs without a comment in the mod keep their stored comment.
             Comment priority:
               1. "GUID - comment" line          -> always written
               2. asset <Name>                   -> only if no comment is stored
               3. text from texts_*.xml          -> only if no comment is stored

        :return: tuple ``(counts, accepted, migrated)``:
                 ``counts`` = ``(xml_count, new_guids, comments_found, changed,
                 unchanged, skipped, names_set)`` for the summary ("skipped"
                 = comment for a GUID that is not registered, e.g. outside the
                 own GUID range or not defined in a <GUID>/<LineId> tag),
                 ``accepted`` = number of accepted collisions,
                 ``migrated`` = ``[(mod, old GUID, new GUID)]``
        :raises ImportCancelled: if the user cancelled in the collision dialog
        :raises Exception: if the mod cannot be read (e.g. corrupt ZIP)
        """
        def scan():
            return scan_mod(path, self.app.game.is_own_guid, self.app.settings.comment_language)

        guid_files, comments, names, xml_count, duplicates = scan()

        accepted, migrated = [], []
        collisions = find_import_collisions(guid_files, self.app.db, duplicates, self.app.reservations)
        if collisions:
            accepted, migrated = self._resolve_collisions(path, collisions, guid_files)
            if migrated:  # files were rewritten -> read the new GUIDs
                guid_files, comments, names, xml_count, duplicates = scan()

        new_count = 0
        for guid, files in guid_files.items():
            for location in sorted(files):
                if self.app.db.add_location(guid, location):
                    new_count += 1

        # Comments: only for GUIDs registered by this import. For a GUID whose
        # collision with ANOTHER mod was accepted, the comment of the mod that
        # had it first is kept (it is only filled if empty).
        shared = {c.guid for c in accepted if c.owner_mods}
        changed = unchanged = skipped = 0
        for guid, comment in comments.items():
            if guid not in guid_files:
                skipped += 1
            elif guid in shared:
                if self.app.db.set_comment_if_empty(guid, comment):
                    changed += 1
                else:
                    unchanged += 1
            elif self.app.db.set_comment(guid, comment):
                changed += 1
            else:
                unchanged += 1

        # Fallback names: only for registered GUIDs WITHOUT a "GUID - comment"
        # line in this mod, and only if the database has no comment yet.
        names_set = 0
        for guid, name in names.items():
            if guid in comments:
                continue
            if self.app.db.set_comment_if_empty(guid, name):
                names_set += 1

        # Planning comments (typed in the Free GUIDs tab) for GUIDs that still
        # have no comment: neither a "GUID - comment" line nor a name.
        planning = self.app.reservations.planning_comments()
        for guid in guid_files:
            if guid in planning and self.app.db.set_comment_if_empty(guid, planning[guid]):
                names_set += 1

        # Duplicates inside a mod are recorded for every imported mod (and
        # removed again once the mod no longer has them).
        db = self.app.db
        for mod, guids in guids_by_mod(guid_files).items():
            for guid in guids:
                db.set_duplicate(guid, mod, mod in duplicates.get(guid, {}))

        # Accepted collisions are not reported again.
        self._apply_accepted(accepted)

        counts = (xml_count, new_count, len(comments), changed, unchanged, skipped, names_set)
        return counts, len(accepted), migrated

    def _apply_accepted(self, accepted):
        """Store the user's "accept" decisions (after the GUIDs were added).

        * other mod   -> the mods are stored in ``accepted_mods``
        * reserved    -> if the other project has NOT used the GUID yet, its
                         reservation is released (the GUID now belongs to the
                         imported mod); if it HAS used it, the conflict is
                         recorded in ``reserved_in`` and stays red while the
                         GUID is reserved there
        * duplicate   -> already recorded by ``set_duplicate``
        """
        db, res = self.app.db, self.app.reservations
        released = False
        for c in accepted:
            if c.owner_mods:
                db.accept_collision(c.guid, db.mods_of(c.guid))
            for name in c.reserved_in:
                items = res.lists.get(name, {})
                if c.guid in items and not items[c.guid]["used"]:
                    del items[c.guid]
                    released = True
                else:
                    db.add_reserved_conflict(c.guid, name)
        if released:
            res.save()

    def _resolve_collisions(self, path, collisions, guid_files):
        """Ask the user how to handle GUID collisions and migrate where requested.

        1. A free GUID is proposed for every (GUID, offending mod) pair:
           not in the database, not reserved in "Free GUIDs" and not used by
           the imported mod itself.
        2. :class:`CollisionDialog` lets the user choose per GUID.
        3. For "migrate", after a final "cannot be undone" confirmation,
           every standalone occurrence of the old GUID is replaced with the
           new one – but ONLY in the files of the offending mod (if the
           import contains several mods, the others stay untouched).

        :return: ``(accepted collisions, migrated)`` with
                 ``migrated`` = ``[(mod, old GUID, new GUID)]``
        :raises ImportCancelled: dialog or confirmation cancelled
        """
        tr = self.app.tr
        game = self.app.game
        label = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]

        pairs = [(c.guid, mod) for c in collisions if c.can_migrate for mod in c.offenders]
        taken = self.app.reservations.taken() | set(guid_files)
        if self.app.db.count_free(game.own_ranges, game.first_own_guid, taken) >= len(pairs):
            free = self.app.db.allocate(len(pairs), game.own_ranges, game.first_own_guid, taken)
            proposals = dict(zip(pairs, free))
        else:
            proposals = {}   # not enough free GUIDs: only "accept" is possible

        decisions = CollisionDialog(self.app, label, collisions, proposals).show()
        if decisions is None:
            raise ImportCancelled()

        accepted = [c for c in collisions if decisions[c.guid] == DECISION_ACCEPT]
        maps = {}   # offending mod -> {old GUID: new GUID}
        migrated = []
        for c in collisions:
            if decisions[c.guid] == DECISION_MIGRATE:
                for mod in c.offenders:
                    maps.setdefault(mod, {})[c.guid] = proposals[(c.guid, mod)]
                    migrated.append((mod, c.guid, proposals[(c.guid, mod)]))

        if maps:
            if not messagebox.askokcancel(
                tr("msg_confirm_replace_title"),
                tr("msg_col_confirm_migrate").format(len(migrated), ", ".join(sorted(maps))),
                icon=messagebox.WARNING, default=messagebox.CANCEL,
            ):
                raise ImportCancelled()

            def transform(text, location):
                mapping = maps.get(mod_of_location(location))
                return apply_dummy_map(text, mapping) if mapping else text

            rewrite_xml_files(path, transform)
        return accepted, migrated

    # ==================================================================
    # Migrate a mod of a colliding GUID (right-click menu)
    # ==================================================================
    def migrate_collision(self, guid):
        """Move one mod that defines the colliding ``guid`` to the next free GUID.

        1. :class:`MigrateDialog` shows the mods of the GUID (in import order,
           the last imported one pre-selected) and the proposed free GUID; the
           user picks the mod and whether it is a folder or a ZIP.
        2. The user selects that mod on disk. It must contain the mod and
           define ``guid`` there (the database only stores relative paths).
        3. After a "cannot be undone" confirmation, every standalone
           occurrence of ``guid`` is replaced in the files of THAT mod only,
           the mod's locations are removed from ``guid`` in the database, and
           the mod is registered again (new GUID with locations and comment,
           normal summary).

        Mods that define ``guid`` more than once themselves cannot be migrated.
        """
        tr = self.app.tr
        db, res, game = self.app.db, self.app.reservations, self.app.game
        entry = db.entries.get(guid)
        if entry is None:
            return
        mods = list(dict.fromkeys(m for m in map(mod_of_location, entry["locations"]) if m))
        if not mods:
            messagebox.showinfo(tr("mig_title"), tr("mig_err_no_mod").format(guid))
            return
        blocked = db.duplicate_in(guid)

        reasons = []
        if len(mods) > 1:
            reasons.append(tr("mig_reason_mods").format(", ".join(mods)))
        for mod in sorted(blocked):
            reasons.append(tr("mig_reason_duplicate").format(mod))
        still_reserved = [n for n in entry.get("reserved_in", []) if guid in res.lists.get(n, {})]
        if still_reserved:
            reasons.append(tr("col_reason_reserved").format(", ".join(still_reserved)))

        taken = res.taken()
        if db.count_free(game.own_ranges, game.first_own_guid, taken) < 1:
            messagebox.showerror(tr("mig_title"), tr("col_dlg_no_free"))
            return
        proposal = db.allocate(1, game.own_ranges, game.first_own_guid, taken)[0]

        default = next((m for m in reversed(mods) if m not in blocked), "")
        choice = MigrateDialog(self.app, guid, mods, default, blocked, proposal, reasons).show()
        if choice is None:
            return
        mod, source = choice

        if source == SOURCE_ZIP:
            path = filedialog.askopenfilename(
                title=tr("mig_pick").format(mod),
                filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")],
            )
        else:
            path = filedialog.askdirectory(title=tr("mig_pick").format(mod))
        if not path:
            return

        # The selected folder / ZIP must contain the mod and define the GUID there.
        try:
            guid_files = scan_mod(path, str.isdigit)[0]
        except Exception as e:
            messagebox.showerror(tr("msg_err_zip"), str(e))
            return
        if mod not in mods_of_locations(guid_files.get(guid, ())):
            messagebox.showerror(tr("mig_title"), tr("mig_err_not_found").format(guid, mod, path))
            return
        if proposal in guid_files:   # the mod folder already uses it (not registered yet)
            proposal = db.allocate(1, game.own_ranges, game.first_own_guid, taken | set(guid_files))[0]

        if not messagebox.askokcancel(
            tr("msg_confirm_replace_title"),
            tr("mig_confirm").format(guid, mod, proposal, path),
            icon=messagebox.WARNING, default=messagebox.CANCEL,
        ):
            return

        def transform(text, location):
            return apply_dummy_map(text, {guid: proposal}) if mod_of_location(location) == mod else text

        try:
            rewrite_xml_files(path, transform)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        db.remove_mod(guid, mod)
        db.save()
        self.register_paths([path], header=tr("mig_done").format(guid, proposal, mod))

        # If the old GUID still carries the comment of the migrated mod (now
        # on the new GUID), clear it: it does not describe the remaining
        # mod(s). Their comment is read again on their next registration.
        old, new = db.entries.get(guid), db.entries.get(proposal)
        if old and new and old["comment"] and old["comment"] == new["comment"]:
            old["comment"] = ""
            db.save()
        self.refresh_view()

    # ==================================================================
    # Check collisions (scan only, nothing is imported)
    # ==================================================================
    def check_collisions(self):
        """Scan a folder with mods for GUID collisions and show the report.

        Every numeric GUID is checked (not only the own ranges), so the work
        of other modders can be checked as well. The database is only read.
        """
        folder = filedialog.askdirectory(title=self.app.tr("dlg_check_collisions"))
        if not folder:
            return
        self.app.configure(cursor="watch")
        self.app.update_idletasks()
        try:
            result = scan_folder_collisions(folder, self.app.db, self.app.reservations)
        finally:
            self.app.configure(cursor="")
        CollisionReport(self.app, folder, result)
