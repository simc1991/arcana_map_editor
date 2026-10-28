from __future__ import annotations

from collections import deque
import sys
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .builder import build_rom
from .dungeon_view import DIRECTION_NAMES, move_position, relative_position, tile_at
from .event_editor import EventEditor
from .events import MapEvent, default_properties
from .encounter_database import EncounterDatabase
from .item_database import ItemDatabase
from .monster_database import MonsterDatabase
from .patches import build_ips_patch
from .spell_database import SpellDatabase
from .project import ArcanaProject
from .rendering import event_kind, is_walkable, tile_details, tile_style
from .rom import ArcanaRom, MAP_HEIGHT, MAP_WIDTH, RomError

APP_TITLE = "Arcana Map Studio"
APP_VERSION = "1.0"
PALETTE = (
    (0x00, "Mur / vide"), (0x10, "Rencontre A"), (0x11, "Rencontre B"),
    (0x20, "Rencontre fréquente"), (0x30, "Sol sûr"), (0x40, "Escalier A"),
    (0x41, "Escalier B"), (0x50, "Transition"), (0x60, "Brouillard"),
    (0x63, "Brouillard spécial"), (0x65, "Tuile Reinoll"), (0x70, "Boss / événement"),
    (0x80, "Coffre"), (0x90, "Porte / événement A"), (0x91, "Porte / événement B"),
    (0x92, "Porte / événement C"),
)


class ArcanaEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.geometry("1400x860")
        self.minsize(1050, 700)
        self.project: ArcanaProject | None = None
        self.entry_index = 0
        self.tile_value = tk.IntVar(value=0x30)
        self.tool = tk.StringVar(value="pencil")
        self.zoom = tk.IntVar(value=24)
        self.show_grid = tk.BooleanVar(value=True)
        self.show_ids = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Ouvrez Arcana (USA).sfc pour commencer.")
        self.map_info = tk.StringVar(value="Aucun projet")
        self.selection_info = tk.StringVar(value="Aucune tuile sélectionnée")
        self.selected_x = 0
        self.selected_y = 0
        self.view_direction = 0
        self.preview_info = tk.StringVar(value="Aperçu donjon")
        self.event_search = tk.StringVar()
        self.event_count = tk.StringVar(value="0 événement")
        self.drag_start: tuple[int, int] | None = None
        self.stroke_before: bytes | None = None
        self.undo_stack: deque[tuple[int, bytes, bytes]] = deque(maxlen=100)
        self.redo_stack: deque[tuple[int, bytes, bytes]] = deque(maxlen=100)
        self._configure_style()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._update_title()
        self.after(100, self._open_default_rom)

    @property
    def tile_size(self) -> int:
        return self.zoom.get()

    def _configure_style(self) -> None:
        self.configure(background="#20252d")
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("App.TFrame", background="#20252d")
        style.configure("Panel.TFrame", background="#2a3039")
        style.configure("Panel.TLabel", background="#2a3039", foreground="#eef1f5")
        style.configure("Title.TLabel", background="#2a3039", foreground="#ffffff", font=("Segoe UI", 11, "bold"))
        style.configure("Tool.TButton", padding=(10, 6))
        style.configure("Selected.Tool.TButton", padding=(10, 6), foreground="#235a9f")

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Nouveau depuis un ROM…", accelerator="Ctrl+N", command=self.open_rom)
        file_menu.add_command(label="Ouvrir un projet…", accelerator="Ctrl+O", command=self.open_project)
        file_menu.add_separator()
        file_menu.add_command(label="Enregistrer", accelerator="Ctrl+S", command=self.save_project)
        file_menu.add_command(label="Enregistrer sous…", accelerator="Ctrl+Shift+S", command=lambda: self.save_project(True))
        file_menu.add_separator()
        file_menu.add_command(label="Construire un ROM modifié…", accelerator="Ctrl+B", command=self.export_rom)
        file_menu.add_command(label="Exporter un patch IPS…", command=self.export_patch)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self._close)
        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Annuler", accelerator="Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="Rétablir", accelerator="Ctrl+Y", command=self.redo)
        view_menu = tk.Menu(menu, tearoff=False)
        view_menu.add_checkbutton(label="Afficher la grille", variable=self.show_grid, command=self._draw_map)
        view_menu.add_checkbutton(label="Afficher les valeurs", variable=self.show_ids, command=self._draw_map)
        view_menu.add_separator()
        for size, label in ((16, "50 %"), (24, "75 %"), (32, "100 %"), (48, "150 %"), (64, "200 %")):
            view_menu.add_radiobutton(label=label, variable=self.zoom, value=size, command=self._draw_map)
        database_menu = tk.Menu(menu, tearoff=False)
        database_menu.add_command(label="Objets et équipements…", command=self.open_item_database)
        database_menu.add_command(label="Groupes de rencontres…", command=self.open_encounter_database)
        database_menu.add_command(label="Monstres…", command=self.open_monster_database)
        database_menu.add_command(label="Sorts…", command=self.open_spell_database)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="À propos", command=self._about)
        menu.add_cascade(label="Fichier", menu=file_menu)
        menu.add_cascade(label="Édition", menu=edit_menu)
        menu.add_cascade(label="Base de données", menu=database_menu)
        menu.add_cascade(label="Affichage", menu=view_menu)
        menu.add_cascade(label="Aide", menu=help_menu)
        self.config(menu=menu)

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-n>", lambda _: self.open_rom())
        self.bind_all("<Control-o>", lambda _: self.open_project())
        self.bind_all("<Control-s>", lambda _: self.save_project())
        self.bind_all("<Control-Shift-S>", lambda _: self.save_project(True))
        self.bind_all("<Control-z>", lambda _: self.undo())
        self.bind_all("<Control-y>", lambda _: self.redo())
        self.bind_all("<Control-b>", lambda _: self.export_rom())
        self.bind_all("<Key-p>", lambda _: self._set_tool("pencil"))
        self.bind_all("<Key-r>", lambda _: self._set_tool("rectangle"))
        self.bind_all("<Key-f>", lambda _: self._set_tool("fill"))
        self.bind_all("<Key-i>", lambda _: self._set_tool("picker"))
        self.bind_all("<Key-w>", lambda _: self._preview_move(1))
        self.bind_all("<Key-s>", lambda _: self._preview_move(-1))
        self.bind_all("<Key-a>", lambda _: self._preview_turn(-1))
        self.bind_all("<Key-d>", lambda _: self._preview_turn(1))

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, style="Panel.TFrame", padding=(8, 7))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Nouveau", command=self.open_rom, style="Tool.TButton").pack(side="left", padx=2)
        ttk.Button(toolbar, text="Ouvrir", command=self.open_project, style="Tool.TButton").pack(side="left", padx=2)
        ttk.Button(toolbar, text="Enregistrer", command=self.save_project, style="Tool.TButton").pack(side="left", padx=2)
        ttk.Button(toolbar, text="Base de données", command=self.open_item_database, style="Tool.TButton").pack(side="left", padx=(8, 2))
        ttk.Button(toolbar, text="Construire ROM", command=self.export_rom, style="Tool.TButton").pack(side="left", padx=(2, 14))
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=5)
        self.tool_buttons: dict[str, ttk.Button] = {}
        for key, label in (("pencil", "Crayon (P)"), ("rectangle", "Rectangle (R)"), ("fill", "Remplir (F)"), ("picker", "Pipette (I)")):
            button = ttk.Button(toolbar, text=label, command=lambda value=key: self._set_tool(value), style="Tool.TButton")
            button.pack(side="left", padx=2)
            self.tool_buttons[key] = button
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(toolbar, text="Annuler", command=self.undo, style="Tool.TButton").pack(side="left", padx=2)
        ttk.Button(toolbar, text="Rétablir", command=self.redo, style="Tool.TButton").pack(side="left", padx=2)
        ttk.Label(toolbar, text="Zoom", style="Panel.TLabel").pack(side="right", padx=(8, 3))
        zoom = ttk.Scale(toolbar, from_=16, to=64, variable=self.zoom, command=self._zoom_changed, length=130)
        zoom.pack(side="right")
        self._set_tool("pencil")

        workspace = ttk.Panedwindow(self, orient="horizontal")
        workspace.pack(fill="both", expand=True, padx=7, pady=7)
        left = ttk.Frame(workspace, style="Panel.TFrame", padding=8)
        center = ttk.Frame(workspace, style="Panel.TFrame")
        right = ttk.Frame(workspace, style="Panel.TFrame", padding=8)
        workspace.add(left, weight=0)
        workspace.add(center, weight=1)
        workspace.add(right, weight=0)
        self._build_map_explorer(left)
        self._build_canvas(center)
        self._build_inspector(right)
        status = ttk.Frame(self, style="Panel.TFrame", padding=(8, 4))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status, style="Panel.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Label(status, text=f"Arcana Map Studio {APP_VERSION}", style="Panel.TLabel").pack(side="right")

    def _build_map_explorer(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="EXPLORATEUR", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        self.map_tree = ttk.Treeview(parent, show="tree", selectmode="browse")
        self.map_tree.column("#0", width=220, minwidth=180)
        self.map_tree.pack(fill="both", expand=True)
        self.map_tree.bind("<<TreeviewSelect>>", self._tree_selected)
        ttk.Separator(parent).pack(fill="x", pady=8)
        ttk.Label(parent, text="PALETTE", style="Title.TLabel").pack(anchor="w", pady=(0, 6))
        palette_frame = ttk.Frame(parent, style="Panel.TFrame")
        palette_frame.pack(fill="x")
        self.palette_buttons: list[tk.Button] = []
        for index, (value, name) in enumerate(PALETTE):
            style = tile_style(value)
            button = tk.Button(
                palette_frame, text=f"{style.symbol or ' '}  {name}", anchor="w", width=24,
                background=style.floor, foreground="#ffffff", activebackground=style.accent,
                activeforeground="#ffffff", relief="flat", command=lambda selected=value: self._select_palette(selected),
            )
            button.grid(row=index, column=0, sticky="ew", pady=1)
            self.palette_buttons.append(button)
        custom = ttk.Frame(parent, style="Panel.TFrame")
        custom.pack(fill="x", pady=(7, 0))
        ttk.Label(custom, text="Hex", style="Panel.TLabel").pack(side="left")
        self.hex_entry = ttk.Entry(custom, width=5)
        self.hex_entry.insert(0, "30")
        self.hex_entry.pack(side="left", padx=5)
        ttk.Button(custom, text="Appliquer", command=self._choose_custom).pack(side="left")

    def _build_canvas(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 7))
        header.pack(fill="x")
        ttk.Label(header, textvariable=self.map_info, style="Title.TLabel").pack(side="left")
        ttk.Checkbutton(header, text="Grille", variable=self.show_grid, command=self._draw_map).pack(side="right", padx=4)
        ttk.Checkbutton(header, text="Valeurs", variable=self.show_ids, command=self._draw_map).pack(side="right", padx=4)
        self.view_tabs = ttk.Notebook(parent)
        self.view_tabs.pack(fill="both", expand=True)
        map_tab = ttk.Frame(self.view_tabs)
        preview_tab = ttk.Frame(self.view_tabs, style="Panel.TFrame")
        self.view_tabs.add(map_tab, text="Carte 2D")
        self.view_tabs.add(preview_tab, text="Aperçu In-Game")
        self.view_tabs.bind("<<NotebookTabChanged>>", lambda _: self._draw_preview())
        self.canvas = tk.Canvas(map_tab, background="#11161d", highlightthickness=0)
        x_scroll = ttk.Scrollbar(map_tab, orient="horizontal", command=self.canvas.xview)
        y_scroll = ttk.Scrollbar(map_tab, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        map_tab.columnconfigure(0, weight=1)
        map_tab.rowconfigure(0, weight=1)
        self.canvas.bind("<ButtonPress-1>", self._canvas_press)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_release)
        self.canvas.bind("<Button-3>", self._canvas_pick)
        self.canvas.bind("<Double-1>", self._map_event_double_click)
        self.canvas.bind("<Motion>", self._canvas_hover)
        self.canvas.bind("<MouseWheel>", self._mousewheel)
        preview_header = ttk.Frame(preview_tab, style="Panel.TFrame", padding=7)
        preview_header.pack(fill="x")
        ttk.Label(preview_header, textvariable=self.preview_info, style="Panel.TLabel").pack(side="left")
        for label, action in (("Tourner gauche", lambda: self._preview_turn(-1)), ("Avancer", lambda: self._preview_move(1)), ("Reculer", lambda: self._preview_move(-1)), ("Tourner droite", lambda: self._preview_turn(1))):
            ttk.Button(preview_header, text=label, command=action).pack(side="right", padx=2)
        self.preview_canvas = tk.Canvas(preview_tab, background="#080b10", highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True)
        self.preview_canvas.bind("<Configure>", lambda _: self._draw_preview())
        self.preview_canvas.bind("<Button-1>", lambda _: self._preview_move(1))
        ttk.Label(preview_tab, text="W/S : avancer/reculer   A/D : tourner   •   La position est synchronisée avec la carte 2D", style="Panel.TLabel", anchor="center", padding=5).pack(fill="x")

    def _build_inspector(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="INSPECTEUR", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        tabs = ttk.Notebook(parent, width=285)
        tabs.pack(fill="both", expand=True)
        tile_tab = ttk.Frame(tabs, padding=9)
        event_tab = ttk.Frame(tabs, padding=9)
        tabs.add(tile_tab, text="Tuile")
        tabs.add(event_tab, text="Événements")
        ttk.Label(tile_tab, textvariable=self.selection_info, justify="left", wraplength=250).pack(anchor="w")
        ttk.Separator(tile_tab).pack(fill="x", pady=10)
        ttk.Label(tile_tab, text="Type de gameplay").pack(anchor="w")
        self.property_type = ttk.Combobox(tile_tab, state="readonly", values=[f"${value:02X} — {name}" for value, name in PALETTE])
        self.property_type.pack(fill="x", pady=5)
        self.property_type.bind("<<ComboboxSelected>>", self._property_changed)
        ttk.Button(tile_tab, text="Appliquer à la tuile", command=self._apply_property).pack(fill="x", pady=5)
        ttk.Separator(tile_tab).pack(fill="x", pady=10)
        ttk.Label(tile_tab, text="Le rendu représente la logique du jeu : murs, sols, rencontres, passages, coffres et événements.", wraplength=250, justify="left").pack(anchor="w")
        search = ttk.Frame(event_tab)
        search.pack(fill="x", pady=(0, 7))
        ttk.Entry(search, textvariable=self.event_search).pack(side="left", fill="x", expand=True)
        ttk.Button(search, text="Effacer", command=lambda: self.event_search.set("")).pack(side="left", padx=(4, 0))
        self.event_search.trace_add("write", lambda *_: self._refresh_events())
        columns = ("name", "type", "position")
        self.event_tree = ttk.Treeview(event_tab, columns=columns, show="headings", height=16)
        self.event_tree.heading("name", text="Nom")
        self.event_tree.heading("type", text="Type")
        self.event_tree.heading("position", text="Position")
        self.event_tree.column("name", width=120)
        self.event_tree.column("type", width=80)
        self.event_tree.column("position", width=60, anchor="center")
        self.event_tree.pack(fill="both", expand=True)
        self.event_tree.bind("<<TreeviewSelect>>", self._event_selected)
        self.event_tree.bind("<Double-1>", lambda _: self._edit_selected_event())
        ttk.Label(event_tab, textvariable=self.event_count).pack(anchor="w", pady=(5, 3))
        buttons = ttk.Frame(event_tab)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Nouveau", command=self._new_event).pack(side="left", fill="x", expand=True)
        ttk.Button(buttons, text="Modifier", command=self._edit_selected_event).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Button(buttons, text="Dupliquer", command=self._duplicate_selected_event).pack(side="left", fill="x", expand=True)
        ttk.Button(event_tab, text="Supprimer l’événement", command=self._delete_selected_event).pack(fill="x", pady=(4, 0))
        ttk.Label(event_tab, text="Double-cliquez un événement pour ouvrir l’éditeur complet.", wraplength=250, justify="left").pack(anchor="w", pady=(8, 0))

    def _set_tool(self, value: str) -> None:
        self.tool.set(value)
        for key, button in getattr(self, "tool_buttons", {}).items():
            button.configure(style="Selected.Tool.TButton" if key == value else "Tool.TButton")
        names = {"pencil": "Crayon", "rectangle": "Rectangle", "fill": "Remplissage", "picker": "Pipette"}
        self.status.set(f"Outil : {names[value]}")

    def _open_default_rom(self) -> None:
        candidates = [Path.cwd() / "Arcana (USA).sfc"]
        if getattr(sys, "frozen", False):
            candidates.insert(0, Path(sys.executable).parent / "Arcana (USA).sfc")
        for candidate in candidates:
            if candidate.exists():
                self._load_rom(candidate)
                break

    def open_rom(self) -> None:
        if not self._discard_changes():
            return
        path = filedialog.askopenfilename(title="Créer un projet depuis Arcana USA", filetypes=(("ROM SNES", "*.sfc *.smc"), ("Tous les fichiers", "*.*")))
        if path:
            self._load_rom(Path(path))

    def _load_rom(self, path: Path) -> None:
        try:
            rom = ArcanaRom(path)
            self.project = ArcanaProject.from_rom(rom)
        except (OSError, RomError) as error:
            messagebox.showerror(APP_TITLE, str(error), parent=self)
            return
        self.entry_index = 0
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._populate_maps()
        quality = "dump vérifié" if rom.info.is_known_dump else "dump compatible"
        self.status.set(f"{path.name} — CRC32 {rom.info.crc32:08X} — {quality}")
        self._refresh_all()
        self._update_title()

    def _populate_maps(self) -> None:
        self.map_tree.delete(*self.map_tree.get_children())
        if not self.project:
            return
        groups = (("Chapitre 1", range(0, 2)), ("Chapitre 2", range(2, 5)), ("Chapitre 3", range(5, 8)), ("Chapitre 4", range(8, 22)), ("Chapitre 5", range(22, 34)))
        for group, indices in groups:
            parent = self.map_tree.insert("", "end", text=group, open=True)
            for index in indices:
                self.map_tree.insert(parent, "end", iid=f"map-{index}", text=self.project.rom.maps[index].name)
        self.map_tree.selection_set("map-0")
        self.map_tree.see("map-0")

    def open_project(self) -> None:
        if not self.project:
            messagebox.showinfo(APP_TITLE, "Ouvrez d’abord le ROM de base.", parent=self)
            return
        if not self._discard_changes():
            return
        path = filedialog.askopenfilename(title="Ouvrir un projet", filetypes=(("Projet Arcana", "*.arcana.json"), ("JSON", "*.json")))
        if not path:
            return
        try:
            self.project = ArcanaProject.load(self.project.rom, path)
        except (OSError, ValueError, RomError) as error:
            messagebox.showerror(APP_TITLE, str(error), parent=self)
            return
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._refresh_all()
        self.status.set(f"Projet ouvert : {path}")
        self._update_title()

    def open_item_database(self) -> None:
        if not self.project:
            messagebox.showinfo(APP_TITLE, "Ouvrez d’abord un ROM ou un projet.", parent=self)
            return
        ItemDatabase(self, self.project, self._item_database_changed)

    def _item_database_changed(self) -> None:
        self._refresh_events()
        self._update_title()
        self.status.set(f"Base de données mise à jour — {len(self.project.items)} entrées disponibles")

    def open_encounter_database(self) -> None:
        if not self.project:
            messagebox.showinfo(APP_TITLE, "Ouvrez d’abord un ROM ou un projet.", parent=self)
            return
        EncounterDatabase(self, self.project, self._encounter_database_changed)

    def _encounter_database_changed(self) -> None:
        self._refresh_events()
        self._update_title()
        self.status.set(f"Groupes de rencontres mis à jour — {len(self.project.encounter_groups)} groupes disponibles")

    def open_monster_database(self) -> None:
        if not self.project:
            messagebox.showinfo(APP_TITLE, "Ouvrez d’abord un ROM ou un projet.", parent=self)
            return
        MonsterDatabase(self, self.project, self._monster_database_changed)

    def _monster_database_changed(self) -> None:
        self._refresh_events()
        self._update_title()
        self.status.set(f"Base de données monstres mise à jour — {len(self.project.enemies)} entrées disponibles")

    def open_spell_database(self) -> None:
        if not self.project:
            messagebox.showinfo(APP_TITLE, "Ouvrez d’abord un ROM ou un projet.", parent=self)
            return
        SpellDatabase(self, self.project, self._spell_database_changed)

    def _spell_database_changed(self) -> None:
        self._refresh_events()
        self._update_title()
        self.status.set(f"Base de données sorts mise à jour — {len(self.project.spells)} entrées disponibles")

    def export_patch(self) -> None:
        if not self.project:
            messagebox.showinfo(APP_TITLE, "Ouvrez d’abord un ROM ou un projet.", parent=self)
            return
        destination = filedialog.asksaveasfilename(
            title="Exporter un patch IPS",
            defaultextension=".ips",
            filetypes=(("Patch IPS", "*.ips"), ("Tous les fichiers", "*.*")),
            parent=self,
        )
        if not destination:
            return
        try:
            with tempfile.NamedTemporaryFile(suffix=".sfc", delete=False) as temporary:
                temp_path = Path(temporary.name)
            try:
                report = build_rom(self.project, temp_path)
                patched = temp_path.read_bytes()
            finally:
                temp_path.unlink(missing_ok=True)
            patch = build_ips_patch(self.project.rom.data, patched)
            Path(destination).write_bytes(patch)
        except RomError as error:
            messagebox.showerror("Export impossible", str(error), parent=self)
            return
        self.status.set(f"Patch IPS exporté : {Path(destination).name} ({len(patch)} octets) — {report.warnings and 'avertissements : ' + '; '.join(report.warnings) or 'aucun avertissement'}")

    def export_rom(self) -> None:
        if not self.project:
            messagebox.showinfo(APP_TITLE, "Ouvrez d’abord un ROM ou un projet.", parent=self)
            return
        destination = filedialog.asksaveasfilename(
            title="Construire un ROM modifié",
            defaultextension=".sfc",
            initialfile="Arcana (Mod).sfc",
            filetypes=(("ROM SNES", "*.sfc"),),
        )
        if not destination:
            return
        try:
            report = build_rom(self.project, destination)
        except (OSError, RomError) as error:
            messagebox.showerror("Construction impossible", str(error), parent=self)
            return
        details = (
            f"ROM construit et vérifié avec succès.\n\n"
            f"Cartes injectées : {report.maps_written}\n"
            f"Données compressées : {report.compressed_bytes} / {report.available_bytes} octets\n"
            f"Coffres injectés : {report.treasures_written}\n"
            f"Escaliers injectés : {report.stairs_written}\n"
            f"Objets injectés : {report.items_written}\n"
            f"Objets en boutique : {report.shop_slots_written}\n"
            f"Groupes de rencontres : {report.encounters_written}\n"
            f"Monstres injectés : {report.enemies_written}\n"
            f"Checksum SNES : ${report.checksum:04X}\n\n"
            f"Fichier : {report.output_path}"
        )
        if report.warnings:
            details += "\n\nAvertissements :\n- " + "\n- ".join(report.warnings)
        messagebox.showinfo("Construction terminée", details, parent=self)
        self.status.set(f"ROM construit : {report.output_path.name}")

    def save_project(self, save_as: bool = False) -> None:
        if not self.project:
            return
        path = self.project.path
        if save_as or path is None:
            selected = filedialog.asksaveasfilename(title="Enregistrer le projet", defaultextension=".arcana.json", filetypes=(("Projet Arcana", "*.arcana.json"),))
            if not selected:
                return
            path = Path(selected)
        try:
            self.project.save(path)
        except OSError as error:
            messagebox.showerror(APP_TITLE, str(error), parent=self)
            return
        self.status.set(f"Projet enregistré : {path}")
        self._update_title()

    def _tree_selected(self, _: object = None) -> None:
        selection = self.map_tree.selection()
        if selection and selection[0].startswith("map-"):
            self.entry_index = int(selection[0][4:])
            self._refresh_all()

    def _refresh_all(self) -> None:
        self._draw_map()
        self._refresh_events()
        self._select_tile(self.selected_x, self.selected_y)

    def _draw_map(self) -> None:
        self.canvas.delete("all")
        size = self.tile_size
        self.canvas.configure(scrollregion=(0, 0, MAP_WIDTH * size, MAP_HEIGHT * size))
        if not self.project:
            return
        tiles = self.project.map_for_entry(self.entry_index)
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                self._draw_tile(x, y, tiles[y * MAP_WIDTH + x])
        entry = self.project.rom.maps[self.entry_index]
        aliases = [item.name for item in self.project.rom.maps if item.snes_address == entry.snes_address]
        shared = f" • bloc partagé par {len(aliases)} étages" if len(aliases) > 1 else ""
        self.map_info.set(f"{entry.name}   |   32 × 32{shared}")
        self._draw_selection()

    def _draw_tile(self, x: int, y: int, value: int) -> None:
        size = self.tile_size
        x0, y0 = x * size, y * size
        style = tile_style(value)
        outline = "#39434f" if self.show_grid.get() else style.floor
        self.canvas.create_rectangle(x0, y0, x0 + size, y0 + size, fill=style.floor, outline=outline, tags=("map", f"tile-{x}-{y}"))
        if is_walkable(value):
            inset = max(2, size // 8)
            self.canvas.create_rectangle(x0 + inset, y0 + inset, x0 + size - inset, y0 + size - inset, outline=style.accent, width=max(1, size // 18), tags=("map", f"tile-{x}-{y}"))
            self._draw_walls(x, y, value)
        if style.symbol and size >= 20:
            self.canvas.create_text(x0 + size / 2, y0 + size / 2, text=style.symbol, fill=style.accent, font=("Segoe UI Symbol", max(9, size // 3), "bold"), tags=("map", f"tile-{x}-{y}"))
        if self.show_ids.get() and size >= 24:
            self.canvas.create_text(x0 + 3, y0 + 2, text=f"{value:02X}", fill="#ffffff", anchor="nw", font=("Consolas", max(6, size // 6)), tags=("map", f"tile-{x}-{y}"))

    def _draw_walls(self, x: int, y: int, value: int) -> None:
        if not self.project or not is_walkable(value):
            return
        size = self.tile_size
        tiles = self.project.map_for_entry(self.entry_index)
        x0, y0 = x * size, y * size
        neighbors = ((0, -1, x0, y0, x0 + size, y0), (1, 0, x0 + size, y0, x0 + size, y0 + size), (0, 1, x0, y0 + size, x0 + size, y0 + size), (-1, 0, x0, y0, x0, y0 + size))
        for dx, dy, ax, ay, bx, by in neighbors:
            nx, ny = x + dx, y + dy
            adjacent = tiles[ny * MAP_WIDTH + nx] if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT else 0
            if not is_walkable(adjacent):
                self.canvas.create_line(ax, ay, bx, by, fill="#d6c7a5", width=max(2, size // 10), tags="map")

    def _draw_selection(self) -> None:
        size = self.tile_size
        self.canvas.delete("selection")
        x0, y0 = self.selected_x * size, self.selected_y * size
        self.canvas.create_rectangle(x0 + 1, y0 + 1, x0 + size - 1, y0 + size - 1, outline="#55b7ff", width=3, tags="selection")
        points = {
            0: (x0 + size / 2, y0 + 4, x0 + size - 5, y0 + size - 5, x0 + size / 2, y0 + size * 0.68, x0 + 5, y0 + size - 5),
            1: (x0 + size - 4, y0 + size / 2, x0 + 5, y0 + 5, x0 + size * 0.32, y0 + size / 2, x0 + 5, y0 + size - 5),
            2: (x0 + size / 2, y0 + size - 4, x0 + 5, y0 + 5, x0 + size / 2, y0 + size * 0.32, x0 + size - 5, y0 + 5),
            3: (x0 + 4, y0 + size / 2, x0 + size - 5, y0 + size - 5, x0 + size * 0.68, y0 + size / 2, x0 + size - 5, y0 + 5),
        }[self.view_direction]
        self.canvas.create_polygon(points, fill="#55b7ff", outline="#ffffff", tags="selection")

    def _coordinates(self, event: tk.Event) -> tuple[int, int]:
        return int(self.canvas.canvasx(event.x)) // self.tile_size, int(self.canvas.canvasy(event.y)) // self.tile_size

    def _canvas_press(self, event: tk.Event) -> None:
        if not self.project:
            return
        x, y = self._coordinates(event)
        if not self._valid_xy(x, y):
            return
        self._select_tile(x, y)
        if self.project.event_at(self.entry_index, x, y):
            self.drag_start = None
            self.stroke_before = None
            return
        self.drag_start = (x, y)
        self.stroke_before = bytes(self.project.map_for_entry(self.entry_index))
        if self.tool.get() == "pencil":
            self._paint_at(x, y)
        elif self.tool.get() == "fill":
            self._flood_fill(x, y)
        elif self.tool.get() == "picker":
            self._pick_at(x, y)

    def _canvas_drag(self, event: tk.Event) -> None:
        if self.tool.get() != "pencil" or not self.project:
            return
        x, y = self._coordinates(event)
        if self._valid_xy(x, y):
            self._paint_at(x, y)
            self._select_tile(x, y)

    def _canvas_release(self, event: tk.Event) -> None:
        if not self.project or self.stroke_before is None:
            return
        x, y = self._coordinates(event)
        if self.tool.get() == "rectangle" and self.drag_start and self._valid_xy(x, y):
            x0, y0 = self.drag_start
            for py in range(min(y0, y), max(y0, y) + 1):
                for px in range(min(x0, x), max(x0, x) + 1):
                    self.project.set_tile(self.entry_index, px, py, self.tile_value.get())
        after = bytes(self.project.map_for_entry(self.entry_index))
        if after != self.stroke_before:
            self.undo_stack.append((self.entry_index, self.stroke_before, after))
            self.redo_stack.clear()
            self.project.dirty = True
            self._refresh_all()
            self._update_title()
        self.drag_start = None
        self.stroke_before = None

    def _paint_at(self, x: int, y: int) -> None:
        if self.project:
            self.project.set_tile(self.entry_index, x, y, self.tile_value.get())
            self._draw_map()

    def _flood_fill(self, x: int, y: int) -> None:
        if not self.project:
            return
        tiles = self.project.map_for_entry(self.entry_index)
        old, new = tiles[y * MAP_WIDTH + x], self.tile_value.get()
        if old == new:
            return
        pending = [(x, y)]
        seen = set()
        while pending:
            px, py = pending.pop()
            if (px, py) in seen or not self._valid_xy(px, py) or tiles[py * MAP_WIDTH + px] != old:
                continue
            seen.add((px, py))
            self.project.set_tile(self.entry_index, px, py, new)
            pending.extend(((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)))

    def _canvas_pick(self, event: tk.Event) -> None:
        x, y = self._coordinates(event)
        if self._valid_xy(x, y):
            self._pick_at(x, y)
            self._select_tile(x, y)

    def _map_event_double_click(self, event: tk.Event) -> None:
        if not self.project:
            return
        x, y = self._coordinates(event)
        found = self.project.event_at(self.entry_index, x, y)
        if not found:
            address = self.project.rom.maps[self.entry_index].snes_address
            value = self.tile_value.get() if event_kind(self.tile_value.get()) else 0x70
            found = MapEvent(address, x, y, value, properties=default_properties(value))
        self.selected_x, self.selected_y = x, y
        EventEditor(self, found, self._save_edited_event, self.project.items, self.project.encounters_for_map(self.entry_index), tuple((entry.index, entry.name) for entry in self.project.rom.maps))

    def _pick_at(self, x: int, y: int) -> None:
        if not self.project:
            return
        value = self.project.map_for_entry(self.entry_index)[y * MAP_WIDTH + x]
        self._select_palette(value)
        self.status.set(f"Pipette : ${value:02X} à ({x}, {y})")

    def _select_tile(self, x: int, y: int) -> None:
        if not self.project or not self._valid_xy(x, y):
            return
        self.selected_x, self.selected_y = x, y
        value = self.project.map_for_entry(self.entry_index)[y * MAP_WIDTH + x]
        style = tile_style(value)
        self.selection_info.set(f"Position : X {x:02d}, Y {y:02d}\nValeur : ${value:02X}\nType : {style.name}\nCatégorie : {style.category}\n\n{tile_details(value)}")
        matching = next((index for index, (candidate, _) in enumerate(PALETTE) if candidate == value), -1)
        self.property_type.current(matching)
        self._draw_selection()
        self._draw_preview()

    def _refresh_events(self) -> None:
        self.event_tree.delete(*self.event_tree.get_children())
        if not self.project:
            self.event_count.set("0 événement")
            return
        query = self.event_search.get().strip().casefold()
        events = self.project.events_for_entry(self.entry_index)
        visible = [event for event in events if not query or query in f"{event.display_name} {event.kind} {event.x} {event.y}".casefold()]
        for event in visible:
            self.event_tree.insert("", "end", iid=f"event-{event.x}-{event.y}", values=(event.display_name, event.kind, f"{event.x}, {event.y}"))
        suffix = "événement" if len(events) == 1 else "événements"
        filtered = f" — {len(visible)} affiché(s)" if len(visible) != len(events) else ""
        self.event_count.set(f"{len(events)} {suffix}{filtered}")

    def _event_selected(self, _: object = None) -> None:
        event = self._selected_event()
        if not event:
            return
        self._select_tile(event.x, event.y)
        size = self.tile_size
        self.canvas.xview_moveto(max(0, event.x * size - 250) / max(1, MAP_WIDTH * size))
        self.canvas.yview_moveto(max(0, event.y * size - 250) / max(1, MAP_HEIGHT * size))

    def _selected_event(self) -> MapEvent | None:
        if not self.project:
            return None
        selection = self.event_tree.selection()
        if not selection:
            return self.project.event_at(self.entry_index, self.selected_x, self.selected_y)
        _, x, y = selection[0].split("-")
        return self.project.event_at(self.entry_index, int(x), int(y))

    def _new_event(self) -> None:
        if not self.project:
            return
        x, y = self._find_free_event_position(self.selected_x, self.selected_y)
        address = self.project.rom.maps[self.entry_index].snes_address
        event = MapEvent(address, x, y, 0x70, properties=default_properties(0x70))
        EventEditor(self, event, self._save_edited_event, self.project.items, self.project.encounters_for_map(self.entry_index), tuple((entry.index, entry.name) for entry in self.project.rom.maps))

    def _edit_selected_event(self) -> None:
        event = self._selected_event()
        if not event:
            messagebox.showinfo(APP_TITLE, "Sélectionnez d’abord un événement dans la liste ou sur la carte.", parent=self)
            return
        EventEditor(self, event, self._save_edited_event, self.project.items, self.project.encounters_for_map(self.entry_index), tuple((entry.index, entry.name) for entry in self.project.rom.maps))

    def _save_edited_event(self, event: MapEvent, old_x: int, old_y: int) -> None:
        if not self.project:
            return
        try:
            self.project.update_event(self.entry_index, event, old_x, old_y)
        except ValueError as error:
            messagebox.showerror("Impossible d’enregistrer", str(error), parent=self)
            return
        self.selected_x, self.selected_y = event.x, event.y
        self._refresh_all()
        self._update_title()
        iid = f"event-{event.x}-{event.y}"
        if self.event_tree.exists(iid):
            self.event_tree.selection_set(iid)
            self.event_tree.see(iid)
        self.status.set(f"Événement enregistré : {event.display_name}")

    def _duplicate_selected_event(self) -> None:
        event = self._selected_event()
        if not event or not self.project:
            messagebox.showinfo(APP_TITLE, "Sélectionnez l’événement à dupliquer.", parent=self)
            return
        x, y = self._find_free_event_position(event.x + 1, event.y)
        duplicate = MapEvent(event.map_address, x, y, event.value, f"{event.display_name} — copie", event.notes, dict(event.properties))
        self.project.update_event(self.entry_index, duplicate, x, y)
        self.selected_x, self.selected_y = x, y
        self._refresh_all()
        self._update_title()
        self.status.set(f"Événement dupliqué en ({x}, {y})")

    def _delete_selected_event(self) -> None:
        event = self._selected_event()
        if not event or not self.project:
            messagebox.showinfo(APP_TITLE, "Sélectionnez l’événement à supprimer.", parent=self)
            return
        if not messagebox.askyesno("Supprimer l’événement", f"Supprimer « {event.display_name} » ?\nLa case deviendra un sol sûr.", parent=self):
            return
        self.project.remove_event(self.entry_index, event.x, event.y)
        self._refresh_all()
        self._update_title()
        self.status.set("Événement supprimé.")

    def _find_free_event_position(self, start_x: int, start_y: int) -> tuple[int, int]:
        if not self.project:
            return 0, 0
        for distance in range(MAP_WIDTH * MAP_HEIGHT):
            position = ((start_y * MAP_WIDTH + start_x) + distance) % (MAP_WIDTH * MAP_HEIGHT)
            x, y = position % MAP_WIDTH, position // MAP_WIDTH
            if self.project.event_at(self.entry_index, x, y) is None:
                return x, y
        raise ValueError("La carte ne contient plus d’emplacement libre")

    def _property_changed(self, _: object = None) -> None:
        index = self.property_type.current()
        if index >= 0:
            self._select_palette(PALETTE[index][0])

    def _apply_property(self) -> None:
        if not self.project:
            return
        before = bytes(self.project.map_for_entry(self.entry_index))
        self.project.set_tile(self.entry_index, self.selected_x, self.selected_y, self.tile_value.get())
        after = bytes(self.project.map_for_entry(self.entry_index))
        if before != after:
            self.undo_stack.append((self.entry_index, before, after))
            self.redo_stack.clear()
            self._refresh_all()
            self._update_title()

    def _select_palette(self, value: int) -> None:
        self.tile_value.set(value)
        self.hex_entry.delete(0, "end")
        self.hex_entry.insert(0, f"{value:02X}")
        self.status.set(f"Tuile active : ${value:02X} — {tile_style(value).name}")

    def _choose_custom(self) -> None:
        try:
            value = int(self.hex_entry.get(), 16)
            if not 0 <= value <= 0xFF:
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_TITLE, "Entrez une valeur hexadécimale de 00 à FF.", parent=self)
            return
        self._select_palette(value)

    def undo(self) -> None:
        if not self.project or not self.undo_stack:
            return
        entry, before, after = self.undo_stack.pop()
        self.project.replace_map(entry, before)
        self.redo_stack.append((entry, before, after))
        self.entry_index = entry
        self._sync_tree_selection()
        self._refresh_all()
        self._update_title()

    def redo(self) -> None:
        if not self.project or not self.redo_stack:
            return
        entry, before, after = self.redo_stack.pop()
        self.project.replace_map(entry, after)
        self.undo_stack.append((entry, before, after))
        self.entry_index = entry
        self._sync_tree_selection()
        self._refresh_all()
        self._update_title()

    def _sync_tree_selection(self) -> None:
        iid = f"map-{self.entry_index}"
        self.map_tree.selection_set(iid)
        self.map_tree.see(iid)

    def _canvas_hover(self, event: tk.Event) -> None:
        if not self.project:
            return
        x, y = self._coordinates(event)
        if self._valid_xy(x, y):
            value = self.project.map_for_entry(self.entry_index)[y * MAP_WIDTH + x]
            self.status.set(f"{self.project.rom.maps[self.entry_index].name}   X:{x:02d} Y:{y:02d}   ${value:02X} {tile_style(value).name}")

    def _mousewheel(self, event: tk.Event) -> None:
        if event.state & 0x0004:
            self.zoom.set(max(16, min(64, self.zoom.get() + (4 if event.delta > 0 else -4))))
            self._draw_map()
        else:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _zoom_changed(self, _: object = None) -> None:
        value = int(round(self.zoom.get() / 4) * 4)
        if value != self.zoom.get():
            self.zoom.set(value)
        self._draw_map()

    def _preview_turn(self, amount: int) -> None:
        self.view_direction = (self.view_direction + amount) % 4
        self._draw_preview()
        self._draw_selection()

    def _preview_move(self, amount: int) -> None:
        if not self.project:
            return
        tiles = self.project.map_for_entry(self.entry_index)
        x, y = move_position(tiles, self.selected_x, self.selected_y, self.view_direction, amount)
        if (x, y) != (self.selected_x, self.selected_y):
            self._select_tile(x, y)
            self._draw_preview()
        else:
            self.status.set("Un mur bloque le passage.")

    def _draw_preview(self) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        canvas = self.preview_canvas
        canvas.delete("all")
        width = max(640, canvas.winfo_width())
        height = max(420, canvas.winfo_height())
        canvas.create_rectangle(0, 0, width, height / 2, fill="#17202b", outline="")
        canvas.create_rectangle(0, height / 2, width, height, fill="#302c28", outline="")
        if not self.project:
            canvas.create_text(width / 2, height / 2, text="Ouvrez un ROM pour afficher le donjon", fill="#d8dee9", font=("Segoe UI", 16))
            return
        tiles = self.project.map_for_entry(self.entry_index)
        frames = []
        for depth in range(6):
            margin_x = width * (0.05 + depth * 0.075)
            margin_y = height * (0.07 + depth * 0.068)
            frames.append((margin_x, margin_y, width - margin_x, height - margin_y))
        for depth in range(4, -1, -1):
            outer = frames[depth]
            inner = frames[depth + 1]
            center_x, center_y = relative_position(self.selected_x, self.selected_y, self.view_direction, 0, depth)
            current = tile_at(tiles, center_x, center_y)
            if current == 0 and depth == 0:
                canvas.create_rectangle(*outer, fill="#3b4650", outline="#c9b995", width=4)
                break
            left_x, left_y = relative_position(self.selected_x, self.selected_y, self.view_direction, -1, depth)
            right_x, right_y = relative_position(self.selected_x, self.selected_y, self.view_direction, 1, depth)
            if tile_at(tiles, left_x, left_y) == 0:
                canvas.create_polygon(outer[0], outer[1], inner[0], inner[1], inner[0], inner[3], outer[0], outer[3], fill="#46515b", outline="#9d927b")
            else:
                canvas.create_line(outer[0], outer[1], inner[0], inner[1], fill="#756e61", width=2)
                canvas.create_line(outer[0], outer[3], inner[0], inner[3], fill="#756e61", width=2)
            if tile_at(tiles, right_x, right_y) == 0:
                canvas.create_polygon(outer[2], outer[1], inner[2], inner[1], inner[2], inner[3], outer[2], outer[3], fill="#414b55", outline="#9d927b")
            else:
                canvas.create_line(outer[2], outer[1], inner[2], inner[1], fill="#756e61", width=2)
                canvas.create_line(outer[2], outer[3], inner[2], inner[3], fill="#756e61", width=2)
            canvas.create_polygon(outer[0], outer[3], inner[0], inner[3], inner[2], inner[3], outer[2], outer[3], fill="#38332e", outline="#70675a")
            canvas.create_polygon(outer[0], outer[1], inner[0], inner[1], inner[2], inner[1], outer[2], outer[1], fill="#202a35", outline="#56616c")
            front_x, front_y = relative_position(self.selected_x, self.selected_y, self.view_direction, 0, depth + 1)
            front = tile_at(tiles, front_x, front_y)
            if front == 0:
                shade = 58 + depth * 7
                color = f"#{shade:02x}{shade + 8:02x}{shade + 12:02x}"
                canvas.create_rectangle(*inner, fill=color, outline="#b7a987", width=max(1, 4 - depth // 2))
                self._draw_preview_bricks(inner)
            elif event_kind(front):
                style = tile_style(front)
                scale = max(12, int((inner[3] - inner[1]) * 0.16))
                canvas.create_text((inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2, text=style.symbol or "◆", fill=style.accent, font=("Segoe UI Symbol", scale, "bold"))
                canvas.create_text((inner[0] + inner[2]) / 2, inner[3] - 18, text=style.name, fill="#f4f1e8", font=("Segoe UI", max(8, scale // 3), "bold"))
        current = tile_at(tiles, self.selected_x, self.selected_y)
        self.preview_info.set(f"X {self.selected_x:02d}  Y {self.selected_y:02d}  •  {DIRECTION_NAMES[self.view_direction]}  •  {tile_style(current).name}")
        canvas.create_text(16, 16, text=self.project.rom.maps[self.entry_index].name, fill="#ffffff", anchor="nw", font=("Segoe UI", 14, "bold"))

    def _draw_preview_bricks(self, frame: tuple[float, float, float, float]) -> None:
        x0, y0, x1, y1 = frame
        height = y1 - y0
        width = x1 - x0
        for row in range(1, 5):
            y = y0 + height * row / 5
            self.preview_canvas.create_line(x0, y, x1, y, fill="#667079")
            offset = width / 8 if row % 2 else 0
            for column in range(1, 4):
                x = x0 + width * column / 4 + offset
                if x < x1:
                    self.preview_canvas.create_line(x, y - height / 5, x, y, fill="#667079")

    @staticmethod
    def _valid_xy(x: int, y: int) -> bool:
        return 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT

    def _discard_changes(self) -> bool:
        if not self.project or not self.project.dirty:
            return True
        answer = messagebox.askyesnocancel(APP_TITLE, "Enregistrer les modifications avant de continuer ?", parent=self)
        if answer is None:
            return False
        if answer:
            self.save_project()
            return not self.project.dirty
        return True

    def _update_title(self) -> None:
        suffix = ""
        if self.project:
            suffix = f" — {self.project.path.name if self.project.path else self.project.rom.path.name}"
            if self.project.dirty:
                suffix += " *"
        self.title(f"{APP_TITLE} {APP_VERSION}{suffix}")

    def _about(self) -> None:
        messagebox.showinfo(APP_TITLE, f"Arcana Map Studio {APP_VERSION}\nÉditeur visuel non officiel pour Arcana USA (SNES).\n\nRendu WYSIWYG logique, cartes, rencontres, transitions, coffres et événements.", parent=self)

    def _close(self) -> None:
        if self._discard_changes():
            self.destroy()


def main() -> None:
    ArcanaEditor().mainloop()
