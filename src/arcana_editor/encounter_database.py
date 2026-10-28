from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from .encounters import EncounterGroup
from .project import ArcanaProject

MAX_GROUP_ID = 0x0F


class EncounterDatabase(tk.Toplevel):
    def __init__(self, parent: tk.Misc, project: ArcanaProject, on_change: Callable[[], None]):
        super().__init__(parent)
        self.project = project
        self.on_change = on_change
        self.current_key: tuple[int, int] | None = None
        self.chapter = tk.IntVar(value=1)
        self.zone = tk.IntVar(value=0)
        self.title("Base de données — Groupes de rencontres")
        self.geometry("900x600")
        self.minsize(760, 520)
        self.transient(parent)
        self._build()
        self._refresh_groups()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self) -> None:
        header = tk.Frame(self, background="#35475a", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="BASE DE DONNÉES", background="#35475a", foreground="#9dd3ff", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(header, text="Groupes de rencontres", background="#35475a", foreground="#ffffff", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(body, padding=6)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=1)
        body.add(right, weight=2)
        chapter_row = ttk.Frame(left)
        chapter_row.pack(fill="x", pady=(0, 6))
        ttk.Label(chapter_row, text="Chapitre").pack(side="left")
        chapter_box = ttk.Combobox(chapter_row, values=("1", "2", "3", "4", "5"), state="readonly", width=5)
        chapter_box.set("1")
        chapter_box.pack(side="left", padx=(6, 0))
        chapter_box.bind("<<ComboboxSelected>>", lambda _: self._chapter_changed(chapter_box.get()))
        self.tree = ttk.Treeview(left, columns=("zone", "enemies"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Groupe")
        self.tree.heading("zone", text="Zone")
        self.tree.heading("enemies", text="Ennemis")
        self.tree.column("#0", width=70)
        self.tree.column("zone", width=55, anchor="center")
        self.tree.column("enemies", width=220)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select_group)
        actions = ttk.Frame(left)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Nouveau groupe", command=self._new_group).pack(side="left", fill="x", expand=True)
        ttk.Button(actions, text="Restaurer", command=self._restore_group).pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Label(right, text="Zone de rencontre").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(right, from_=0, to=255, textvariable=self.zone, width=8).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(right, text="Ennemis du groupe (1 à 15, Ctrl+clic pour sélectionner)").grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 4))
        list_frame = ttk.Frame(right)
        list_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.enemy_list = tk.Listbox(list_frame, selectmode="multiple", exportselection=False, activestyle="none")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.enemy_list.yview)
        self.enemy_list.configure(yscrollcommand=scrollbar.set)
        self.enemy_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for index, name in enumerate(self.project.rom.enemy_names):
            self.enemy_list.insert("end", f"${index:02X} — {name}")
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)
        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill="x")
        ttk.Label(footer, text="Les groupes modifiés sont sauvegardés dans le projet et injectés lors de la construction du ROM.").pack(side="left")
        ttk.Button(footer, text="Fermer", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Enregistrer le groupe", command=self._save_group).pack(side="right")

    def _chapter_changed(self, value: str) -> None:
        self.chapter.set(int(value))
        self.current_key = None
        self._refresh_groups()

    def _refresh_groups(self, select: tuple[int, int] | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        chapter = self.chapter.get()
        for group in self.project.encounter_groups:
            if group.chapter != chapter:
                continue
            iid = f"{group.chapter}:{group.group_id}"
            enemies = ", ".join(group.enemy_names)
            self.tree.insert("", "end", iid=iid, text=f"#{group.group_id:X}", values=(f"${group.zone:02X}", enemies))
        target = select or self.current_key
        if target and self.tree.exists(f"{target[0]}:{target[1]}"):
            self.tree.selection_set(f"{target[0]}:{target[1]}")
            self.tree.see(f"{target[0]}:{target[1]}")

    def _select_group(self, _: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        chapter, group_id = (int(part) for part in selection[0].split(":"))
        group = next((candidate for candidate in self.project.encounter_groups if candidate.chapter == chapter and candidate.group_id == group_id), None)
        if group:
            self._load_group(group)

    def _load_group(self, group: EncounterGroup) -> None:
        self.current_key = (group.chapter, group.group_id)
        self.zone.set(group.zone)
        self.enemy_list.selection_clear(0, "end")
        for enemy_id in group.enemy_ids:
            if enemy_id < self.enemy_list.size():
                self.enemy_list.selection_set(enemy_id)

    def _new_group(self) -> None:
        chapter = self.chapter.get()
        used = {group.group_id for group in self.project.encounter_groups if group.chapter == chapter}
        free = next((group_id for group_id in range(MAX_GROUP_ID + 1) if group_id not in used), None)
        if free is None:
            messagebox.showinfo("Aucun emplacement", "Ce chapitre possède déjà 16 groupes.", parent=self)
            return
        self.current_key = None
        self.zone.set(0)
        self.enemy_list.selection_clear(0, "end")

    def _save_group(self) -> None:
        if self.current_key is None:
            chapter = self.chapter.get()
            used = {group.group_id for group in self.project.encounter_groups if group.chapter == chapter}
            group_id = next((candidate for candidate in range(MAX_GROUP_ID + 1) if candidate not in used), None)
            if group_id is None:
                messagebox.showerror("Aucun emplacement", "Ce chapitre possède déjà 16 groupes.", parent=self)
                return
        else:
            chapter, group_id = self.current_key
        enemy_ids = tuple(self.enemy_list.curselection())
        flags = next((group.flags for group in self.project.encounter_groups if group.chapter == chapter and group.group_id == group_id), 0)
        try:
            group = EncounterGroup(chapter, group_id, int(self.zone.get()), enemy_ids, (), flags)
            self.project.save_encounter_group(group)
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("Groupe invalide", str(error), parent=self)
            return
        self.current_key = (chapter, group_id)
        self._refresh_groups(self.current_key)
        self.on_change()

    def _restore_group(self) -> None:
        if self.current_key is None:
            return
        chapter, group_id = self.current_key
        self.project.remove_encounter_override(chapter, group_id)
        self._refresh_groups(self.current_key)
        self.on_change()
