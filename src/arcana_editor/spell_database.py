from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from .i18n import tr
from .project import ArcanaProject
from .spells import SPELL_NAME_COUNT, Spell


class SpellDatabase(tk.Toplevel):
    def __init__(self, parent: tk.Misc, project: ArcanaProject, on_change: Callable[[], None]):
        super().__init__(parent)
        self.project = project
        self.on_change = on_change
        self.current_key: str | None = None
        self.search = tk.StringVar()
        self.name = tk.StringVar()
        self.spell_id = tk.IntVar(value=0)
        self.accuracy = tk.IntVar(value=0)
        self.power = tk.IntVar(value=0)
        self.element = tk.IntVar(value=0)
        self.title(tr("Database — Spells"))
        self.geometry("760x620")
        self.minsize(680, 540)
        self.transient(parent)
        self._build()
        self._refresh_list()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self) -> None:
        header = tk.Frame(self, background="#35475a", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text=tr("DATABASE"), background="#35475a", foreground="#9dd3ff", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(header, text=tr("Spells"), background="#35475a", foreground="#ffffff", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(body, padding=6, width=280)
        left.pack_propagate(False)
        left.pack(side="left", fill="y")
        right = ttk.Frame(body, padding=14)
        right.pack(side="left", fill="both", expand=True)
        ttk.Entry(left, textvariable=self.search).pack(fill="x", pady=(0, 6))
        self.search.trace_add("write", lambda *_: self._refresh_list())
        self.tree = ttk.Treeview(left, columns=("id", "power"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text=tr("Name"))
        self.tree.heading("id", text="ID")
        self.tree.heading("power", text=tr("Power"))
        self.tree.column("#0", width=150)
        self.tree.column("id", width=45, anchor="center")
        self.tree.column("power", width=70, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select_spell)
        ttk.Label(right, text=tr("Name")).grid(row=0, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.name).grid(row=1, column=0, sticky="ew", pady=(2, 10))
        ttk.Label(right, text=tr("Identifier")).grid(row=2, column=0, sticky="w")
        ttk.Spinbox(right, from_=0, to=255, textvariable=self.spell_id, width=8, state="readonly").grid(row=3, column=0, sticky="w", pady=(2, 10))
        ttk.Label(right, text=tr("Accuracy (0–255)")).grid(row=4, column=0, sticky="w")
        ttk.Spinbox(right, from_=0, to=255, textvariable=self.accuracy, width=8).grid(row=5, column=0, sticky="w", pady=(2, 10))
        ttk.Label(right, text=tr("Power")).grid(row=6, column=0, sticky="w")
        ttk.Spinbox(right, from_=0, to=65535, textvariable=self.power, width=10).grid(row=7, column=0, sticky="w", pady=(2, 10))
        ttk.Label(right, text=tr("Element / affinity")).grid(row=8, column=0, sticky="w")
        ttk.Spinbox(right, from_=0, to=65535, textvariable=self.element, width=10).grid(row=9, column=0, sticky="w", pady=(2, 10))
        ttk.Label(right, text=tr("Only the first") + f" {SPELL_NAME_COUNT - 1} " + tr("spells have an injectable name in the ROM."), wraplength=360, justify="left").grid(row=10, column=0, sticky="w", pady=(8, 0))
        right.columnconfigure(0, weight=1)
        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill="x")
        ttk.Button(footer, text=tr("Close"), command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text=tr("Save spell"), command=self._save_spell).pack(side="right")

    def _refresh_list(self, select_key: str | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().strip().casefold()
        for spell in self.project.spells:
            if query and query not in spell.name.casefold():
                continue
            self.tree.insert("", "end", iid=spell.key, text=spell.name or tr("Spell") + f" ${spell.spell_id:02X}", values=(f"${spell.spell_id:02X}", spell.power))
        children = self.tree.get_children()
        target = select_key or self.current_key
        if target and self.tree.exists(target):
            self.tree.selection_set(target)
            self.tree.see(target)
        elif children:
            self.tree.selection_set(children[0])
            self.tree.see(children[0])

    def _select_spell(self, _: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        spell = next((candidate for candidate in self.project.spells if candidate.key == selection[0]), None)
        if spell:
            self.current_key = spell.key
            self.name.set(spell.name)
            self.spell_id.set(spell.spell_id)
            self.accuracy.set(spell.accuracy)
            self.power.set(spell.power)
            self.element.set(spell.element)

    def _save_spell(self) -> None:
        try:
            spell = Spell(
                int(self.spell_id.get()), self.name.get().strip(),
                accuracy=int(self.accuracy.get()), power=int(self.power.get()),
                element=int(self.element.get()),
            )
            self.project.save_spell(spell)
        except (ValueError, tk.TclError) as error:
            messagebox.showerror(tr("Invalid spell"), str(error), parent=self)
            return
        self._refresh_list(spell.key)
        self.on_change()
