from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from .i18n import tr
from .items import EQUIPMENT_CATEGORIES, VENDORS, GameItem, category_display, category_from_display
from .project import ArcanaProject

CATEGORIES = ("Objet", "Arme", "Armure", "Bouclier", "Accessoire", "Carte")
CHARACTERS = ("Rooks", "Teefa", "Salah", "Darwin", "Axs")


class ItemDatabase(tk.Toplevel):
    def __init__(self, parent: tk.Misc, project: ArcanaProject, on_change: Callable[[], None]):
        super().__init__(parent)
        self.project = project
        self.on_change = on_change
        self.current_key: str | None = None
        self.search = tk.StringVar()
        self.category_filter = tk.StringVar(value=tr("All"))
        self.name = tk.StringVar()
        self.category = tk.StringVar(value=tr("Item"))
        self.item_id = tk.IntVar(value=1)
        self.description = tk.StringVar()
        self.price = tk.IntVar(value=0)
        self.resale = tk.IntVar(value=0)
        self.stats = {name: tk.IntVar(value=0) for name in ("attack", "defense", "magic_defense", "strength", "intelligence", "endurance", "agility")}
        self.stat_widgets: dict[str, ttk.Spinbox] = {}
        self.vendor_vars = {vendor: tk.BooleanVar(value=False) for vendor in VENDORS}
        self.character_vars = {character: tk.BooleanVar(value=False) for character in CHARACTERS}
        self.title(tr("Database — Items"))
        self.geometry("1050x700")
        self.minsize(900, 620)
        self.transient(parent)
        self._build()
        self._refresh_list()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self) -> None:
        header = tk.Frame(self, background="#35475a", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text=tr("DATABASE"), background="#35475a", foreground="#9dd3ff", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(header, text=tr("Items and equipment"), background="#35475a", foreground="#ffffff", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(body, padding=6)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=1)
        body.add(right, weight=2)
        filters = ttk.Frame(left)
        filters.pack(fill="x", pady=(0, 6))
        ttk.Entry(filters, textvariable=self.search).pack(side="left", fill="x", expand=True)
        ttk.Combobox(filters, textvariable=self.category_filter, values=(tr("All"),) + tuple(category_display(c) for c in CATEGORIES), state="readonly", width=13).pack(side="left", padx=(5, 0))
        self.search.trace_add("write", lambda *_: self._refresh_list())
        self.category_filter.trace_add("write", lambda *_: self._refresh_list())
        self.tree = ttk.Treeview(left, columns=("category", "id"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text=tr("Name"))
        self.tree.heading("category", text=tr("Category"))
        self.tree.heading("id", text="ID")
        self.tree.column("#0", width=180)
        self.tree.column("category", width=90)
        self.tree.column("id", width=45, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select_item)
        actions = ttk.Frame(left)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text=tr("New"), command=self._new_item).pack(side="left", fill="x", expand=True)
        ttk.Button(actions, text=tr("Duplicate"), command=self._duplicate_item).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(actions, text=tr("Delete"), command=self._delete_item).pack(side="left", fill="x", expand=True)
        self._build_form(right)
        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill="x")
        ttk.Label(footer, text=tr("Changes are saved to the project, available in chests and injected into the built ROM.")).pack(side="left")
        ttk.Button(footer, text=tr("Close"), command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text=tr("Save item"), command=self._save_item).pack(side="right")

    def _build_form(self, parent: ttk.Frame) -> None:
        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", expand=True)
        general = ttk.Frame(tabs, padding=14)
        stats = ttk.Frame(tabs, padding=14)
        vendors = ttk.Frame(tabs, padding=14)
        tabs.add(general, text=tr("General"))
        tabs.add(stats, text=tr("Statistics"))
        tabs.add(vendors, text=tr("Vendors"))
        labels = ((tr("Name"), self.name), (tr("Description"), self.description), (tr("Buy price"), self.price), (tr("Resale value"), self.resale))
        for row, (label, variable) in enumerate(labels):
            ttk.Label(general, text=label).grid(row=row * 2, column=0, sticky="w", pady=(4, 0))
            ttk.Entry(general, textvariable=variable).grid(row=row * 2 + 1, column=0, columnspan=2, sticky="ew", pady=(2, 7))
        ttk.Label(general, text=tr("Category")).grid(row=8, column=0, sticky="w")
        ttk.Label(general, text=tr("Identifier")).grid(row=8, column=1, sticky="w", padx=(8, 0))
        category = ttk.Combobox(general, textvariable=self.category, values=tuple(category_display(c) for c in CATEGORIES), state="readonly")
        category.grid(row=9, column=0, sticky="ew", pady=(2, 7))
        category.bind("<<ComboboxSelected>>", lambda _: self._category_changed())
        ttk.Spinbox(general, from_=1, to=255, textvariable=self.item_id).grid(row=9, column=1, sticky="ew", padx=(8, 0), pady=(2, 7))
        general.columnconfigure(0, weight=1)
        general.columnconfigure(1, weight=1)
        stat_labels = {
            "attack": tr("Attack"), "defense": tr("Defense"), "magic_defense": tr("Magic defense"),
            "strength": tr("Strength"), "intelligence": tr("Intelligence"), "endurance": tr("Endurance"), "agility": tr("Agility"),
        }
        for row, (key, label) in enumerate(stat_labels.items()):
            ttk.Label(stats, text=label).grid(row=row, column=0, sticky="w", pady=5)
            widget = ttk.Spinbox(stats, from_=-255, to=999, textvariable=self.stats[key])
            widget.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=5)
            self.stat_widgets[key] = widget
        ttk.Separator(stats).grid(row=7, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Label(stats, text=tr("Characters allowed to equip")).grid(row=8, column=0, columnspan=2, sticky="w")
        for row, (character, variable) in enumerate(self.character_vars.items(), 9):
            ttk.Checkbutton(stats, text=character, variable=variable).grid(row=row, column=0, columnspan=2, sticky="w")
        stats.columnconfigure(1, weight=1)
        ttk.Label(vendors, text=tr("Available from"), font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))
        for vendor, variable in self.vendor_vars.items():
            ttk.Checkbutton(vendors, text=vendor, variable=variable).pack(anchor="w", pady=4)
        ttk.Separator(vendors).pack(fill="x", pady=12)
        ttk.Label(vendors, text=tr("The buy price from the General tab will be used by the selected vendors. Inventories are rebuilt and injected when the ROM is built."), wraplength=470, justify="left").pack(anchor="w")

    def _refresh_list(self, select_key: str | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().strip().casefold()
        category = self.category_filter.get()
        for item in self.project.items:
            if item.category == "Monnaie" or query and query not in item.name.casefold() or category != tr("All") and item.category != category_from_display(category):
                continue
            self.tree.insert("", "end", iid=item.key, text=item.name, values=(category_display(item.category), f"${item.item_id:02X}"))
        target = select_key or self.current_key
        if target and self.tree.exists(target):
            self.tree.selection_set(target)
            self.tree.see(target)

    def _select_item(self, _: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item = next((candidate for candidate in self.project.items if candidate.key == selection[0]), None)
        if item:
            self._load_item(item)

    def _load_item(self, item: GameItem) -> None:
        self.current_key = item.key
        self.name.set(item.name)
        self.description.set(item.description)
        self.category.set(category_display(item.category))
        self.item_id.set(item.item_id)
        self.price.set(item.price)
        self.resale.set(item.resale_value)
        for key, variable in self.stats.items():
            variable.set(getattr(item, key))
        for name, variable in self.vendor_vars.items():
            variable.set(name in item.vendors)
        for name, variable in self.character_vars.items():
            variable.set(name in item.equippable_by)
        self._update_stat_controls()

    def _update_stat_controls(self) -> None:
        category = category_from_display(self.category.get())
        enabled = set()
        if category == "Arme":
            enabled = {"attack", "strength", "intelligence", "endurance", "agility"}
        elif category == "Armure":
            enabled = {"defense", "strength", "intelligence", "endurance", "agility"}
        elif category in {"Bouclier", "Accessoire"}:
            enabled = {"defense", "magic_defense", "strength", "intelligence", "endurance", "agility"}
        for key, widget in self.stat_widgets.items():
            widget.configure(state="normal" if key in enabled else "disabled")

    def _item_from_form(self, custom: bool | None = None) -> GameItem:
        original = next((item for item in self.project.items if item.key == self.current_key), None)
        return GameItem(
            category=category_from_display(self.category.get()), item_id=int(self.item_id.get()), name=self.name.get().strip(),
            description=self.description.get().strip(), price=max(0, int(self.price.get())), resale_value=max(0, int(self.resale.get())),
            attack=int(self.stats["attack"].get()), defense=int(self.stats["defense"].get()), magic_defense=int(self.stats["magic_defense"].get()),
            strength=int(self.stats["strength"].get()), intelligence=int(self.stats["intelligence"].get()), endurance=int(self.stats["endurance"].get()), agility=int(self.stats["agility"].get()),
            equippable_by=[name for name, variable in self.character_vars.items() if variable.get()],
            vendors=[name for name, variable in self.vendor_vars.items() if variable.get()],
            custom=custom if custom is not None else (original.custom if original else True),
        )

    def _save_item(self) -> None:
        try:
            item = self._item_from_form()
            self.project.save_item(item, self.current_key)
        except (ValueError, tk.TclError) as error:
            messagebox.showerror(tr("Invalid item"), str(error), parent=self)
            return
        self.current_key = item.key
        self._refresh_list(item.key)
        self.on_change()

    def _new_item(self) -> None:
        category = category_from_display(self.category_filter.get()) if category_from_display(self.category_filter.get()) in CATEGORIES else "Objet"
        item = GameItem(category, self.project.next_item_id(category), tr("New item"), custom=True)
        self.current_key = None
        self._load_item(item)
        self.current_key = None

    def _duplicate_item(self) -> None:
        selection = self.tree.selection()
        source = next((item for item in self.project.items if selection and item.key == selection[0]), None)
        if not source:
            return
        duplicate = source.clone(item_id=self.project.next_item_id(source.category), name=source.name + " — " + tr("copy"), custom=True)
        self.current_key = None
        self._load_item(duplicate)
        self.current_key = None

    def _delete_item(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        try:
            self.project.remove_custom_item(selection[0])
        except ValueError as error:
            messagebox.showinfo(tr("Cannot delete"), str(error), parent=self)
            return
        self.current_key = None
        self._refresh_list()
        self.on_change()

    def _category_changed(self) -> None:
        self._update_stat_controls()
        if self.current_key is None:
            try:
                self.item_id.set(self.project.next_item_id(category_from_display(self.category.get())))
            except ValueError:
                pass
