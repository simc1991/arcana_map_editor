from __future__ import annotations

import base64
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .enemies import ELEMENTS, RACES, Enemy
from .i18n import tr
from .project import ArcanaProject
from .sprites import build_enemy_tile_buffer, enemy_sprite_rgb, image_to_enemy_tiles

STAT_FIELDS = (
    ("hp", tr("HP")), ("level", tr("Level")), ("strength", tr("Strength")), ("intelligence", tr("Intelligence")),
    ("endurance", tr("Endurance")), ("alertness", tr("Alertness")), ("exp", tr("Experience")), ("gp", tr("Gold (GP)")),
)
COMBAT_FIELDS = (
    ("attack_animation", tr("Attack animation")), ("equip_armor", tr("Equipped armor (def)")),
    ("equip_amulet", tr("Equipped amulet (def)")), ("spell", tr("Spell (0 = none)")),
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
        self._loaded_image: tk.PhotoImage | None = None
        self._sprite_tiles = ""
        self._sprite_palette = ""
        self._sprite_w = 0
        self._sprite_h = 0
        self.stats = {key: tk.IntVar(value=0) for key, _ in STAT_FIELDS}
        self.combat = {key: tk.IntVar(value=0) for key, _ in COMBAT_FIELDS}
        self.race = tk.StringVar(value=tr(RACES[0]))
        self.element = tk.StringVar(value=tr(ELEMENTS[0]))
        self.title(tr("Database — Monsters"))
        self.geometry("980x680")
        self.minsize(840, 580)
        self.transient(parent)
        self._build()
        self._refresh_list()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self) -> None:
        header = tk.Frame(self, background="#35475a", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text=tr("DATABASE"), background="#35475a", foreground="#9dd3ff", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(header, text=tr("Monsters"), background="#35475a", foreground="#ffffff", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=10)
        left = ttk.Frame(body, padding=6, width=300)
        left.pack_propagate(False)
        left.pack(side="left", fill="y")
        right = ttk.Frame(body, padding=8)
        right.pack(side="left", fill="both", expand=True)
        ttk.Entry(left, textvariable=self.search).pack(fill="x", pady=(0, 6))
        self.search.trace_add("write", lambda *_: self._refresh_list())
        self.tree = ttk.Treeview(left, columns=("id", "hp", "level"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text=tr("Name"))
        self.tree.heading("id", text="ID")
        self.tree.heading("hp", text=tr("HP"))
        self.tree.heading("level", text=tr("Lvl"))
        self.tree.column("#0", width=140)
        self.tree.column("id", width=45, anchor="center")
        self.tree.column("hp", width=60, anchor="center")
        self.tree.column("level", width=45, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select_enemy)
        actions = ttk.Frame(left)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text=tr("New"), command=self._new_enemy).pack(side="left", fill="x", expand=True)
        ttk.Button(actions, text=tr("Duplicate"), command=self._duplicate_enemy).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(actions, text=tr("Delete"), command=self._delete_enemy).pack(side="left", fill="x", expand=True)
        self._build_form(right)
        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill="x")
        ttk.Label(footer, text=tr("Monsters are saved to the project and injected into the built ROM. The image stays project-only editorial data.")).pack(side="left")
        ttk.Button(footer, text=tr("Close"), command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text=tr("Save monster"), command=self._save_enemy).pack(side="right")

    def _build_form(self, parent: ttk.Frame) -> None:
        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", expand=True)
        general = ttk.Frame(tabs, padding=14)
        stats = ttk.Frame(tabs, padding=14)
        combat = ttk.Frame(tabs, padding=14)
        tabs.add(general, text=tr("General"))
        tabs.add(stats, text=tr("Statistics"))
        tabs.add(combat, text=tr("Combat"))
        ttk.Label(general, text=tr("Name")).grid(row=0, column=0, sticky="w")
        ttk.Entry(general, textvariable=self.name).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        ttk.Label(general, text=tr("Identifier")).grid(row=2, column=0, sticky="w")
        ttk.Spinbox(general, from_=0, to=255, textvariable=self.enemy_id, width=8).grid(row=3, column=0, sticky="w", pady=(2, 8))
        sprite_box = ttk.LabelFrame(general, text=tr("Monster image"), padding=10)
        sprite_box.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        self.sprite_label = tk.Label(sprite_box, text=tr("No image"), background="#1c2733", foreground="#9dd3ff", width=220, height=180)
        self.sprite_label.pack(fill="both", expand=True)
        sprite_buttons = ttk.Frame(sprite_box)
        sprite_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(sprite_buttons, text=tr("Load an image…"), command=self._load_sprite).pack(side="left", fill="x", expand=True)
        ttk.Button(sprite_buttons, text=tr("Convert → ROM"), command=self._convert_sprite).pack(side="left", padx=4)
        ttk.Button(sprite_buttons, text=tr("Remove"), command=self._clear_sprite).pack(side="left")
        ttk.Label(general, text=tr("The ROM sprite is shown by default. Load a PNG or GIF then \"Convert → ROM\" to inject it into the built ROM (max 16 colors)."), wraplength=360, justify="left").grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        general.columnconfigure(0, weight=1)
        for row, (key, label) in enumerate(STAT_FIELDS):
            ttk.Label(stats, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Spinbox(stats, from_=0, to=65535, textvariable=self.stats[key], width=10).grid(row=row, column=1, sticky="w", padx=(8, 0), pady=5)
        for row, (key, label) in enumerate(COMBAT_FIELDS):
            ttk.Label(combat, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Spinbox(combat, from_=0, to=65535, textvariable=self.combat[key], width=10).grid(row=row, column=1, sticky="w", padx=(8, 0), pady=5)
        ttk.Label(combat, text=tr("Race")).grid(row=4, column=0, sticky="w", pady=5)
        ttk.Combobox(combat, textvariable=self.race, values=tuple(tr(v) for v in RACES.values()), state="readonly").grid(row=4, column=1, sticky="w", padx=(8, 0), pady=5)
        ttk.Label(combat, text=tr("Element")).grid(row=5, column=0, sticky="w", pady=5)
        ttk.Combobox(combat, textvariable=self.element, values=tuple(tr(v) for v in ELEMENTS.values()), state="readonly").grid(row=5, column=1, sticky="w", padx=(8, 0), pady=5)

    def _refresh_list(self, select_key: str | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().strip().casefold()
        for enemy in self.project.enemies:
            if query and query not in enemy.name.casefold():
                continue
            self.tree.insert("", "end", iid=enemy.key, text=enemy.name, values=(f"${enemy.enemy_id:02X}", enemy.hp, enemy.level))
        children = self.tree.get_children()
        target = select_key or self.current_key
        if target and self.tree.exists(target):
            self.tree.selection_set(target)
            self.tree.see(target)
        elif children:
            self.tree.selection_set(children[0])
            self.tree.see(children[0])

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
        self.race.set(tr(RACES.get(enemy.race, tr("Race") + f" ${enemy.race:02X}")))
        self.element.set(tr(ELEMENTS.get(enemy.element, tr("Element") + f" ${enemy.element:02X}")))
        self._set_sprite(enemy.sprite)
        self._sprite_tiles = enemy.sprite_tiles
        self._sprite_palette = enemy.sprite_palette
        self._sprite_w = enemy.sprite_w
        self._sprite_h = enemy.sprite_h

    def _set_sprite(self, sprite_b64: str) -> None:
        self.sprite_b64 = sprite_b64
        self.sprite_image = None
        self._loaded_image = None
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
            self.sprite_label.configure(image="", text=tr("No image"))

    def _load_sprite(self) -> None:
        path = filedialog.askopenfilename(
            title=tr("Load a monster image"),
            filetypes=((tr("Images"), "*.png *.gif"), (tr("All files"), "*.*")),
            parent=self,
        )
        if not path:
            return
        try:
            raw = open(path, "rb").read()
            encoded = base64.b64encode(raw).decode("ascii")
            self._loaded_image = tk.PhotoImage(data=encoded)
        except (OSError, tk.TclError) as error:
            messagebox.showerror(tr("Invalid image"), tr("Cannot load this image:") + f" {error}", parent=self)
            return
        self._set_sprite(encoded)

    def _convert_sprite(self) -> None:
        if self._loaded_image is None:
            messagebox.showinfo(tr("No image"), tr("Load a PNG or GIF image first."), parent=self)
            return
        try:
            tiles, palette, width, height = image_to_enemy_tiles(self._loaded_image)
        except (tk.TclError, ValueError) as error:
            messagebox.showerror(tr("Conversion failed"), str(error), parent=self)
            return
        self._sprite_tiles = tiles.hex()
        self._sprite_palette = b"".join(int(value).to_bytes(2, "little") for value in palette).hex()
        self._sprite_w = width
        self._sprite_h = height
        messagebox.showinfo(
            tr("Conversion complete"),
            tr("Image converted to") + f" {len(tiles) // 32} " + tr("SNES tiles") + f" ({width}×{height} px, {sum(1 for c in palette if c)} " + tr("colors") + ").\n" + tr("Save the monster then build the ROM to inject it."),
            parent=self,
        )

    def _clear_sprite(self) -> None:
        self._set_sprite("")
        self._sprite_tiles = ""
        self._sprite_palette = ""
        self._sprite_w = 0
        self._sprite_h = 0

    def _enemy_from_form(self, custom: bool | None = None) -> Enemy:
        original = next((candidate for candidate in self.project.enemies if candidate.key == self.current_key), None)
        race = next((key for key, label in RACES.items() if tr(label) == self.race.get()), 0)
        element = next((key for key, label in ELEMENTS.items() if tr(label) == self.element.get()), 0)
        return Enemy(
            enemy_id=int(self.enemy_id.get()), name=self.name.get().strip(),
            hp=int(self.stats["hp"].get()), exp=int(self.stats["exp"].get()), gp=int(self.stats["gp"].get()),
            level=int(self.stats["level"].get()), strength=int(self.stats["strength"].get()),
            intelligence=int(self.stats["intelligence"].get()), endurance=int(self.stats["endurance"].get()),
            alertness=int(self.stats["alertness"].get()), race=race, element=element,
            attack_animation=int(self.combat["attack_animation"].get()),
            equip_armor=int(self.combat["equip_armor"].get()), equip_amulet=int(self.combat["equip_amulet"].get()),
            spell=int(self.combat["spell"].get()), sprite=self.sprite_b64,
            sprite_tiles=self._sprite_tiles, sprite_palette=self._sprite_palette,
            sprite_w=self._sprite_w, sprite_h=self._sprite_h,
            custom=custom if custom is not None else (original.custom if original else True),
        )

    def _save_enemy(self) -> None:
        try:
            enemy = self._enemy_from_form()
            self.project.save_enemy(enemy, self.current_key)
        except (ValueError, tk.TclError) as error:
            messagebox.showerror(tr("Invalid monster"), str(error), parent=self)
            return
        self.current_key = enemy.key
        self._refresh_list(enemy.key)
        self.on_change()

    def _new_enemy(self) -> None:
        try:
            enemy = Enemy(self.project.next_enemy_id(), tr("New monster"), custom=True)
        except ValueError as error:
            messagebox.showinfo(tr("No free slot"), str(error), parent=self)
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
            duplicate = source.clone(enemy_id=self.project.next_enemy_id(), name=source.name + " — " + tr("copy"), custom=True)
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
            messagebox.showinfo(tr("Cannot delete"), str(error), parent=self)
            return
        self.current_key = None
        self._refresh_list()
        self.on_change()
