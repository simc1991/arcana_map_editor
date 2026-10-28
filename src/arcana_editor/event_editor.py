from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from .encounters import EncounterGroup
from .events import EVENT_TYPES, MapEvent, default_properties
from .items import GameItem
from .rom import MAP_HEIGHT, MAP_WIDTH


class EventEditor(tk.Toplevel):
    def __init__(self, parent: tk.Misc, event: MapEvent, on_save: Callable[[MapEvent, int, int], None], items: tuple[GameItem, ...] = (), encounter_groups: tuple[EncounterGroup, ...] = (), maps: tuple[tuple[int, str], ...] = ()):
        super().__init__(parent)
        self.event = event
        self.items = items
        self.encounter_groups = encounter_groups
        self.maps = maps
        self.item_by_display = {item.display: item for item in items}
        self.encounter_by_display = {group.display: group for group in encounter_groups}
        self.map_by_display = {f"${index:02X} — {name}": (index, name) for index, name in maps}
        self.original_x = event.x
        self.original_y = event.y
        self.on_save = on_save
        self.title(f"Éditeur d’événement — {event.display_name}")
        self.geometry("600x610")
        self.minsize(560, 560)
        self.transient(parent)
        self.grab_set()
        self.name = tk.StringVar(value=event.name)
        self.kind = tk.StringVar(value=event.kind)
        self.x = tk.IntVar(value=event.x)
        self.y = tk.IntVar(value=event.y)
        self.variant = tk.IntVar(value=event.value & 0x0F)
        self.property_vars: dict[str, tk.StringVar] = {}
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(50, self._center)

    def _build(self) -> None:
        header = tk.Frame(self, background="#35475a", padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="ÉVÉNEMENT", background="#35475a", foreground="#9dd3ff", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.header_title = tk.Label(header, text=self.event.display_name, background="#35475a", foreground="#ffffff", font=("Segoe UI", 18, "bold"))
        self.header_title.pack(anchor="w")
        self.header_subtitle = tk.Label(header, text=self.event.details, background="#35475a", foreground="#d9e3ec", font=("Segoe UI", 10))
        self.header_subtitle.pack(anchor="w", pady=(3, 0))
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=12, pady=12)
        general = ttk.Frame(tabs, padding=16)
        gameplay = ttk.Frame(tabs, padding=16)
        notes = ttk.Frame(tabs, padding=16)
        tabs.add(general, text="Général")
        tabs.add(gameplay, text="Gameplay")
        tabs.add(notes, text="Notes")
        self._build_general(general)
        self.gameplay = gameplay
        self._build_gameplay()
        ttk.Label(notes, text="Notes de conception").pack(anchor="w")
        self.notes = tk.Text(notes, wrap="word", height=15, font=("Segoe UI", 10))
        self.notes.pack(fill="both", expand=True, pady=(6, 0))
        self.notes.insert("1.0", self.event.notes)
        footer = ttk.Frame(self, padding=(12, 0, 12, 12))
        footer.pack(fill="x")
        ttk.Button(footer, text="Annuler", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Enregistrer l’événement", command=self._save).pack(side="right")
        ttk.Label(footer, text="Ctrl+Entrée pour enregistrer").pack(side="left")
        self.bind("<Control-Return>", lambda _: self._save())

    def _build_general(self, frame: ttk.Frame) -> None:
        ttk.Label(frame, text="Nom de l’événement").grid(row=0, column=0, columnspan=2, sticky="w")
        name_entry = ttk.Entry(frame, textvariable=self.name)
        name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 14))
        ttk.Label(frame, text="Type").grid(row=2, column=0, columnspan=2, sticky="w")
        kind_combo = ttk.Combobox(frame, textvariable=self.kind, values=list(EVENT_TYPES), state="readonly")
        kind_combo.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 14))
        kind_combo.bind("<<ComboboxSelected>>", lambda _: self._kind_changed())
        ttk.Label(frame, text="Position X").grid(row=4, column=0, sticky="w")
        ttk.Label(frame, text="Position Y").grid(row=4, column=1, sticky="w", padx=(12, 0))
        ttk.Spinbox(frame, from_=0, to=MAP_WIDTH - 1, textvariable=self.x, width=8).grid(row=5, column=0, sticky="ew", pady=(4, 14))
        ttk.Spinbox(frame, from_=0, to=MAP_HEIGHT - 1, textvariable=self.y, width=8).grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=(4, 14))
        ttk.Label(frame, text="Variante technique (0–15)").grid(row=6, column=0, columnspan=2, sticky="w")
        ttk.Spinbox(frame, from_=0, to=15, textvariable=self.variant).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        ttk.Label(frame, text="Le type et la variante déterminent la valeur enregistrée dans la carte. Les libellés techniques restent accessibles sans être obligatoires.", wraplength=490, justify="left").grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        name_entry.focus_set()

    def _build_gameplay(self) -> None:
        for child in self.gameplay.winfo_children():
            child.destroy()
        self.property_vars.clear()
        properties = dict(default_properties(EVENT_TYPES[self.kind.get()] | self.variant.get()))
        properties.update(self.event.properties)
        for technical_key in ("item_key", "item_id", "catégorie", "zone", "ennemis", "destination_map_index", "rom_source_treasure", "rom_source_stair", "destination_externe", "type_trésor"):
            properties.pop(technical_key, None)
        descriptions = {
            "groupe": "Groupe de rencontres",
            "fréquence": "Fréquence",
            "contenu": "Contenu du coffre",
            "quantité": "Quantité",
            "destination": "Carte ou étage de destination",
            "x_cible": "Position X cible",
            "y_cible": "Position Y cible",
            "direction": "Orientation à l’arrivée",
            "déclenchement": "Déclenchement",
            "condition": "Condition",
            "intensité": "Intensité",
        }
        if not properties:
            ttk.Label(self.gameplay, text="Ce type ne possède pas encore de propriétés supplémentaires.", wraplength=480).pack(anchor="w")
            return
        for key, value in properties.items():
            row = ttk.Frame(self.gameplay)
            row.pack(fill="x", pady=5)
            ttk.Label(row, text=descriptions.get(key, key.replace("_", " ").title()), width=27).pack(side="left")
            variable = tk.StringVar(value=str(value))
            self.property_vars[key] = variable
            if key == "groupe" and self.encounter_groups:
                try:
                    group_id = int(value)
                except (TypeError, ValueError):
                    group_id = self.event.value & 0x0F
                current = next((group.display for group in self.encounter_groups if group.group_id == group_id), self.encounter_groups[0].display)
                variable.set(current)
                ttk.Combobox(row, textvariable=variable, values=[group.display for group in self.encounter_groups], state="readonly").pack(side="left", fill="x", expand=True)
            elif key == "contenu" and self.items:
                current = next((item.display for item in self.items if item.name == str(value) or item.key == self.event.properties.get("item_key")), str(value))
                variable.set(current)
                ttk.Entry(row, textvariable=variable, state="readonly").pack(side="left", fill="x", expand=True)
                ttk.Button(row, text="Choisir…", command=lambda var=variable: self._open_item_picker(var)).pack(side="left", padx=(5, 0))
            elif key == "destination" and self.maps:
                stored_index = self.event.properties.get("destination_map_index")
                if stored_index == -1:
                    current = f"Sortie externe — {value}"
                    self.map_by_display[current] = (-1, str(value))
                else:
                    current = next((display for display, (index, name) in self.map_by_display.items() if index == stored_index or name == str(value)), next(iter(self.map_by_display)))
                variable.set(current)
                ttk.Combobox(row, textvariable=variable, values=list(self.map_by_display), state="readonly").pack(side="left", fill="x", expand=True)
            elif key == "direction":
                ttk.Combobox(row, textvariable=variable, values=("Nord", "Est", "Sud", "Ouest"), state="readonly").pack(side="left", fill="x", expand=True)
            elif key == "déclenchement":
                ttk.Combobox(row, textvariable=variable, values=("Contact joueur", "Interaction", "Entrée sur la carte", "Automatique"), state="readonly").pack(side="left", fill="x", expand=True)
            else:
                ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Separator(self.gameplay).pack(fill="x", pady=12)
        ttk.Label(self.gameplay, text="Ces propriétés sont conservées dans le projet. Les champs reliés aux tables ROM seront injectés lorsque le constructeur de ROM sera disponible.", wraplength=480, justify="left").pack(anchor="w")

    def _open_item_picker(self, variable: tk.StringVar) -> None:
        picker = tk.Toplevel(self)
        picker.title("Choisir le contenu du coffre")
        picker.geometry("680x520")
        picker.minsize(560, 420)
        picker.transient(self)
        picker.grab_set()
        search_value = tk.StringVar()
        category_value = tk.StringVar(value="Toutes les catégories")
        header = ttk.Frame(picker, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="Rechercher un objet", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        filters = ttk.Frame(header)
        filters.pack(fill="x", pady=(6, 0))
        search = ttk.Entry(filters, textvariable=search_value)
        search.pack(side="left", fill="x", expand=True)
        categories = ("Toutes les catégories", "Objet", "Arme", "Armure", "Bouclier", "Accessoire", "Carte", "Monnaie")
        category = ttk.Combobox(filters, textvariable=category_value, values=categories, state="readonly", width=20)
        category.pack(side="left", padx=(6, 0))
        columns = ("name", "category", "id")
        tree = ttk.Treeview(picker, columns=columns, show="headings", selectmode="browse")
        tree.heading("name", text="Nom de l’objet")
        tree.heading("category", text="Catégorie")
        tree.heading("id", text="ID")
        tree.column("name", width=350)
        tree.column("category", width=130)
        tree.column("id", width=60, anchor="center")
        tree.pack(fill="both", expand=True, padx=12)
        count = tk.StringVar()

        def refresh(*_: object) -> None:
            tree.delete(*tree.get_children())
            query = search_value.get().strip().casefold()
            selected_category = category_value.get()
            matches = [item for item in self.items if (not query or query in item.name.casefold()) and (selected_category == categories[0] or item.category == selected_category)]
            for item in matches:
                tree.insert("", "end", iid=item.key, values=(item.name, item.category, f"${item.item_id:02X}"))
            count.set(f"{len(matches)} objet(s) affiché(s) sur {len(self.items)}")
            current = self.item_by_display.get(variable.get())
            if current and tree.exists(current.key):
                tree.selection_set(current.key)
                tree.see(current.key)
            elif matches:
                tree.selection_set(matches[0].key)

        def choose() -> None:
            selection = tree.selection()
            if not selection:
                return
            item = next((candidate for candidate in self.items if candidate.key == selection[0]), None)
            if item:
                variable.set(item.display)
                picker.destroy()

        search_value.trace_add("write", refresh)
        category.bind("<<ComboboxSelected>>", refresh)
        tree.bind("<Double-1>", lambda _: choose())
        footer = ttk.Frame(picker, padding=12)
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=count).pack(side="left")
        ttk.Button(footer, text="Annuler", command=picker.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Choisir cet objet", command=choose).pack(side="right")
        refresh()
        search.focus_set()

    def _kind_changed(self) -> None:
        self.event = MapEvent(
            self.event.map_address,
            self.x.get(),
            self.y.get(),
            EVENT_TYPES[self.kind.get()] | self.variant.get(),
            self.name.get(),
            self.event.notes,
            {},
        )
        self._build_gameplay()
        self._refresh_header()

    def _refresh_header(self) -> None:
        value = EVENT_TYPES[self.kind.get()] | self.variant.get()
        preview = MapEvent(self.event.map_address, self.x.get(), self.y.get(), value, self.name.get())
        self.header_title.configure(text=preview.display_name)
        self.header_subtitle.configure(text=preview.details)

    def _save(self) -> None:
        try:
            x, y, variant = int(self.x.get()), int(self.y.get()), int(self.variant.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Événement invalide", "La position et la variante doivent être numériques.", parent=self)
            return
        if not 0 <= x < MAP_WIDTH or not 0 <= y < MAP_HEIGHT:
            messagebox.showerror("Événement invalide", "La position doit rester dans la carte 32 × 32.", parent=self)
            return
        if not 0 <= variant <= 15:
            messagebox.showerror("Événement invalide", "La variante doit être comprise entre 0 et 15.", parent=self)
            return
        properties: dict[str, str | int] = {}
        for key, variable in self.property_vars.items():
            value = variable.get().strip()
            properties[key] = int(value) if value.isdigit() else value
        for technical_key in ("rom_source_treasure", "rom_source_stair", "type_trésor"):
            if technical_key in self.event.properties:
                properties[technical_key] = self.event.properties[technical_key]
        if self.kind.get() in ("Escalier", "Transition") and self.maps:
            selected_map = self.map_by_display.get(str(properties.get("destination", "")))
            if not selected_map:
                messagebox.showerror("Destination invalide", "Sélectionnez une carte de destination existante.", parent=self)
                return
            properties["destination_map_index"] = selected_map[0]
            properties["destination"] = selected_map[1]
        if self.kind.get() in ("Rencontre", "Rencontre +") and self.encounter_groups:
            selected_group = self.encounter_by_display.get(str(properties.get("groupe", "")))
            if not selected_group:
                messagebox.showerror("Groupe invalide", "Sélectionnez un groupe de rencontres existant.", parent=self)
                return
            properties["groupe"] = selected_group.group_id
            variant = selected_group.group_id
            properties["zone"] = selected_group.zone
            properties["ennemis"] = list(selected_group.enemy_names)
        if self.kind.get() == "Coffre" and self.items:
            selected = self.item_by_display.get(str(properties.get("contenu", "")))
            if not selected:
                messagebox.showerror("Objet invalide", "Sélectionnez un objet existant dans la liste du jeu.", parent=self)
                return
            properties["contenu"] = selected.name
            properties["item_key"] = selected.key
            properties["item_id"] = selected.item_id
            properties["catégorie"] = selected.category
        updated = MapEvent(
            map_address=self.event.map_address,
            x=x,
            y=y,
            value=EVENT_TYPES[self.kind.get()] | variant,
            name=self.name.get().strip(),
            notes=self.notes.get("1.0", "end-1c").strip(),
            properties=properties,
        )
        self.on_save(updated, self.original_x, self.original_y)
        self.destroy()

    def _center(self) -> None:
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
