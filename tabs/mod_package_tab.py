"""UI for defining named mod packages from one or more inclusive GUID ranges."""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, simpledialog, ttk

import customtkinter as ctk


class ModPackageTab:
    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._build_ui()
        self.refresh_view()

    def _build_ui(self):
        project = ctk.CTkFrame(self.parent, fg_color="transparent")
        project.pack(padx=10, pady=(10, 0), fill="x")
        self.lbl_package = ctk.CTkLabel(project, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_package.pack(side="left", padx=(15, 5), pady=5)
        self.option_package = ctk.CTkOptionMenu(project, values=[""], command=self.select_package, width=220)
        self.option_package.pack(side="left", padx=5, pady=5)
        self.btn_new = ctk.CTkButton(project, text="", width=80, command=self.new_package)
        self.btn_new.pack(side="left", padx=5)
        self.btn_rename = ctk.CTkButton(project, text="", width=80, command=self.rename_package)
        self.btn_rename.pack(side="left", padx=5)
        self.btn_delete = ctk.CTkButton(project, text="", width=80, fg_color="#d9534f",
                                        hover_color="#c9302c", command=self.delete_package)
        self.btn_delete.pack(side="left", padx=5)

        ranges = ctk.CTkFrame(self.parent)
        ranges.pack(padx=10, pady=(8, 6), fill="x")
        self.lbl_start = ctk.CTkLabel(ranges, text="")
        self.lbl_start.pack(side="left", padx=(15, 5), pady=10)
        self.entry_start = ctk.CTkEntry(ranges, width=130)
        self.entry_start.pack(side="left", padx=5)
        self.lbl_end = ctk.CTkLabel(ranges, text="")
        self.lbl_end.pack(side="left", padx=(15, 5))
        self.entry_end = ctk.CTkEntry(ranges, width=130)
        self.entry_end.pack(side="left", padx=5)
        self.btn_add = ctk.CTkButton(ranges, text="+", width=38, command=self.add_range)
        self.btn_add.pack(side="left", padx=(15, 4))
        self.btn_remove = ctk.CTkButton(ranges, text="−", width=38, fg_color="#d9534f",
                                       hover_color="#c9302c", command=self.remove_range)
        self.btn_remove.pack(side="left", padx=4)

        container = ctk.CTkFrame(self.parent)
        container.pack(padx=10, pady=(0, 10), fill="both", expand=True)
        self.tree = ttk.Treeview(container, columns=("package", "range"), show="headings",
                                 selectmode="extended")
        self.tree.column("package", width=300, anchor="w")
        self.tree.column("range", width=300, anchor="w")
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(5, 0), pady=5)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=5)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

    def update_language(self):
        tr = self.app.tr
        self.lbl_package.configure(text=tr("pkg_label"))
        self.btn_new.configure(text=tr("res_btn_new_list"))
        self.btn_rename.configure(text=tr("res_btn_rename_list"))
        self.btn_delete.configure(text=tr("res_btn_delete_list"))
        self.lbl_start.configure(text=tr("pkg_guid_start"))
        self.lbl_end.configure(text=tr("pkg_guid_end"))
        self.tree.heading("package", text=tr("pkg_col_package"), anchor="w")
        self.tree.heading("range", text=tr("pkg_col_range"), anchor="w")

    def refresh_view(self):
        model = self.app.mod_packages
        names = model.names()
        self.option_package.configure(values=names or [""])
        if model.active not in names:
            model.active = names[0] if names else None
        self.option_package.set(model.active or "")
        self.tree.delete(*self.tree.get_children())
        if model.active:
            for index, (start, end) in enumerate(model.packages.get(model.active, [])):
                self.tree.insert("", "end", iid=f"{model.active}\0{index}",
                                 values=(model.active, f"{start} - {end}"))
        self._fit_columns_to_content()
        enabled = "normal" if model.active else "disabled"
        for widget in (self.btn_rename, self.btn_delete, self.btn_add, self.btn_remove,
                       self.entry_start, self.entry_end):
            widget.configure(state=enabled)

    def _fit_columns_to_content(self):
        """Resize Treeview columns to the widest heading or visible cell."""
        font = tkfont.nametofont("TkDefaultFont")
        heading_font = tkfont.nametofont("TkHeadingFont")
        padding = 28
        minimum = 120
        for column in ("package", "range"):
            heading = self.tree.heading(column, "text")
            width = heading_font.measure(heading) + padding
            for item in self.tree.get_children():
                width = max(width, font.measure(str(self.tree.set(item, column))) + padding)
            self.tree.column(column, width=max(minimum, width), stretch=False)

    def select_package(self, name):
        self.app.mod_packages.active = name or None
        self.app.mod_packages.save()
        self.refresh_view()

    def _ask_name(self, title_key, initial=""):
        return simpledialog.askstring(self.app.tr(title_key), self.app.tr("pkg_name_prompt"),
                                      initialvalue=initial, parent=self.app)

    def new_package(self):
        name = self._ask_name("pkg_new")
        if name is None:
            return
        if not self.app.mod_packages.add(name):
            messagebox.showerror(self.app.tr("pkg_error"), self.app.tr("pkg_name_invalid"))
            return
        self.app.mod_packages.save(); self.refresh_view(); self.app.database_tab.refresh_view()

    def rename_package(self):
        old = self.app.mod_packages.active
        if not old:
            return
        new = self._ask_name("pkg_rename", old)
        if new is None:
            return
        if not self.app.mod_packages.rename(old, new):
            messagebox.showerror(self.app.tr("pkg_error"), self.app.tr("pkg_name_invalid"))
            return
        self.app.mod_packages.save(); self.refresh_view(); self.app.database_tab.refresh_view()

    def delete_package(self):
        name = self.app.mod_packages.active
        if not name or not messagebox.askyesno(self.app.tr("pkg_delete"),
                                                self.app.tr("pkg_delete_confirm").format(name)):
            return
        self.app.mod_packages.delete(name)
        self.app.mod_packages.save(); self.refresh_view(); self.app.database_tab.refresh_view()

    def _read_range(self):
        try:
            start = int(self.entry_start.get().strip())
            end = int(self.entry_end.get().strip())
        except ValueError:
            return None
        return (start, end) if 0 <= start <= end else None

    def add_range(self):
        name = self.app.mod_packages.active
        values = self._read_range()
        if not name or values is None:
            messagebox.showerror(self.app.tr("pkg_error"), self.app.tr("pkg_range_invalid"))
            return
        start, end = values
        conflict = self.app.mod_packages.overlapping_package(start, end)
        if conflict:
            messagebox.showerror(self.app.tr("pkg_error"),
                                 self.app.tr("pkg_range_overlap").format(conflict))
            return
        self.app.mod_packages.add_range(name, start, end)
        self.app.mod_packages.save(); self.refresh_view(); self.app.database_tab.refresh_view()

    def show_context_menu(self, event):
        """Show a right-click menu for one or more selected GUID ranges."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        if item not in self.tree.selection():
            self.tree.selection_set(item)
        menu = tk.Menu(self.app, tearoff=0)
        menu.add_command(label="Remove", command=self.remove_range)
        menu.post(event.x_root, event.y_root)

    def remove_range(self):
        """Remove all selected ranges from the currently displayed Mod Package."""
        selection = self.tree.selection()
        if not selection:
            return
        grouped = {}
        for item in selection:
            name, index = item.split("\0", 1)
            grouped.setdefault(name, []).append(int(index))

        changed = False
        # Delete descending indices so earlier deletions cannot shift later rows.
        for name, indices in grouped.items():
            for index in sorted(set(indices), reverse=True):
                changed = self.app.mod_packages.remove_range(name, index) or changed
        if changed:
            self.app.mod_packages.save()
            self.refresh_view()
            self.app.database_tab.refresh_view()
