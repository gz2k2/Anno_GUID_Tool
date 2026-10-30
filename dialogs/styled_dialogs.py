"""Application-wide CustomTkinter replacements for Tk message/input dialogs."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog

import customtkinter as ctk


class StyledDialog(ctk.CTkToplevel):
    """Small modal dialog with the application's common CTk layout."""

    def __init__(self, parent, title, message="", *, kind="info", input_value=None,
                 confirm=False, ok_cancel=False):
        super().__init__(parent)
        self.result = None
        self._input = None
        self.title(title or "")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(padx=22, pady=(20, 12), fill="both", expand=True)
        if message:
            color = {
                "error": ("#c92a2a", "#ff6b6b"),
                "warning": ("#b26a00", "#f0a43a"),
            }.get(kind)
            ctk.CTkLabel(
                body, text=message, justify="left", anchor="w",
                wraplength=520, text_color=color,
            ).pack(fill="x")

        if input_value is not None:
            self._input = ctk.CTkEntry(body, width=360)
            self._input.pack(fill="x", pady=(12 if message else 0, 0))
            self._input.insert(0, str(input_value))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(padx=22, pady=(0, 20), fill="x")

        if confirm or ok_cancel or input_value is not None:
            ctk.CTkButton(
                buttons, text="Cancel", width=90,
                fg_color="gray40", hover_color="gray30",
                command=self._cancel,
            ).pack(side="right")
            primary = "Yes" if confirm else "OK"
            ctk.CTkButton(
                buttons, text=primary, width=90, command=self._accept,
            ).pack(side="right", padx=(0, 8))
        else:
            ctk.CTkButton(
                buttons, text="OK", width=90, command=self._accept,
            ).pack(side="right")

        self.bind("<Escape>", lambda _event: self._cancel())
        self.bind("<Return>", lambda _event: self._accept())
        self.after(10, self._activate)

    def _activate(self):
        try:
            self.update_idletasks()
            parent = self.master
            if parent and parent.winfo_exists():
                x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
                y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
                self.geometry(f"+{x}+{y}")
            self.grab_set()
            if self._input is not None:
                self._input.focus_force()
                self._input.selection_range(0, tk.END)
            else:
                self.focus_force()
        except tk.TclError:
            pass

    def _accept(self):
        self.result = self._input.get() if self._input is not None else True
        self.destroy()

    def _cancel(self):
        self.result = None if self._input is not None else False
        self.destroy()

    def show(self):
        self.wait_window()
        return self.result


def _parent(kwargs):
    parent = kwargs.get("parent")
    if parent is not None:
        return parent
    return tk._default_root


def _show(kind, title, message, **kwargs):
    parent = _parent(kwargs)
    if parent is None:
        return "ok"
    StyledDialog(parent, title, message, kind=kind).show()
    return "ok"


def _ask_yes_no(title, message, **kwargs):
    parent = _parent(kwargs)
    return bool(parent and StyledDialog(parent, title, message, kind="warning", confirm=True).show())


def _ask_ok_cancel(title, message, **kwargs):
    parent = _parent(kwargs)
    return bool(parent and StyledDialog(parent, title, message, kind="warning", ok_cancel=True).show())


def _ask_string(title, prompt, **kwargs):
    parent = _parent(kwargs)
    if parent is None:
        return None
    initial = kwargs.get("initialvalue", "")
    return StyledDialog(parent, title, prompt, input_value=initial).show()


def install_styled_dialogs():
    """Replace Tk's generic message/input functions application-wide."""
    messagebox.showinfo = lambda title, message, **kw: _show("info", title, message, **kw)
    messagebox.showwarning = lambda title, message, **kw: _show("warning", title, message, **kw)
    messagebox.showerror = lambda title, message, **kw: _show("error", title, message, **kw)
    messagebox.askyesno = _ask_yes_no
    messagebox.askokcancel = _ask_ok_cancel
    simpledialog.askstring = _ask_string
