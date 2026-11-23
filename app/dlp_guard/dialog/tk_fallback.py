"""Fallback desktop dialog (Tkinter) for when TaskDialog is unavailable."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .base import Confirmation


class TkDialog:
    def confirm(self, c: Confirmation) -> bool:
        result = {"ok": False}
        root = tk.Tk()
        root.title("DLP Guard")
        root.attributes("-topmost", True)
        root.resizable(False, False)
        frm = ttk.Frame(root, padding=16)
        frm.pack()
        ttk.Label(frm, text="Sensitive content detected", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            frm, wraplength=380, justify="left",
            text=f"The marker WALLED_SENSITIVE was found in {c.what} being sent to {c.site}.\n\n"
                 f"{c.label}: {c.name}",
        ).pack(anchor="w", pady=10)
        row = ttk.Frame(frm)
        row.pack(anchor="e")

        def done(ok: bool) -> None:
            result["ok"] = ok
            root.destroy()

        ttk.Button(row, text="Continue", command=lambda: done(True)).pack(side="left", padx=4)
        cancel = ttk.Button(row, text="Cancel", command=lambda: done(False))
        cancel.pack(side="left")
        cancel.focus_set()
        root.protocol("WM_DELETE_WINDOW", lambda: done(False))
        root.bind("<Escape>", lambda _e: done(False))
        root.lift()
        root.focus_force()
        root.mainloop()
        return result["ok"]
