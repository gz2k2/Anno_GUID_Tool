"""
reserve_tab.py
==============

Tab "Free GUIDs" – suggests a continuous block of free GUIDs for a mod that
is still being written, and keeps those GUIDs reserved until the finished
mod is imported into the database.

Reserved GUIDs are grouped in named lists, one per mod project ("Mod
project" drop-down with New / Rename / Delete). Everything below works on
the selected list; GUIDs reserved in ANY list are blocked for all of them.

Workflow
--------
1. The user enters how many GUIDs are needed and clicks "Suggest Free
   Block". The first continuous block of that size inside the OWN GUID
   ranges of the active game is reserved; GUIDs in the database and GUIDs
   that are already reserved are skipped.
2. While writing the mod, the user copies the GUIDs one by one
   ("Copy Next Free GUID", double-click or Ctrl+C) and marks them as used
   (click the ☐ box, or automatically when "Mark as used when copied" is on).
   Used GUIDs are shown struck through.
3. "Extend List" reserves more GUIDs directly after the last GUID of the
   list (or the next continuous free block after it, if those are taken).
4. When the mod is finished, it is imported in the "GUID Database" tab.
   Reserved GUIDs that are now in the database are shown as "registered"
   together with their database comment.
   A planning comment can be typed into the Comment column (double-click
   the cell, F2 or right-click → Edit comment). On import, the comment of
   the finished mod replaces it; if the mod has none, it is taken over.
5. "Clean Up" removes the registered GUIDs from the list and releases the
   unused ones. Used but not yet registered GUIDs stay reserved.
6. A finished project's list can be deleted; its GUIDs are released.

Reserved GUIDs (free AND used) are never suggested again and are also
skipped when the "Replace Dummy GUIDs" tab assigns real GUIDs.
The reservations are stored per game (see core/guid_reservations.py).
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

import customtkinter as ctk

from tabs.database_tab import TREE_FONT

#: Largest number of GUIDs that can be suggested / added in one step.
RESERVE_MAX_COUNT = 1000

#: Default value of the "Number of GUIDs" field.
RESERVE_DEFAULT_COUNT = 10

#: How long (ms) the "Copied: ..." / "Reserved: ..." feedback stays visible.
FEEDBACK_MS = 4000

#: Check box glyphs of the "Used" column.
BOX_UNCHECKED = "☐"
BOX_CHECKED = "☑"

# Row colors per state: (light mode, dark mode).
COLOR_USED = ("#8a8a8a", "#8a8a8a")
COLOR_REGISTERED = ("#2b8a3e", "#6fbf73")

# States of a reserved GUID (also used as Treeview tags).
STATE_FREE = "free"
STATE_USED = "used"
STATE_REGISTERED = "registered"


def guid_runs(guids):
    """Group numeric GUID strings into runs of consecutive numbers.

    Example: ``["100", "101", "102", "105"]`` -> ``"100 – 102, 105"``
    """
    numbers = sorted(int(g) for g in guids if g.isdigit())
    runs = []
    for number in numbers:
        if runs and number == runs[-1][1] + 1:
            runs[-1][1] = number
        else:
            runs.append([number, number])
    return ", ".join(f"{a} – {b}" if a != b else str(a) for a, b in runs)


class ReserveTab:
    """Builds and controls the "Free GUIDs" tab.

    :param app:    the main :class:`GUIDManagerApp` (gives access to
                   ``app.game``, ``app.db``, ``app.reservations``, ``app.tr`` …)
    :param parent: the CTkTabview frame this tab is drawn into
    """

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._feedback_job = None
        #: inline editor of the Comment column while it is open, else None
        self._editor = None
        self._build_ui()
        self.refresh_view()

    # ==================================================================
    # UI construction
    # ==================================================================
    def _build_ui(self):
        """Create all widgets: project row, two control rows, statistics bar, table and hint."""
        # --- Row 0: mod project (list) selection -----------------------
        project_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        project_frame.pack(padx=10, pady=(10, 0), fill="x")

        self.lbl_project = ctk.CTkLabel(project_frame, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_project.pack(side="left", padx=(15, 5), pady=5)

        self.opt_project = ctk.CTkOptionMenu(project_frame, values=[""], width=260,
                                             dynamic_resizing=False, command=self.select_list)
        self.opt_project.pack(side="left", padx=5, pady=5)

        self.btn_new_list = ctk.CTkButton(project_frame, text="", width=90, command=self.new_list)
        self.btn_new_list.pack(side="left", padx=5, pady=5)

        self.btn_rename_list = ctk.CTkButton(project_frame, text="", width=90, command=self.rename_list)
        self.btn_rename_list.pack(side="left", padx=5, pady=5)

        self.btn_delete_list = ctk.CTkButton(
            project_frame, text="", width=90, fg_color="#d9534f", hover_color="#c9302c",
            command=self.delete_list,
        )
        self.btn_delete_list.pack(side="left", padx=5, pady=5)

        # --- Row 1: optional custom start GUID -------------------------
        start_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        start_frame.pack(padx=10, pady=(5, 0), fill="x")

        self.var_use_own_start = tk.BooleanVar(value=False)
        self.chk_use_own_start = ctk.CTkCheckBox(
            start_frame, text="", variable=self.var_use_own_start,
            command=self._on_use_own_start_toggled,
        )
        self.chk_use_own_start.pack(side="left", padx=(15, 5), pady=5)
        self.entry_own_start = ctk.CTkEntry(start_frame, width=110)
        self.entry_own_start.bind("<Return>", lambda e: self.suggest_block())

        # --- Row 2: count + suggest / extend (left), copy next (right) -
        top_frame = ctk.CTkFrame(self.parent)
        top_frame.pack(padx=10, pady=(5, 0), fill="x")

        self.lbl_count = ctk.CTkLabel(top_frame, text="")
        self.lbl_count.pack(side="left", padx=(15, 5), pady=10)

        self.entry_count = ctk.CTkEntry(top_frame, width=70)
        self.entry_count.insert(0, str(RESERVE_DEFAULT_COUNT))
        self.entry_count.pack(side="left", padx=5, pady=10)
        self.entry_count.bind("<Return>", lambda e: self.suggest_block())

        self.btn_suggest = ctk.CTkButton(top_frame, text="", command=self.suggest_block)
        self.btn_suggest.pack(side="left", padx=5, pady=10)

        self.btn_extend = ctk.CTkButton(top_frame, text="", command=self.extend_list)
        self.btn_extend.pack(side="left", padx=5, pady=10)

        self.btn_copy_next = ctk.CTkButton(
            top_frame, text="", fg_color="#2b8a3e", hover_color="#216a2f",
            command=self.copy_next_free,
        )
        self.btn_copy_next.pack(side="right", padx=10, pady=10)

        # --- Row 2: options, clean up, own range info, feedback --------
        option_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        option_frame.pack(padx=10, pady=(5, 0), fill="x")

        self.var_mark_on_copy = tk.BooleanVar(value=self.app.settings.mark_used_on_copy)
        self.chk_mark_on_copy = ctk.CTkCheckBox(
            option_frame, text="", variable=self.var_mark_on_copy,
            command=self._on_mark_on_copy_toggled,
        )
        self.chk_mark_on_copy.pack(side="left", padx=(15, 10), pady=5)

        self.btn_cleanup = ctk.CTkButton(
            option_frame, text="", width=110, fg_color="#d9534f", hover_color="#c9302c",
            command=self.clean_up,
        )
        self.btn_cleanup.pack(side="left", padx=5, pady=5)

        self.lbl_range_info = ctk.CTkLabel(option_frame, text="", text_color="gray")
        self.lbl_range_info.pack(side="left", padx=15, pady=5)

        self.lbl_feedback = ctk.CTkLabel(option_frame, text="", text_color=COLOR_REGISTERED,
                                         font=ctk.CTkFont(weight="bold"))
        self.lbl_feedback.pack(side="right", padx=15, pady=5)

        # --- Statistics bar --------------------------------------------
        stats_frame = ctk.CTkFrame(self.parent)
        stats_frame.pack(padx=10, pady=(10, 5), fill="x")

        self.lbl_stats = ctk.CTkLabel(stats_frame, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_stats.pack(side="left", anchor="w", padx=15, pady=8)

        self.lbl_blocks = ctk.CTkLabel(stats_frame, text="", text_color="gray")
        self.lbl_blocks.pack(side="right", padx=15, pady=8)

        # --- Table of reserved GUIDs -----------------------------------
        table_container = ctk.CTkFrame(self.parent)
        table_container.pack(padx=10, pady=(0, 5), fill="both", expand=True)

        self.tree = ttk.Treeview(
            table_container, columns=("used", "guid", "status", "comment"),
            show="headings", selectmode="extended",
        )
        self.tree.column("used", width=70, minwidth=60, anchor="center", stretch=False)
        self.tree.column("guid", width=110, minwidth=90, anchor="w", stretch=False)
        self.tree.column("status", width=110, minwidth=80, anchor="w", stretch=False)
        self.tree.column("comment", width=400, minwidth=150, anchor="w", stretch=True)

        # Struck-through font for used / registered rows (a Treeview tag can
        # set its own font). Kept as attribute so it is not garbage-collected.
        self._strike_font = tkfont.Font(family=TREE_FONT[0], size=TREE_FONT[1], overstrike=1)

        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Control-c>", lambda e: self.copy_selected())
        self.tree.bind("<Control-a>", self.select_all)
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<F2>", lambda e: self.edit_comment())
        # Close the inline editor when the list scrolls or is resized.
        self.tree.bind("<MouseWheel>", lambda e: self._close_editor(save=True), add="+")
        self.tree.bind("<Configure>", lambda e: self._close_editor(save=True), add="+")

        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=5)
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # --- Usage hint below the table --------------------------------
        self.lbl_hint = ctk.CTkLabel(self.parent, text="", text_color="gray")
        self.lbl_hint.pack(padx=15, pady=(0, 8), anchor="w")

    def update_language(self):
        """Set all texts of this tab according to the active UI language."""
        tr = self.app.tr
        self.lbl_project.configure(text=tr("res_lbl_project"))
        self.btn_new_list.configure(text=tr("res_btn_new_list"))
        self.btn_rename_list.configure(text=tr("res_btn_rename_list"))
        self.btn_delete_list.configure(text=tr("res_btn_delete_list"))
        self.lbl_count.configure(text=tr("res_lbl_count"))
        self.chk_use_own_start.configure(text=tr("res_chk_use_own_start"))
        self.btn_suggest.configure(text=tr("res_btn_suggest"))
        self.btn_extend.configure(text=tr("res_btn_extend"))
        self.btn_copy_next.configure(text=tr("res_btn_copy_next"))
        self.chk_mark_on_copy.configure(text=tr("res_chk_mark_on_copy"))
        self.btn_cleanup.configure(text=tr("res_btn_cleanup"))
        self.lbl_hint.configure(text=tr("res_hint"))
        self.tree.heading("used", text=tr("res_col_used"), anchor="center")
        self.tree.heading("guid", text=tr("tree_guid"), anchor="w")
        self.tree.heading("status", text=tr("res_col_status"), anchor="w")
        self.tree.heading("comment", text=tr("tree_comment"), anchor="w")
        self.refresh_view()

    # ==================================================================
    # Table view
    # ==================================================================
    def _state(self, guid):
        """State of a reserved GUID: registered (in database) > used > free."""
        if guid in self.app.db:
            return STATE_REGISTERED
        return STATE_USED if self.app.reservations.is_used(guid) else STATE_FREE

    def _apply_tag_styles(self):
        """Colors / strike-through of the row states for the current appearance mode."""
        dark = 1 if ctk.get_appearance_mode() == "Dark" else 0
        self.tree.tag_configure(STATE_USED, foreground=COLOR_USED[dark], font=self._strike_font)
        self.tree.tag_configure(STATE_REGISTERED, foreground=COLOR_REGISTERED[dark], font=self._strike_font)

    def refresh_view(self):
        """Rebuild the table and the statistics from the reservations + database.

        An open comment editor is closed (and saved) first.

        The selection and the scroll position are kept, so toggling a GUID
        does not make the list jump.
        """
        if self._editor is not None:
            self._close_editor(save=True)
        tr = self.app.tr
        res = self.app.reservations
        selected = set(self._selected_guids())
        top = self.tree.yview()[0]

        self._apply_tag_styles()
        self.tree.delete(*self.tree.get_children())

        counts = {STATE_FREE: 0, STATE_USED: 0, STATE_REGISTERED: 0}
        for guid in res.sorted_guids():
            state = self._state(guid)
            counts[state] += 1
            box = BOX_UNCHECKED if state == STATE_FREE else BOX_CHECKED
            # Registered: the database comment (from the imported mod), else
            # the planning comment typed in here.
            comment = res.comment(guid)
            if state == STATE_REGISTERED:
                comment = self.app.db.entries[guid]["comment"] or comment
            self.tree.insert("", "end", iid=guid, tags=(state,),
                             values=(box, guid, tr(f"res_status_{state}"), comment))

        keep = [g for g in selected if self.tree.exists(g)]
        if keep:
            self.tree.selection_set(keep)
        self.tree.yview_moveto(top)

        # Project drop-down: all lists of the active game. Without any list,
        # a placeholder is shown and Rename / Delete are disabled (the first
        # "Suggest" creates a list automatically).
        names = res.list_names()
        self.opt_project.configure(values=names or [tr("res_no_list")])
        self.opt_project.set(res.active or tr("res_no_list"))
        state = "normal" if names else "disabled"
        self.btn_rename_list.configure(state=state)
        self.btn_delete_list.configure(state=state)

        self.lbl_stats.configure(text=tr("res_stats").format(
            self.app.game.name, len(res),
            counts[STATE_FREE], counts[STATE_USED], counts[STATE_REGISTERED],
        ))
        self.lbl_blocks.configure(text=tr("res_blocks").format(guid_runs(res.entries)) if len(res) else "")
        self.lbl_range_info.configure(text=tr("lbl_range_info").format(self.app.game.own_ranges_text))

    def _show_feedback(self, text):
        """Show a short confirmation next to the options (cleared after FEEDBACK_MS)."""
        if self._feedback_job:
            self.app.after_cancel(self._feedback_job)
        self.lbl_feedback.configure(text=text)
        self._feedback_job = self.app.after(FEEDBACK_MS, lambda: self.lbl_feedback.configure(text=""))

    # ==================================================================
    # Mod project lists
    # ==================================================================
    def select_list(self, name):
        """Drop-down callback: show the list ``name``."""
        res = self.app.reservations
        if name not in res.lists or name == res.active:
            return
        res.set_active(name)
        res.save()
        self.tree.selection_set(())
        self.refresh_view()
        self.tree.yview_moveto(0)

    def _ask_list_name(self, title_key, initial=""):
        """Ask for a list name; returns it, or None if cancelled / invalid.

        A name must not be empty and must not exist yet (case-insensitive,
        except for the list's own current name when renaming).
        """
        tr = self.app.tr
        dialog = ctk.CTkInputDialog(title=tr(title_key), text=tr("res_ask_list_name"))
        name = (dialog.get_input() or "").strip()
        if not name or name == initial:
            return None
        existing = {n.lower() for n in self.app.reservations.lists if n != initial}
        if name.lower() in existing:
            messagebox.showerror(tr(title_key), tr("msg_res_list_exists").format(name))
            return None
        return name

    def new_list(self):
        """Create a new, empty list for another mod project and select it."""
        name = self._ask_list_name("res_title_new_list")
        if name is None:
            return
        res = self.app.reservations
        res.add_list(name)
        res.save()
        self.refresh_view()

    def rename_list(self):
        """Rename the selected list (its GUIDs are kept)."""
        res = self.app.reservations
        old = res.active
        if old is None:
            return
        new = self._ask_list_name("res_title_rename_list", initial=old)
        if new is None:
            return
        res.rename_list(old, new)
        res.save()
        self.refresh_view()

    def delete_list(self):
        """Delete the selected list after a confirmation; its GUIDs are released.

        Warns separately about used GUIDs that are not registered yet: they
        may already be in a mod and could be suggested again afterwards.
        """
        res = self.app.reservations
        name = res.active
        if name is None:
            return
        tr = self.app.tr
        body = tr("msg_res_delete_list_body").format(name, len(res))
        used_open = sum(1 for g in res.sorted_guids() if self._state(g) == STATE_USED)
        if used_open:
            body += tr("msg_res_remove_used").format(used_open)
        if not messagebox.askyesno(tr("msg_res_delete_list_title"), body, icon=messagebox.WARNING):
            return
        res.delete_list(name)
        res.save()
        self.refresh_view()

    # ==================================================================
    # Suggest / Extend
    # ==================================================================
    def _on_use_own_start_toggled(self):
        """Show the custom start GUID field only while the option is enabled."""
        if self.var_use_own_start.get():
            self.entry_own_start.pack(side="left", padx=(0, 10), pady=5,
                                      after=self.chk_use_own_start)
            if not self.entry_own_start.get().strip():
                self.entry_own_start.insert(0, str(self.app.game.first_own_guid))
            self.entry_own_start.focus_set()
        else:
            self.entry_own_start.pack_forget()

    def _read_own_start_guid(self):
        """Return a validated custom start GUID, or None after showing an error."""
        value = self.entry_own_start.get().strip()
        try:
            start_guid = int(value)
        except ValueError:
            start_guid = -1
        if start_guid < 0 or not self.app.game.is_own_guid(str(start_guid)):
            tr = self.app.tr
            messagebox.showerror(tr("msg_res_err_start_title"),
                                 tr("msg_res_err_start").format(self.app.game.own_ranges_text))
            return None
        return start_guid

    def _read_count(self):
        """Number of GUIDs from the input field, or None (after an error message)."""
        try:
            count = int(self.entry_count.get().strip())
        except ValueError:
            count = 0
        if not 1 <= count <= RESERVE_MAX_COUNT:
            tr = self.app.tr
            messagebox.showerror(tr("msg_res_err_count_title"),
                                 tr("msg_res_err_count").format(RESERVE_MAX_COUNT))
            return None
        return count

    def _reserve_block(self, count, from_guid, no_block_text):
        """Find and reserve a continuous free block; show feedback or an error."""
        res = self.app.reservations
        if res.active is None:  # first use: create a list to put the GUIDs in
            res.add_list(self.app.tr("res_default_list"))
        block = self.app.db.find_free_block(count, self.app.game.own_ranges, from_guid, res.taken())
        if block is None:
            messagebox.showerror(self.app.tr("msg_res_no_block_title"), no_block_text)
            return
        res.add(block)
        res.save()
        self.refresh_view()
        self.tree.see(block[0])
        self._show_feedback(self.app.tr("res_feedback_added").format(guid_runs(block)))

    def suggest_block(self):
        """Reserve the FIRST continuous free block of the requested size.

        Searched from the start of the own GUID ranges, so gaps between
        registered GUIDs are used first. GUIDs reserved in ANY list are
        skipped. The block is added to the selected list.
        """
        count = self._read_count()
        if count is None:
            return
        game = self.app.game
        if self.var_use_own_start.get():
            start_guid = self._read_own_start_guid()
            if start_guid is None:
                return
            block = [str(guid) for guid in range(start_guid, start_guid + count)]
            end_guid = start_guid + count - 1
            if (not game.is_own_guid(str(end_guid))
                    or any(guid in self.app.db or guid in self.app.reservations.taken()
                           for guid in block)):
                messagebox.showerror(
                    self.app.tr("msg_res_start_collision_title"),
                    self.app.tr("msg_res_start_collision").format(start_guid, end_guid),
                )
                return
            res = self.app.reservations
            if res.active is None:
                res.add_list(self.app.tr("res_default_list"))
            res.add(block)
            res.save()
            self.refresh_view()
            self.tree.see(block[0])
            self._show_feedback(self.app.tr("res_feedback_added").format(guid_runs(block)))
            return

        self._reserve_block(count, game.first_own_guid,
                            self.app.tr("msg_res_no_block").format(count, game.own_ranges_text))

    def extend_list(self):
        """Reserve more GUIDs directly after the last GUID of the list.

        If the GUIDs right after the list are taken, the next continuous
        free block behind it is used. With an empty list this is the same
        as "Suggest Free Block".
        """
        last = self.app.reservations.last_guid()
        if last is None:
            self.suggest_block()
            return
        count = self._read_count()
        if count is None:
            return
        self._reserve_block(count, last + 1,
                            self.app.tr("msg_res_no_block_after").format(count, last))

    # ==================================================================
    # Copy / mark as used
    # ==================================================================
    def _copy_to_clipboard(self, guids):
        """Copy GUIDs (one per line) and mark them as used if the option is on."""
        if not guids:
            return
        self.app.clipboard_clear()
        self.app.clipboard_append("\n".join(guids))
        if self.var_mark_on_copy.get():
            res = self.app.reservations
            for guid in guids:
                res.set_used(guid, True)
            res.save()
            self.refresh_view()
        self._show_feedback(self.app.tr("res_feedback_copied").format(guid_runs(guids)))

    def copy_next_free(self):
        """Copy the lowest FREE reserved GUID (the next one to use in the mod)."""
        guid = next((g for g in self.app.reservations.sorted_guids()
                     if self._state(g) == STATE_FREE), None)
        if guid is None:
            tr = self.app.tr
            messagebox.showinfo(tr("msg_res_none_free_title"), tr("msg_res_none_free"))
            return
        self._copy_to_clipboard([guid])
        self.tree.selection_set(guid)
        self.tree.see(guid)

    def copy_selected(self):
        """Copy the selected GUIDs (Ctrl+C / context menu)."""
        self._copy_to_clipboard(self._selected_guids())
        return "break"

    def set_used(self, guids, used):
        """Mark ``guids`` as used / free (registered GUIDs are left unchanged)."""
        res = self.app.reservations
        for guid in guids:
            if guid not in self.app.db:
                res.set_used(guid, used)
        res.save()
        self.refresh_view()

    def _on_mark_on_copy_toggled(self):
        """Persist the "Mark as used when copied" checkbox."""
        self.app.settings.mark_used_on_copy = bool(self.var_mark_on_copy.get())
        self.app.settings.save()

    # ==================================================================
    # Mouse / keyboard
    # ==================================================================
    def _selected_guids(self):
        """GUIDs of all selected rows (the row id IS the GUID)."""
        return list(self.tree.selection())

    def _on_click(self, event):
        """A click on the ☐ / ☑ cell toggles "used" for that row."""
        if self.tree.identify_region(event.x, event.y) != "cell":
            return None
        if self.tree.identify_column(event.x) != "#1":
            return None
        guid = self.tree.identify_row(event.y)
        if not guid or guid in self.app.db:
            return "break"
        self.set_used([guid], not self.app.reservations.is_used(guid))
        return "break"

    def _on_double_click(self, event):
        """Double-click: Comment cell -> edit the comment; other cells -> copy the GUID."""
        column = self.tree.identify_column(event.x)
        guid = self.tree.identify_row(event.y)
        if column == "#1" or not guid:
            return "break"
        if column == "#4":
            self.edit_comment(guid)
        else:
            self._copy_to_clipboard([guid])
        return "break"

    # ==================================================================
    # Comment (inline editor)
    # ==================================================================
    def edit_comment(self, guid=None):
        """Open an inline editor over the Comment cell of ``guid`` (default: selection).

        Enter or leaving the field saves, Esc cancels. Free / used GUIDs get
        a planning comment (stored with the reservation); for registered
        GUIDs the database comment is edited.
        """
        if guid is None:
            selection = self.tree.selection()
            if not selection:
                return
            guid = selection[0]
            guids = list(selection)
        else:
            guids = [guid]
        self._close_editor(save=True)
        self.tree.see(guid)
        self.tree.update_idletasks()
        bbox = self.tree.bbox(guid, "comment")
        if not bbox:
            return
        x, y, width, height = bbox

        dark = ctk.get_appearance_mode() == "Dark"
        editor = tk.Entry(
            self.tree, font=TREE_FONT, relief="flat", borderwidth=1,
            bg="#2b2b2b" if dark else "#ffffff", fg="#ffffff" if dark else "#000000",
            insertbackground="#ffffff" if dark else "#000000",
            highlightthickness=1, highlightcolor="#1f538d",
        )
        editor.insert(0, self.tree.set(guid, "comment"))
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=width, height=height)
        # focus_force: the editor is only opened by the user's own double-click
        # / F2, and focus_set alone may leave the keys with the main window.
        editor.focus_force()
        editor.bind("<Return>", lambda e: self._close_editor(save=True))
        editor.bind("<KP_Enter>", lambda e: self._close_editor(save=True))
        editor.bind("<Escape>", lambda e: self._close_editor(save=False))
        editor.bind("<FocusOut>", lambda e: self._close_editor(save=True))
        self._editor = (editor, guids)

    def _close_editor(self, save):
        """Close the inline editor; store its text if ``save``."""
        if self._editor is None:
            return
        editor, guids = self._editor
        self._editor = None   # first, so FocusOut during destroy does nothing
        text = editor.get().strip()
        editor.destroy()
        if save:
            self.set_comments(guids, text)
        self.tree.focus_set()

    def set_comment(self, guid, text):
        """Store one comment; retained for callers that target a single GUID."""
        self.set_comments([guid], text)

    def set_comments(self, guids, text):
        """Apply the same comment to all selected reserved GUIDs."""
        text = text.strip()
        db_changed = False
        reservations_changed = False
        res = self.app.reservations
        for guid in guids:
            if guid in self.app.db:
                db_changed = self.app.db.set_comment(guid, text) or db_changed
            elif res.comment(guid) != text:
                res.set_comment(guid, text)
                reservations_changed = True
        if db_changed:
            self.app.db.save()
        if reservations_changed:
            res.save()
        if db_changed or reservations_changed:
            self.refresh_view()

    def select_all(self, event=None):
        """Select all rows (Ctrl+A)."""
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children)
        return "break"

    def show_context_menu(self, event):
        """Right-click menu: Copy / Mark as used / Mark as free / Remove from list."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        if item not in self.tree.selection():
            self.tree.selection_set(item)

        tr = self.app.tr
        guids = self._selected_guids()
        suffix = f" ({len(guids)})" if len(guids) > 1 else ""

        menu = tk.Menu(self.app, tearoff=0)
        menu.add_command(label=tr("res_ctx_copy") + suffix, command=self.copy_selected)
        menu.add_command(label=tr("res_ctx_edit_comment") + suffix, command=self.edit_comment)
        menu.add_command(label=tr("res_ctx_mark_used") + suffix,
                         command=lambda: self.set_used(guids, True))
        menu.add_command(label=tr("res_ctx_mark_free") + suffix,
                         command=lambda: self.set_used(guids, False))
        menu.add_separator()
        menu.add_command(label=tr("res_ctx_remove") + suffix, command=self.remove_selected)
        menu.post(event.x_root, event.y_root)

    # ==================================================================
    # Remove / Clean up
    # ==================================================================
    def remove_selected(self):
        """Remove the selected GUIDs from the list after a confirmation.

        Warns separately about used GUIDs that are not registered yet: they
        may already be in a mod and could be suggested again afterwards.
        """
        guids = self._selected_guids()
        if not guids:
            return
        tr = self.app.tr
        body = tr("msg_res_remove_body").format(len(guids))
        used_open = sum(1 for g in guids if self._state(g) == STATE_USED)
        if used_open:
            body += tr("msg_res_remove_used").format(used_open)
        if not messagebox.askyesno(tr("msg_res_remove_title"), body, icon=messagebox.WARNING):
            return
        res = self.app.reservations
        res.remove(guids)
        res.save()
        self.refresh_view()

    def clean_up(self):
        """Remove registered GUIDs and release unused ones (after a confirmation).

        Used but not yet registered GUIDs stay reserved: they are in a mod
        that has not been imported yet.
        """
        tr = self.app.tr
        res = self.app.reservations
        states = {g: self._state(g) for g in res.sorted_guids()}
        registered = [g for g, s in states.items() if s == STATE_REGISTERED]
        free = [g for g, s in states.items() if s == STATE_FREE]
        used_open = sum(1 for s in states.values() if s == STATE_USED)

        if not registered and not free:
            messagebox.showinfo(tr("msg_res_cleanup_title"),
                                tr("msg_res_cleanup_nothing").format(used_open))
            return
        if not messagebox.askyesno(
            tr("msg_res_cleanup_title"),
            tr("msg_res_cleanup_body").format(len(registered), len(free), used_open),
        ):
            return
        res.remove(registered + free)
        res.save()
        self.refresh_view()
