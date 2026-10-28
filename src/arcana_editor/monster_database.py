from __future__ import annotations

import base64
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .enemies import ELEMENTS, RACES, Enemy
from .project import ArcanaProject
from .sprites import build_enemy_tile_buffer, enemy_sprite_rgb

STAT_FIELDS = (
    ("hp", "PV"), ("level", "Niveau"), ("strength", "Force"), ("intelligence", "Intelligence"),
    ("endurance", "Endurance"), ("alertness", "Vigilance"), ("exp", "Expérience"), ("gp", "Or (GP)"),
)
COMBAT_FIELDS = (
    ("attack_animation", "Animation d’attaque"), ("equip_armor", "Armure équipée (def)"),
    ("equip_amulet", "Accessoire équipé (def)"), ("spell", "Sort (0 = aucun)"),
)


class MonsterDatabase(tk.Toplevel):
    def __init__(self, parent: tk.Misc, project: ArcanaProject, on_change: Callable[[], None]):
        super().__init__(parent)
        self.project = project
        self.on_change = on_change
        self.current_key: str | None = None
        self.search = tk.StringVar()
        self.name = tk.StringVar()
        self.enemy_id = tk.IntVar(value=0)
        self.sprite_b64 = ""
        self.sprite_image: tk.PhotoImage | None = None
        self._tile_buffer: dict | None = None
        self._rom_sprite = False
        self.stats = {key: tk.IntVar(value=0) for key, _ in STAT_FIELDS}
        self.combat = {key: tk.IntVar(value=0) for key, _ in COMBAT_FIELDS}
        self.race = tk.StringVar(value=RACES[0])
        self.element = tk.StringVar(value=ELEMENTS[0])
        self.title("Base de données — Monstres")
        self.geometry("980x680")
        self.minsize(840, 580)
        self.transient(parent)
        self._build()
        self._refresh_list()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self) -> None:
        header = tk.Frame(self, background="#35475a", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="BASE DE DONNÉES", background="#35475a", foreground="#9dd3ff", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(header, text="Monstres", background="#35475a", foreground="#ffffff", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(body, padding=6)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=1)
        body.add(right, weight=2)
        ttk.Entry(left, textvariable=self.search).pack(fill="x", pady=(0, 6))
        self.search.trace_add("write", lambda *_: self._refresh_list())
        self.tree = ttk.Treeview(left, columns=("id", "hp", "level"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Nom")
        self.tree.heading("id", text="ID")
        self.tree.heading("hp", text="PV")
        self.tree.heading("level", text="Niv")
        self.tree.column("#0", width=140)
        self.tree.column("id", width=45, anchor="center")
        self.tree.column("hp", width=60, anchor="center")
        self.tree.column("level", width=45, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select_enemy)
        actions = ttk.Frame(left)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Nouveau", command=self._new_enemy).pack(side="left", fill="x", expand=True)
        ttk.Button(actions, text="Dupliquer", command=self._duplicate_enemy).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(actions, text="Supprimer", command=self._delete_enemy).pack(side="left", fill="x", expand=True)
        self._build_form(right)
        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill="x")
        ttk.Label(footer, text="Les monstres sont sauvegardés dans le projet et injectés dans le ROM construit. L’image reste une donnée éditoriale du projet.").pack(side="left")
        ttk.Button(footer, text="Fermer", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Enregistrer le monstre", command=self._save_enemy).pack(side="right")

    def _build_form(self, parent: ttk.Frame) -> None:
        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", expand=True)
        general = ttk.Frame(tabs, padding=14)
        stats = ttk.Frame(tabs, padding=14)
        combat = ttk.Frame(tabs, padding=14)
        tabs.add(general, text="Général")
        tabs.add(stats, text="Statistiques")
        tabs.add(combat, text="Combat")
        ttk.Label(general, text="Nom").grid(row=0, column=0, sticky="w")
        ttk.Entry(general, textvariable=self.name).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        ttk.Label(general, text="Identifiant").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(general, from_=0, to=255, textvariable=self.enemy_id, width=8).grid(row=3, column=0, sticky="w", pady=(2, 8))
        sprite_box = ttk.LabelFrame(general, text="Image du monstre", padding=10)
        sprite_box.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        self.sprite_label = tk.Label(sprite_box, text="Aucune image", background="#1c2733", foreground="#9dd3ff", width=220, height=180)
        self.sprite_label.pack(fill="both", expand=True)
        sprite_buttons = ttk.Frame(sprite_box)
        sprite_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(sprite_buttons, text="Charger une image…", command=self._load_sprite).pack(side="left", fill="x", expand=True)
        ttk.Button(sprite_buttons, text="Retirer", command=self._clear_sprite).pack(side="left", padx=(4, 0))
        ttk.Label(general, text="Le sprite du ROM est affiché par défaut. Chargez un PNG ou GIF pour le remplacer dans le projet ; la conversion en tiles SNES est prévue pour une version ultérieure.", wraplength=360, justify="left").grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        general.columnconfigure(0, weight=1)
        for row, (key, label) in enumerate(STAT_FIELDS):
            ttk.Label(stats, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Spinbox(stats, from_=0, to=65535, textvariable=self.stats[key], width=10).grid(row=row, column=1, sticky="w", padx=(8, 0), pady=5)
        for row, (key, label) in enumerate(COMBAT_FIELDS):
            ttk.Label(combat, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Spinbox(combat, from_=0, to=65535, textvariable=self.combat[key], width=10).grid(row=row, column=1, sticky="w", padx=(8, 0), pady=5)
        ttk.Label(combat, text="Race").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Combobox(combat, textvariable=self.race, values=tuple(RACES.values()), state="readonly").grid(row=4, column=1, sticky="w", padx=(8, 0), pady=5)
        ttk.Label(combat, text="Élément").grid(row=5, column=0, sticky="w", pady=5)
        ttk.Combobox(combat, textvariable=self.element, values=tuple(ELEMENTS.values()), state="readonly").grid(row=5, column=1, sticky="w", padx=(8, 0), pady=5)

    def _refresh_list(self, select_key: str | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().strip().casefold()
        for enemy in self.project.enemies:
            if query and query not in enemy.name.casefold():
                continue
            self.tree.insert("", "end", iid=enemy.key, text=enemy.name, values=(f"${enemy.enemy_id:02X}", enemy.hp, enemy.level))
        target = select_key or self.current_key
        if target and self.tree.exists(target):
            self.tree.selection_set(target)
            self.tree.see(target)

    def _select_enemy(self, _: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        enemy = next((candidate for candidate in self.project.enemies if candidate.key == selection[0]), None)
        if enemy:
            self._load_enemy(enemy)

    def _load_enemy(self, enemy: Enemy) -> None:
        self.current_key = enemy.key
        self.name.set(enemy.name)
        self.enemy_id.set(enemy.enemy_id)
        for key, variable in self.stats.items():
            variable.set(getattr(enemy, key))
        for key, variable in self.combat.items():
            variable.set(getattr(enemy, key))
        self.race.set(RACES.get(enemy.race, f"Race ${enemy.race:02X}"))
        self.element.set(ELEMENTS.get(enemy.element, f"Élément ${enemy.element:02X}"))
        self._set_sprite(enemy.sprite)

    def _set_sprite(self, sprite_b64: str) -> None:
        self.sprite_b64 = sprite_b64
        self.sprite_image = None
        if sprite_b64:
            try:
                self.sprite_image = tk.PhotoImage(data=sprite_b64)
            except tk.TclError:
                self.sprite_image = None
        if self.sprite_image is None and self.current_key is not None:
            try:
                enemy_id = int(self.enemy_id.get())
            except (ValueError, tk.TclError):
                enemy_id = -1
            if 0 <= enemy_id < len(self.project.rom.enemies):
                if self._tile_buffer is None:
                    self._tile_buffer = build_enemy_tile_buffer(self.project.rom.data)
                ppm = enemy_sprite_rgb(self.project.rom.data, enemy_id, shared=self._tile_buffer)
                if ppm:
                    try:
                        self.sprite_image = tk.PhotoImage(data=ppm, format="PPM").zoom(2)
                        self._rom_sprite = True
                    except tk.TclError:
                        self.sprite_image = None
        if self.sprite_image:
            self.sprite_label.configure(image=self.sprite_image, text="")
        else:
            self.sprite_label.configure(image="", text="Aucune image")

    def _load_sprite(self) -> None:
        path = filedialog.askopenfilename(
            title="Charger une image de monstre",
            filetypes=(("Images", "*.png *.gif"), ("Tous les fichiers", "*.*")),
            parent=self,
        )
        if not path:
            return
        try:
            raw = open(path, "rb").read()
            encoded = base64.b64encode(raw).decode("ascii")
            tk.PhotoImage(data=encoded)
        except (OSError, tk.TclError) as error:
            messagebox.showerror("Image invalide", f"Impossible de charger cette image : {error}", parent=self)
            return
        self._set_sprite(encoded)

    def _clear_sprite(self) -> None:
        self._set_sprite("")

    def _enemy_from_form(self, custom: bool | None = None) -> Enemy:
        original = next((candidate for candidate in self.project.enemies if candidate.key == self.current_key), None)
        race = next((key for key, label in RACES.items() if label == self.race.get()), 0)
        element = next((key for key, label in ELEMENTS.items() if label == self.element.get()), 0)
        return Enemy(
            enemy_id=int(self.enemy_id.get()), name=self.name.get().strip(),
            hp=int(self.stats["hp"].get()), exp=int(self.stats["exp"].get()), gp=int(self.stats["gp"].get()),
            level=int(self.stats["level"].get()), strength=int(self.stats["strength"].get()),
            intelligence=int(self.stats["intelligence"].get()), endurance=int(self.stats["endurance"].get()),
            alertness=int(self.stats["alertness"].get()), race=race, element=element,
            attack_animation=int(self.combat["attack_animation"].get()),
            equip_armor=int(self.combat["equip_armor"].get()), equip_amulet=int(self.combat["equip_amulet"].get()),
            spell=int(self.combat["spell"].get()), sprite=self.sprite_b64,
            custom=custom if custom is not None else (original.custom if original else True),
        )

    def _save_enemy(self) -> None:
        try:
            enemy = self._enemy_from_form()
            self.project.save_enemy(enemy, self.current_key)
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("Monstre invalide", str(error), parent=self)
            return
        self.current_key = enemy.key
        self._refresh_list(enemy.key)
        self.on_change()

    def _new_enemy(self) -> None:
        try:
            enemy = Enemy(self.project.next_enemy_id(), "Nouveau monstre", custom=True)
        except ValueError as error:
            messagebox.showinfo("Aucun emplacement", str(error), parent=self)
            return
        self.current_key = None
        self._load_enemy(enemy)
        self.current_key = None

    def _duplicate_enemy(self) -> None:
        selection = self.tree.selection()
        source = next((candidate for candidate in self.project.enemies if selection and candidate.key == selection[0]), None)
        if not source:
            return
        try:
            duplicate = source.clone(enemy_id=self.project.next_enemy_id(), name=f"{source.name} — copie", custom=True)
        except ValueError as error:
            messagebox.showinfo("Aucun emplacement", str(error), parent=self)
            return
        self.current_key = None
        self._load_enemy(duplicate)
        self.current_key = None

    def _delete_enemy(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        try:
            self.project.remove_custom_enemy(selection[0])
        except ValueError as error:
            messagebox.showinfo("Suppression impossible", str(error), parent=self)
            return
        self.current_key = None
        self._refresh_list()
        self.on_change()
