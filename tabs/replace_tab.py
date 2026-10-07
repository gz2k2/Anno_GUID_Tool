"""
replace_tab.py
==============

Tab "Replace Dummy GUIDs" – replaces placeholder (dummy) GUIDs in a mod
with real, unused GUIDs from the own GUID ranges of the ACTIVE game.
Every game can have several own ranges and several dummy ranges.

Everything in this tab refers to the game selected in the game selector:
its dummy ranges, its own ranges and its database (collision check). When
the game is switched, :meth:`ReplaceTab.on_game_changed` resets the start
GUID and re-scans the loaded mod with the new game's dummy ranges.

Workflow
--------
1. The user opens a mod folder or ZIP ("Open Folder" / "Open ZIP"), or
   drags it onto the window while this tab is shown (Windows).
2. The mod is scanned immediately; every GUID defined in a ``<GUID>`` or
   ``<LineId>`` tag that lies inside one of the DUMMY GUID ranges (Settings) is
   listed in the log together with the file(s) it is defined in.
3. "Assign & Replace Real GUIDs":
     a. determines the first real GUID to use
        - *Automatic* checked: first GUID of the own GUID ranges
        - otherwise: the value of the "Start GUID" field
     b. checks that enough free GUIDs exist before touching any file,
     c. asks for a final confirmation (OK / Cancel), because the files are
        overwritten directly and the operation cannot be undone,
     d. maps every dummy (sorted ascending) to the next free real GUID
        (GUIDs already in the database or reserved in the "Free GUIDs"
        tab are skipped; when an own range is
        full, assignment continues at the start of the next own range),
     e. replaces every standalone occurrence of each dummy in all XML
        files – definitions AND references,
     f. writes a log and offers to register the mod in the database.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from core.config_manager import in_ranges, parse_ranges
from core.xml_scanner import apply_dummy_map, collect_guids, rewrite_xml_files

#: Check box glyphs for replacement selection table.
BOX_UNCHECKED = "☐"
BOX_CHECKED = "☑"


class ReplaceTab:
    """Builds and controls the "Replace Dummy GUIDs" tab.

    :param app:    the main :class:`GUIDManagerApp`
    :param parent: the CTkTabview frame this tab is drawn into
    """

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        #: Currently loaded mod (folder path or ZIP file path), or None.
        self.working_path = None
        #: True once the app has activated drag & drop (changes the "no path" hint).
        self.drop_enabled = False
        #: Dict mapping dummy GUID -> set of file locations
        self.found_dummies = {}
        #: Set of dummy GUID strings selected by user for replacement
        self.selected_dummies = set()
        self._build_ui()

    # ==================================================================
    # UI construction
    # ==================================================================
    def _build_ui(self):
        """Create all widgets of the tab (grid layout + selection table + log textbox)."""
        game = self.app.game

        ctrl_frame = ctk.CTkFrame(self.parent)
        ctrl_frame.pack(padx=10, pady=10, fill="x")

        # Row 0: "Open Folder" / "Open ZIP" buttons + loaded path label
        btn_container = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_container.grid(row=0, column=0, padx=5, pady=10, sticky="w")

        self.btn_select_folder = ctk.CTkButton(btn_container, text="", width=120, command=self.load_folder)
        self.btn_select_folder.pack(side="left", padx=5)

        self.btn_select_zip = ctk.CTkButton(btn_container, text="", width=120, command=self.load_zip)
        self.btn_select_zip.pack(side="left", padx=5)

        self.lbl_mod_path = ctk.CTkLabel(ctrl_frame, text="", text_color="gray")
        self.lbl_mod_path.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Row 1: Dummy GUID range selection (Settings checkbox + custom entry field)
        self.lbl_dummy_range = ctk.CTkLabel(ctrl_frame, text="")
        self.lbl_dummy_range.grid(row=1, column=0, padx=10, pady=5, sticky="e")

        dummy_container = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        dummy_container.grid(row=1, column=1, columnspan=2, padx=0, pady=5, sticky="w")

        self.var_use_settings_dummy = tk.BooleanVar(value=self.app.settings.use_settings_dummy)
        self.chk_use_settings_dummy = ctk.CTkCheckBox(
            dummy_container, text="", variable=self.var_use_settings_dummy,
            command=self.on_use_settings_dummy_toggled,
        )
        self.chk_use_settings_dummy.pack(side="left", padx=(10, 10))

        self.entry_custom_dummy_range = ctk.CTkEntry(dummy_container, width=220)
        self.entry_custom_dummy_range.pack(side="left", padx=5)
        self.entry_custom_dummy_range.bind("<KeyRelease>", self._on_custom_dummy_edited)

        # Row 2: start GUID entry + own range info
        self.lbl_start = ctk.CTkLabel(ctrl_frame, text="")
        self.lbl_start.grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.entry_start_guid = ctk.CTkEntry(ctrl_frame, width=150)
        self.entry_start_guid.insert(0, str(game.first_own_guid))
        self.entry_start_guid.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        self.lbl_range_info = ctk.CTkLabel(ctrl_frame, text="", text_color="gray")
        self.lbl_range_info.grid(row=2, column=2, padx=10, pady=5, sticky="w")

        # Row 3: "Automatic" checkbox (state persisted in config.ini)
        self.var_auto_assign = tk.BooleanVar(value=self.app.settings.auto_assign)
        self.chk_automatic = ctk.CTkCheckBox(
            ctrl_frame, text="", variable=self.var_auto_assign,
            command=self.on_auto_assign_toggled,
        )
        self.chk_automatic.grid(row=3, column=1, columnspan=2, padx=10, pady=5, sticky="w")

        # Row 4: "Replace all non-own GUIDs" checkbox
        self.var_replace_non_own = tk.BooleanVar(value=self.app.settings.replace_non_own)
        self.chk_replace_non_own = ctk.CTkCheckBox(
            ctrl_frame, text="", variable=self.var_replace_non_own,
            command=self.on_replace_non_own_toggled,
        )
        self.chk_replace_non_own.grid(row=4, column=1, columnspan=2, padx=10, pady=5, sticky="w")

        # Row 5: main action button
        self.btn_replace = ctk.CTkButton(
            ctrl_frame, text="", fg_color="green", hover_color="darkgreen",
            command=self.replace_dummy_guids,
        )
        self.btn_replace.grid(row=5, column=1, padx=10, pady=15, sticky="w")

        # Apply initial enabled/disabled state of fields without writing config
        self.on_auto_assign_toggled(save=False)
        self.on_use_settings_dummy_toggled(save=False)
        self.on_replace_non_own_toggled(save=False)

        # --- Selection controls & Treeview for target GUIDs -------------
        table_bar = ctk.CTkFrame(self.parent, fg_color="transparent")
        table_bar.pack(padx=10, pady=(5, 2), fill="x")

        self.btn_select_all = ctk.CTkButton(table_bar, text="", width=110, command=self.select_all_dummies)
        self.btn_select_all.pack(side="left", padx=(5, 5))

        self.btn_deselect_all = ctk.CTkButton(table_bar, text="", width=110, command=self.deselect_all_dummies)
        self.btn_deselect_all.pack(side="left", padx=(0, 10))

        self.lbl_selected_stats = ctk.CTkLabel(table_bar, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_selected_stats.pack(side="left", padx=10)

        table_container = ctk.CTkFrame(self.parent)
        table_container.pack(padx=10, pady=(0, 5), fill="both", expand=True)

        self.tree = ttk.Treeview(
            table_container, columns=("replace", "guid", "files"),
            show="headings", selectmode="extended",
        )
        self.tree.column("replace", width=70, minwidth=60, anchor="center", stretch=False)
        self.tree.column("guid", width=140, minwidth=100, anchor="w", stretch=False)
        self.tree.column("files", width=500, minwidth=150, anchor="w", stretch=True)

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<space>", self._on_space_key)
        self.tree.bind("<Button-3>", self.show_context_menu)

        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=5)
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Log output (read-only except while the tool writes into it)
        self.txt_log = ctk.CTkTextbox(
            self.parent, height=120, font=ctk.CTkFont(family="Consolas", size=12), wrap="none",
        )
        self.txt_log.pack(padx=10, pady=(0, 10), fill="x")

    def update_language(self):
        """Set all texts of this tab according to the active UI language."""
        tr = self.app.tr
        self.btn_select_folder.configure(text=tr("btn_load_folder"))
        self.btn_select_zip.configure(text=tr("btn_load_zip"))
        if not self.working_path:
            self.lbl_mod_path.configure(text=tr("no_path_drop" if self.drop_enabled else "no_path"))
        self.lbl_dummy_range.configure(text=tr("lbl_dummy_range"))
        self.chk_use_settings_dummy.configure(text=tr("chk_use_settings_dummy"))
        self.lbl_start.configure(text=tr("lbl_start_guid"))
        self.chk_automatic.configure(text=tr("chk_automatic"))
        self.chk_replace_non_own.configure(text=tr("chk_replace_non_own"))
        self.btn_replace.configure(text=tr("btn_replace"))
        self.btn_select_all.configure(text=tr("btn_select_all"))
        self.btn_deselect_all.configure(text=tr("btn_deselect_all"))
        self.tree.heading("replace", text=tr("col_replace"), anchor="center")
        self.tree.heading("guid", text=tr("tree_guid"), anchor="w")
        self.tree.heading("files", text=tr("tree_loc"), anchor="w")
        self.update_range_info()
        self.update_selected_stats()

    def update_range_info(self):
        """Show the active game's own ranges and dummy ranges (from Settings) in this tab."""
        cfg = self.app.game
        self.lbl_range_info.configure(text=self.app.tr("lbl_range_info").format(cfg.own_ranges_text))
        if self.var_use_settings_dummy.get():
            self.entry_custom_dummy_range.configure(state="normal")
            self.entry_custom_dummy_range.delete(0, tk.END)
            self.entry_custom_dummy_range.insert(0, cfg.dummy_ranges_text)
            self.entry_custom_dummy_range.configure(state="disabled", text_color="gray")

    # ==================================================================
    # Callbacks from the Settings tab
    # ==================================================================
    def on_game_changed(self):
        """Called after another game was selected in the game selector.

        The start GUID is reset to the first GUID of the new game's own ranges, the range
        display is updated and the loaded mod (if any) is re-scanned with the
        new game's dummy range.
        """
        self._set_start_guid(self.app.game.first_own_guid)
        self.update_range_info()
        if self.working_path:
            self.scan_dummies()

    def on_ranges_changed(self):
        """Called after the GUID ranges of the ACTIVE game were saved in Settings.

        * Start GUID: if it is not a number or lies outside all own ranges,
          it is reset to the first GUID of the own ranges.
        * Range display is updated.
        * The loaded mod (if any) is re-scanned with the new dummy ranges.
        """
        cfg = self.app.game
        try:
            current = int(self.entry_start_guid.get().strip())
        except ValueError:
            current = None
        if current is None or not cfg.is_own_guid(str(current)):
            self._set_start_guid(cfg.first_own_guid)
        self._refresh_after_dummy_change()

    def _refresh_after_dummy_change(self):
        """Update the range display and re-scan the loaded mod (if any),
        so the dummy list reflects the new dummy ranges immediately."""
        self.update_range_info()
        if self.working_path:
            self.scan_dummies()

    # ==================================================================
    # Helpers
    # ==================================================================
    def _set_start_guid(self, value):
        """Write ``value`` into the start GUID entry, even if it is disabled."""
        previous_state = self.entry_start_guid.cget("state")
        self.entry_start_guid.configure(state="normal")
        self.entry_start_guid.delete(0, tk.END)
        self.entry_start_guid.insert(0, str(value))
        self.entry_start_guid.configure(state=previous_state)

    def _write_log(self, header, lines):
        """Replace the log content with ``header`` followed by ``lines``.

        The textbox is enabled only while writing so the user cannot edit it.
        """
        self.txt_log.configure(state="normal", wrap="none")
        self.txt_log.delete("1.0", tk.END)
        self.txt_log.insert(tk.END, header)
        for line in lines:
            self.txt_log.insert(tk.END, line)
        self.txt_log.configure(state="disabled")

    def _set_working_path(self, path):
        """Remember the loaded mod, show its path and scan it for dummies."""
        self.working_path = path
        self.lbl_mod_path.configure(text=path, text_color=("black", "white"))
        self.scan_dummies()

    def _collect_dummies(self):
        """Return ``{dummy_guid: {files...}}`` for all target GUIDs in the loaded mod."""
        if self.var_replace_non_own.get():
            predicate = lambda g: g.isdigit() and not self.app.game.is_own_guid(g)
        elif self.var_use_settings_dummy.get():
            predicate = self.app.game.is_dummy_guid
        else:
            custom_ranges = parse_ranges(self.entry_custom_dummy_range.get())
            predicate = lambda g: g.isdigit() and in_ranges(int(g), custom_ranges)
        guid_files, _ = collect_guids(self.working_path, predicate)
        return guid_files

    # ==================================================================
    # Load / Scan
    # ==================================================================
    def enable_drop_hint(self):
        """Mention drag & drop in the "no path loaded" label (called by the app)."""
        self.drop_enabled = True
        self.update_language()

    def handle_drop(self, mods):
        """Load a mod folder / ZIP dropped onto the window while this tab is shown.

        Only ONE mod can be loaded. If several were dropped, nothing is loaded,
        so the replacement can never run on a mod the user did not intend.
        """
        if len(mods) > 1:
            tr = self.app.tr
            messagebox.showwarning(tr("msg_drop_one_title"), tr("msg_drop_one_body").format(len(mods)))
            return
        self._set_working_path(mods[0])

    def load_folder(self):
        """Let the user pick a mod folder and scan it."""
        path = filedialog.askdirectory(title="Select mod folder")
        if path:
            self._set_working_path(path)

    def load_zip(self):
        """Let the user pick a mod ZIP archive and scan it."""
        path = filedialog.askopenfilename(
            title="Select mod file (.zip)",
            filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")],
        )
        if path:
            self._set_working_path(path)

    def scan_dummies(self):
        """List all dummy GUIDs of the loaded mod in the table and log (no changes made)."""
        if not self.working_path:
            return
        try:
            self.found_dummies = self._collect_dummies()
        except Exception as e:
            print(f"Error while scanning: {e}")
            self.found_dummies = {}

        # Default: select all found GUIDs for replacement
        self.selected_dummies = set(self.found_dummies.keys())
        self.refresh_tree()

        lines = [
            f" - {d:<15} ({', '.join(sorted(self.found_dummies[d]))})\n"
            for d in sorted(self.found_dummies, key=int)
        ]
        header_key = "found_non_own_guids" if self.var_replace_non_own.get() else "found_dummies"
        self._write_log(self.app.tr(header_key).format(len(self.found_dummies)), lines)

    # ==================================================================
    # Treeview & Selection helpers
    # ==================================================================
    def refresh_tree(self):
        """Rebuild all rows in the Treeview table from self.found_dummies."""
        self.tree.delete(*self.tree.get_children())
        for guid in sorted(self.found_dummies, key=int):
            files = self.found_dummies[guid]
            box = BOX_CHECKED if guid in self.selected_dummies else BOX_UNCHECKED
            files_text = ", ".join(sorted(files))
            self.tree.insert("", "end", iid=guid, values=(box, guid, files_text))
        self.update_selected_stats()

    def refresh_tree_row(self, guid):
        """Update values of a single row in Treeview."""
        if self.tree.exists(guid) and guid in self.found_dummies:
            box = BOX_CHECKED if guid in self.selected_dummies else BOX_UNCHECKED
            files_text = ", ".join(sorted(self.found_dummies[guid]))
            self.tree.item(guid, values=(box, guid, files_text))

    def update_selected_stats(self):
        """Update label showing how many GUIDs are selected."""
        total = len(self.found_dummies)
        selected = len(self.selected_dummies)
        self.lbl_selected_stats.configure(
            text=self.app.tr("lbl_guids_selected").format(selected, total)
        )

    def select_all_dummies(self):
        """Select all found GUIDs for replacement."""
        self.selected_dummies = set(self.found_dummies.keys())
        self.refresh_tree()

    def deselect_all_dummies(self):
        """Deselect all found GUIDs for replacement."""
        self.selected_dummies.clear()
        self.refresh_tree()

    def toggle_all_dummies(self):
        """Toggle all: if all selected -> deselect all, else select all."""
        if len(self.selected_dummies) == len(self.found_dummies):
            self.deselect_all_dummies()
        else:
            self.select_all_dummies()

    def _on_tree_click(self, event):
        """Click on column 1 (or heading 1) toggles replacement selection."""
        if self.tree.identify_region(event.x, event.y) == "heading":
            if self.tree.identify_column(event.x) == "#1":
                self.toggle_all_dummies()
                return "break"
            return None
        if self.tree.identify_region(event.x, event.y) != "cell":
            return None
        if self.tree.identify_column(event.x) != "#1":
            return None
        guid = self.tree.identify_row(event.y)
        if not guid:
            return "break"
        if guid in self.selected_dummies:
            self.selected_dummies.remove(guid)
        else:
            self.selected_dummies.add(guid)
        self.refresh_tree_row(guid)
        self.update_selected_stats()
        return "break"

    def set_dummies_selected(self, guids, selected):
        """Set replacement selection state for a list of GUIDs."""
        for guid in guids:
            if selected:
                self.selected_dummies.add(guid)
            else:
                self.selected_dummies.discard(guid)
            self.refresh_tree_row(guid)
        self.update_selected_stats()

    def show_context_menu(self, event):
        """Right-click menu: select / deselect highlighted rows for replacement."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        if item not in self.tree.selection():
            self.tree.selection_set(item)

        tr = self.app.tr
        selected_rows = list(self.tree.selection())
        suffix = f" ({len(selected_rows)})" if len(selected_rows) > 1 else ""

        menu = tk.Menu(self.app, tearoff=0)
        menu.add_command(
            label=tr("ctx_select_replace") + suffix,
            command=lambda: self.set_dummies_selected(selected_rows, True),
        )
        menu.add_command(
            label=tr("ctx_deselect_replace") + suffix,
            command=lambda: self.set_dummies_selected(selected_rows, False),
        )
        menu.add_separator()
        menu.add_command(label=tr("btn_select_all"), command=self.select_all_dummies)
        menu.add_command(label=tr("btn_deselect_all"), command=self.deselect_all_dummies)
        menu.post(event.x_root, event.y_root)

    def _on_space_key(self, event):
        """Space key toggles replacement selection for all highlighted rows."""
        selected_rows = self.tree.selection()
        if not selected_rows:
            return None
        all_checked = all(g in self.selected_dummies for g in selected_rows)
        for guid in selected_rows:
            if all_checked:
                self.selected_dummies.discard(guid)
            else:
                self.selected_dummies.add(guid)
            self.refresh_tree_row(guid)
        self.update_selected_stats()
        return "break"

    def on_use_settings_dummy_toggled(self, save=True):
        """Enable/disable custom dummy range field based on "Use settings dummy range"."""
        if save:
            self.app.settings.use_settings_dummy = bool(self.var_use_settings_dummy.get())
            self.app.settings.save()

        if self.var_use_settings_dummy.get():
            self.entry_custom_dummy_range.configure(state="normal")
            self.entry_custom_dummy_range.delete(0, tk.END)
            self.entry_custom_dummy_range.insert(0, self.app.game.dummy_ranges_text)
            self.entry_custom_dummy_range.configure(state="disabled", text_color="gray")
        else:
            self.entry_custom_dummy_range.configure(state="normal", text_color=("black", "white"))

        if self.working_path:
            self.scan_dummies()

    def _on_custom_dummy_edited(self, event=None):
        """Re-scan loaded mod when custom dummy range entry is edited."""
        if not self.var_use_settings_dummy.get() and self.working_path:
            self.scan_dummies()

    def on_auto_assign_toggled(self, save=True):
        """Enable/disable the start GUID field depending on "Automatic".

        * Automatic ON  -> field disabled (grey); assignment always starts at
          the beginning of the own range and fills all free gaps.
        * Automatic OFF -> field editable; assignment starts at its value.

        :param save: persist the checkbox state to config.ini (False during
                     initial UI construction).
        """
        if self.var_auto_assign.get():
            self.entry_start_guid.configure(state="disabled", text_color="gray")
        else:
            self.entry_start_guid.configure(state="normal", text_color=("black", "white"))
        if save:
            self.app.settings.auto_assign = bool(self.var_auto_assign.get())
            self.app.settings.save()

    def on_replace_non_own_toggled(self, save=True):
        """Callback when "Replace all GUIDs not in own ranges" checkbox is toggled."""
        if save:
            self.app.settings.replace_non_own = bool(self.var_replace_non_own.get())
            self.app.settings.save()

        if self.var_replace_non_own.get():
            self.chk_use_settings_dummy.configure(state="disabled")
            self.entry_custom_dummy_range.configure(state="disabled", text_color="gray")
        else:
            self.chk_use_settings_dummy.configure(state="normal")
            self.on_use_settings_dummy_toggled(save=False)

        if self.working_path:
            self.scan_dummies()

    # ==================================================================
    # Main action
    # ==================================================================
    def replace_dummy_guids(self):
        """Assign real GUIDs to all dummies of the loaded mod and rewrite its XML files.

        No file is modified if any validation fails (no mod loaded, invalid
        start GUID, start outside all own ranges, no dummies, not enough free GUIDs)
        or if the user cancels the final "cannot be undone" confirmation.
        """
        tr = self.app.tr
        cfg = self.app.game   # ranges of the active game
        db = self.app.db      # database of the active game

        if not self.working_path:
            messagebox.showwarning("Warning", tr("msg_warn_load_mod"))
            return

        # --- Step 1: determine the first real GUID -------------------
        auto_assign = bool(self.var_auto_assign.get())
        if auto_assign:
            start_guid = cfg.first_own_guid
        else:
            try:
                start_guid = int(self.entry_start_guid.get().strip())
            except ValueError:
                messagebox.showerror("Error", tr("msg_err_num"))
                return

        if not cfg.is_own_guid(str(start_guid)):
            messagebox.showerror("Error", tr("msg_err_start_outside").format(cfg.own_ranges_text))
            return

        # --- Step 2: collect dummies & filter to selected ones ----------
        try:
            all_found = self._collect_dummies()
        except Exception as e:
            messagebox.showerror(tr("msg_err_zip"), str(e))
            return

        if not all_found:
            if self.var_replace_non_own.get():
                messagebox.showinfo("Info", tr("msg_no_non_own_guids").format(cfg.own_ranges_text))
            elif self.var_use_settings_dummy.get():
                messagebox.showinfo("Info", tr("msg_no_dummies").format(cfg.dummy_ranges_text))
            else:
                dummy_text = self.entry_custom_dummy_range.get().strip() or "Custom"
                messagebox.showinfo("Info", tr("msg_no_dummies").format(dummy_text))
            return

        dummy_files = {g: files for g, files in all_found.items() if g in self.selected_dummies}
        if not dummy_files:
            messagebox.showinfo("Info", tr("msg_no_guids_selected"))
            return

        # --- Step 3: make sure the own ranges have enough free GUIDs ---
        # Counted over ALL own ranges, from the start GUID upwards. GUIDs
        # reserved in the "Free GUIDs" tab count as used.
        reserved = self.app.reservations.taken()
        free_count = db.count_free(cfg.own_ranges, start_guid, reserved)
        if free_count < len(dummy_files):
            messagebox.showerror(
                "Error",
                tr("msg_err_range_exhausted").format(cfg.own_ranges_text, len(dummy_files), free_count),
            )
            return

        # --- Step 4: final confirmation (OK / Cancel) ----------------
        # Shown only after all checks passed, so the user is asked only when
        # the replacement can actually run. "Cancel" is the default button to
        # protect against accidental Enter presses. Nothing has been changed yet.
        if not messagebox.askokcancel(
            tr("msg_confirm_replace_title"),
            tr("msg_confirm_replace_body").format(cfg.name, len(dummy_files)),
            icon=messagebox.WARNING,
            default=messagebox.CANCEL,
        ):
            return

        # --- Step 5: map dummies (ascending) to free real GUIDs -------
        sorted_dummies = sorted(dummy_files, key=int)
        # Continues automatically in the next own range when one is full.
        real_guids = db.allocate(len(sorted_dummies), cfg.own_ranges, start_guid, reserved)
        dummy_map = dict(zip(sorted_dummies, real_guids))

        # --- Step 6: rewrite all XML files -----------------------------
        try:
            rewrite_xml_files(self.working_path, lambda text, _location: apply_dummy_map(text, dummy_map))
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # Manual mode: move the start GUID behind the last assigned GUID so
        # the next run continues from there (only after a successful rewrite).
        if not auto_assign:
            # If the last GUID was the end of a range, jump to the next range.
            next_guid = cfg.next_own_guid(int(real_guids[-1]) + 1)
            self._set_start_guid(next_guid if next_guid is not None else int(real_guids[-1]) + 1)

        # --- Step 7: log + optional registration in the database ------
        lines = [
            f"Replaced: {dummy:<15} ---> {real:<12} ({', '.join(sorted(dummy_files[dummy]))})\n"
            for dummy, real in dummy_map.items()
        ]
        self._write_log(tr("replace_done"), lines)

        # Re-scan mod to update table
        self.scan_dummies()

        if messagebox.askyesno(tr("msg_ask_db_title"), tr("msg_ask_db_body").format(len(dummy_map), cfg.name)):
            self.app.database_tab.register_path(self.working_path)
