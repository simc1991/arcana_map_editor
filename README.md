# Arcana Map Studio

Open source map editor and analysis tools for **Arcana (USA)** on the Super Nintendo.

## Current state

Version `0.7.1` provides:

- validation of the Arcana USA LoROM dump, with or without a 512-byte copier header;
- SNES header reading, SHA-256 and CRC32;
- native decompression of the HAL format used by the game;
- extraction of the 34 dungeon entries and the 14 unique 32×32 map blocks;
- an RPG Maker XP-inspired workspace with explorer, toolbar, palette and inspector;
- WYSIWYG top-down rendering of the game logic with floors, walls, encounters, fog, stairs, chests and events;
- a first-person In-Game preview synchronized with the 2D map;
- dungeon navigation with `W/S`, rotation with `A/D` and visible orientation on the plan;
- perspective walls, depth, bricks, corridors and interactive markers in the preview;
- zoom from 50 to 200%, grid and optional display of technical values;
- pencil, rectangle, fill and eyedropper tools with undo/redo history;
- a chapter-structured explorer and a panel listing every interactive element on the map;
- a full event editor with General, Gameplay and Notes tabs;
- custom names, moving, type switching and variants without mandatory hex editing;
- context-sensitive properties: chest contents, destination, orientation, encounter group, frequency, condition and trigger;
- chest catalog decoded from the ROM with 145 entries: currency, items, weapons, armors, shields, accessories and cards;
- a searchable item picker showing name, category and game identifier;
- an RPG Maker-style item database with search and filters;
- item editing, duplication and creation stored in the project;
- editable equipment statistics: attack, defense, magic defense and attributes;
- weapon attack, armor/shield/accessory defense and magic defense decoded from ROM tables;
- original per-character equipment restrictions;
- irrelevant fields automatically disabled depending on the category;
- buy price and resale value decoded from the ROM for equipment;
- per-character equipment restrictions and vendor assignment by chapter;
- new items immediately available in the chest picker;
- instant search, creation, duplication, deletion and navigation to events;
- validation of positions, variants and event collisions;
- semantic editing of encounters, transitions, chests and tile-encoded events;
- explanation of variants, encounter tables and the real `1/12` or `1/4` rates in the inspector;
- support for maps shared between Stavery floors;
- non-destructive saving in a JSON project backward-compatible with versions 0.1, 0.2 and 0.3;
- a HAL compressor compatible with the commands used by the maps;
- automatic reconstruction and relocation of the 14 map blocks in bank `$13`;
- update of the 34 map pointers and the SNES checksum;
- non-destructive export to a new `.sfc` file verified by re-decompression;
- injection of types, identifiers, quantities and new positions of existing chests;
- decoding of stair tables, including the adjacent activation tile;
- injection of target maps, coordinates and orientations of existing internal stairs;
- report of the number of chests and stairs actually injected;
- capacity report and warnings about data that is not injected yet;
- a standalone Windows executable built with PyInstaller.

The second roadmap milestone is underway: grid-carried interactive elements are now visible and editable. Editing their associated detailed tables — exact chest contents, stair destinations and enemy formations — remains to be completed. Injecting into a new ROM still requires safe recompression and patch export.

## Run from sources

Requirements: Python 3.11 or newer with Tk.

```powershell
python -m pip install -e .
python -m arcana_editor
```

The application automatically detects `Arcana (USA).sfc` in the current folder. The reference dump has the following SHA-256:

```text
aac9d6f2b8408e4bbdc83ebbba755428caf8021fefbfac7220fb4c772abd9944
```

## Build the `.exe`

```powershell
python -m pip install pytest pyinstaller
.\build.ps1
```

The result is `dist\ArcanaMapStudio.exe`. Place your own `Arcana (USA).sfc` next to the executable or use **File > Open ROM**.

## Build a modified ROM

Use **File > Build modified ROM** or `Ctrl+B`. The editor recompresses the maps, places them back in their original area, updates pointers and the checksum, then re-decompresses each map of the produced file to verify the export. The source dump is never overwritten.

Version 0.7.1 fully rebuilds and relocates the chest and stair tables in the verified free areas of banks `$18` and `$03`. It supports creating and deleting chests, adding stairs, and converting an external exit into a dungeon destination. Encounters, custom items, statistics and vendor inventories remain saved in the project but are not yet written to the ROM.

## Extract the maps

```powershell
python -m arcana_editor.extract "Arcana (USA).sfc" extracted
```

The command creates a JSON manifest and 14 decompressed 1,024-byte binary grids. These generated files must not be published without checking your rights.

## Tests

```powershell
python -m pytest
```

ROM-independent tests run on GitHub Actions. Integration tests are automatically skipped when the proprietary ROM is absent.

## Architecture

- `src/arcana_editor/rom.py`: SNES header, LoROM addressing, HAL decompression and map tables.
- `src/arcana_editor/project.py`: non-destructive project model and JSON serialization.
- `src/arcana_editor/app.py`: Tkinter interface.
- `src/arcana_editor/extract.py`: reproducible extraction of map data.
- `tests/`: unit tests and local integration tests.

## Decompilation

An annotated 65c816 disassembly already exists in the public `SarahShinespark/arcana-disassembly` project. It is an excellent technical reference, but no explicit license was displayed when this repository was created. Its code is therefore not copied here. Arcana Map Studio only reimplements the required formats from observed behavior and the ROM tables.

Roadmap:

1. **partially delivered in 0.6** — HAL compressor, ROM reconstruction and map injection; BPS/IPS export and injection of the other databases still to do;
2. **advanced in 0.7.1** — chest and stair tables rebuilt with creation, deletion, relocation and external exit conversion; encounters still to be finalized;
3. **in progress** — perspective wall and corridor preview delivered in 0.3; extraction and rendering of real SNES tiles still to be done;
4. **delivered in 0.5 at project level — Item database**: editing and creation, statistics, prices, vendors and automatic availability in chests; ROM injection awaits the builder;
5. editing of towns, enemies, general statistics and dialogue;
6. **planned — Monster editor**: an RPG Maker-style enemy database allowing you to load a monster image (converted to the SNES tile format), configure stats, attacks, spells, elemental affinities and rewards, preview the sprite in the editor and inject the tables into the ROM;
7. verifiable ROM reconstruction pipeline from a locally provided dump;
8. **partially delivered** — undo/redo history and RPG Maker-style drawing tools; layers, advanced selection and validation remain to be done.

## Item database module — roadmap

The module takes the form of an RPG Maker-inspired database, accessible from the toolbar and organized by categories: items, weapons, armors, shields, accessories and cards. Version 0.5 delivers editing at the project level; writing these tables into a modified ROM is tied to the future builder.

### Editing and creation

- modify the name, description, category, identifier and logical icon of an existing item;
- duplicate an item as a starting point;
- create an item in a free ROM slot or extend the tables when the ROM builder is available;
- detect free identifiers, duplicates, text limits and broken references;
- keep creations in the project without modifying the original dump;
- immediately make any existing or created item available in the chest contents picker.

### Equipment statistics

For weapons, armors, shields and accessories, the editor will expose the statistics actually supported by the game:

- attack, defense and magic defense;
- attribute bonuses or penalties identified in the ROM tables;
- characters or classes allowed to equip the item;
- special effects, resistances and cursed properties once their format is confirmed;
- buy price, resale value and "unsellable" flag;
- comparison with another piece of equipment and preview of the stat impact.

### Vendors and availability

- list of shops and vendors present in towns;
- checkboxes to choose which vendors sell the item;
- default global price and optional per-vendor override if the game engine allows it;
- display order in each shop;
- availability conditions tied to chapter or progression where they exist;
- warning when a shop exceeds the capacity of its ROM table.

### Chest integration

The chest catalog will use a single source shared with the database. A creation or rename is therefore immediately visible in the event editor. References are stored by category and identifier, not only by name, to avoid breaking chests on rename.

### Technical steps

1. decode the price, statistics, equipment restriction and shop inventory tables;
2. extend `GameItem` and the project format with this data without breaking existing projects;
3. build the Database interface with search, filters, duplication and validation;
4. link vendors and the chest picker to the project catalog;
5. add identifier allocation and item creation;
6. inject the modified tables through the future ROM builder and verify the result in an emulator.

## Monster editor module — roadmap

A future module dedicated to battle enemies, on the model of the RPG Maker enemy database:

- enemy list with search, filters, duplication and deletion;
- editable statistics: HP, attack, defense, magic, speed and rewards (experience, gold, drops);
- **monster image loading**: import a PNG/BMP image from the editor, preview it in the battle layout, and — as a longer-term goal — convert it to the SNES 4bpp tile format for ROM injection;
- attack and AI configuration: normal attacks, spells, attack patterns and conditions;
- elemental affinities, resistances and status immunities where the ROM format allows;
- assignment to encounter groups and dungeon zones;
- storage in the project first, then table injection through the ROM builder;
- verification of the result in an emulator.

## Legality

The ROM, graphics, texts, music and other Arcana resources belong to their rightsholders. This repository must contain neither a ROM nor extracted content. The user must legally provide their own dump. The software produces projects and, eventually, patches that do not contain the full game.

## License

The original Arcana Map Studio code is distributed under the MIT license. This license does not apply to the Arcana game or its resources.
