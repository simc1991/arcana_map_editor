from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

from .compression import compress_hal
from .encounters import ENCOUNTER_POINTER_TABLE_PC, chapter_for_map
from .enemies import (
    ENEMY_AFFINITY_PC,
    ENEMY_ALERT_PC,
    ENEMY_ATK_ANIM_PC,
    ENEMY_ENDUR_PC,
    ENEMY_EQ_AMULET_PC,
    ENEMY_EQ_ARMOR_PC,
    ENEMY_EXP_PC,
    ENEMY_GP_PC,
    ENEMY_HP_PC,
    ENEMY_INT_PC,
    ENEMY_LVL_PC,
    ENEMY_NAMES_PC,
    ENEMY_RECORD_SIZE,
    ENEMY_SPELL_PC,
    ENEMY_STR_PC,
    ENEMY_TABLE_SLOTS,
)
from .items import (
    AMULET_DEFENSE_PC,
    AMULET_MAGIC_DEFENSE_PC,
    ARMOR_DEFENSE_PC,
    CARD_NAMES_PC,
    CARD_RECORD_SIZE,
    CHARACTER_BITS,
    EQUIPMENT_NAMES_PC,
    EQUIPMENT_RECORD_SIZE,
    EQUIP_FLAGS_AMULETS_PC,
    EQUIP_FLAGS_ARMOR_PC,
    EQUIP_FLAGS_RINGS_PC,
    EQUIP_FLAGS_WEAPONS_PC,
    ITEM_NAMES_PC,
    ITEM_RECORD_SIZE,
    PRICE_WEAPONS_PC,
    RING_DEFENSE_PC,
    SHOP_MAX_ITEMS,
    SHOP_POINTER_TABLE_PC,
    SHOP_SIZE_TABLE_PC,
    VENDORS,
    WEAPON_POWER_PC,
    read_shop_lists,
)
from .project import ArcanaProject
from .rom import MAP_POINTER_TABLE_PC, STAIR_POINTER_TABLE_PC, TREASURE_POINTER_TABLE_PC, RomError, decompress_hal

TREASURE_RELOCATION_START = 0xC5B90
TREASURE_RELOCATION_END = 0xC8000
STAIR_RELOCATION_START = 0x1EDFE
STAIR_RELOCATION_END = 0x20000


@dataclass(frozen=True)
class BuildReport:
    output_path: Path
    maps_written: int
    compressed_bytes: int
    available_bytes: int
    checksum: int
    treasures_written: int
    stairs_written: int
    items_written: int = 0
    shop_slots_written: int = 0
    encounters_written: int = 0
    enemies_written: int = 0
    spells_written: int = 0
    warnings: tuple[str, ...] = ()


def _update_checksum(rom: bytearray) -> int:
    rom[0x7FDC:0x7FE0] = b"\x00\x00\x00\x00"
    checksum = (sum(rom) + 0x1FE) & 0xFFFF
    struct.pack_into("<HH", rom, 0x7FDC, checksum ^ 0xFFFF, checksum)
    return checksum


def _event_position(key: str) -> tuple[int, int]:
    _, x, y = key.split(":")
    return int(x), int(y)


def _treasure_payload(properties: dict) -> tuple[int, int]:
    category = properties.get("catégorie")
    if properties.get("contenu") == "Gold" or category == "Monnaie":
        value = int(properties.get("quantité", 0))
        if not 0 <= value <= 0xFFFF:
            raise RomError("Le montant Gold d’un coffre doit être compris entre 0 et 65535")
        return 3, value
    treasure_type = {"Carte": 0, "Objet": 1, "Arme": 2, "Armure": 2, "Bouclier": 2, "Accessoire": 2}.get(str(category))
    if treasure_type is None:
        raise RomError(f"Catégorie de récompense inconnue : {category}")
    value = int(properties["item_id"])
    if not 0 <= value <= 0xFF:
        raise RomError("L’identifiant d’objet du coffre est hors limites")
    return treasure_type, value


def _rebuild_treasures(project: ArcanaProject, rom: bytearray) -> tuple[int, int]:
    overrides = {}
    deleted_sources = set()
    new_entries = []
    for key, metadata in project.event_metadata.items():
        properties = metadata.get("properties", {})
        if metadata.get("deleted") and properties.get("rom_source_treasure") is not None:
            deleted_sources.add(int(properties["rom_source_treasure"]))
            continue
        if "contenu" not in properties:
            continue
        x, y = _event_position(key)
        source = properties.get("rom_source_treasure")
        record = (int(metadata.get("map_index", 0)), x, y, int(properties.get("orientation", 0)), *_treasure_payload(properties))
        if source is None:
            new_entries.append(record)
        else:
            overrides[int(source)] = record
    by_chapter = {chapter: [] for chapter in range(1, 6)}
    used_sources = set()
    for original in project.rom.treasures:
        if original.pc_offset in deleted_sources:
            continue
        if original.pc_offset in overrides:
            map_index, x, y, facing, treasure_type, value = overrides[original.pc_offset]
            used_sources.add(original.pc_offset)
        else:
            map_index, x, y, facing, treasure_type, value = original.map_index, original.x, original.y, original.facing, original.treasure_type, original.value
        by_chapter[chapter_for_map(map_index)].append((map_index, x, y, facing, treasure_type, value))
    for record in new_entries:
        by_chapter[chapter_for_map(record[0])].append(record)
    missing = set(overrides) - used_sources
    if missing:
        raise RomError("Un coffre modifié ne correspond plus à une entrée ROM source")
    cursor = TREASURE_RELOCATION_START
    for chapter in range(1, 6):
        pointer = 0x8000 | (cursor & 0x7FFF)
        struct.pack_into("<H", rom, TREASURE_POINTER_TABLE_PC + (chapter - 1) * 2, pointer)
        for map_index, x, y, facing, treasure_type, value in by_chapter[chapter]:
            if not 0 <= x < 32 or not 0 <= y < 32:
                raise RomError("Coordonnées de coffre hors limites")
            if cursor + 12 > TREASURE_RELOCATION_END:
                raise RomError("La banque $18 ne contient plus assez d’espace pour les coffres")
            struct.pack_into("<6H", rom, cursor, 0x0100 | map_index, x, y, facing, treasure_type, value)
            cursor += 12
        if cursor + 2 > TREASURE_RELOCATION_END:
            raise RomError("La banque $18 ne contient plus assez d’espace pour les coffres")
        struct.pack_into("<H", rom, cursor, 0xFFFF)
        cursor += 2
    return sum(len(entries) for entries in by_chapter.values()), cursor


def _rebuild_stairs(project: ArcanaProject, rom: bytearray) -> tuple[int, int]:
    direction_values = {"Nord": 0, "Est": 2, "Sud": 4, "Ouest": 6}
    overrides = {}
    deleted_sources = set()
    additions: dict[int, list[tuple[int, int, int, int, int, int]]] = {}
    for key, metadata in project.event_metadata.items():
        properties = metadata.get("properties", {})
        if metadata.get("deleted") and properties.get("rom_source_stair") is not None:
            deleted_sources.add(int(properties["rom_source_stair"]))
            continue
        if "destination_map_index" not in properties:
            continue
        x, y = _event_position(key)
        map_index = int(metadata.get("map_index", 0))
        destination_index = int(properties["destination_map_index"])
        if destination_index < 0:
            destination = int(properties.get("destination_externe", 0))
            target_x = target_y = direction = 0
        else:
            if not 0 <= destination_index < len(project.rom.maps):
                raise RomError("Carte de destination d’escalier hors limites")
            target_x, target_y = int(properties.get("x_cible", 0)), int(properties.get("y_cible", 0))
            if not 0 <= target_x < 32 or not 0 <= target_y < 32:
                raise RomError("Coordonnées d’arrivée d’escalier hors limites")
            direction = direction_values.get(str(properties.get("direction", "Nord")))
            if direction is None:
                raise RomError("Orientation d’escalier inconnue")
            destination = 0x0100 | destination_index
        source = properties.get("rom_source_stair")
        if source is None:
            additions.setdefault(map_index, []).append((x, y, destination, target_x, target_y, direction))
        else:
            original = next((entry for entry in project.rom.stairs if entry.destination_pc_offset == int(source)), None)
            if original is None:
                raise RomError("La source d’un escalier modifié est introuvable")
            overrides[int(source)] = (original.x, original.y, destination, target_x, target_y, direction)
    old_pointers = struct.unpack_from(f"<{len(project.rom.maps)}H", project.rom.data, STAIR_POINTER_TABLE_PC)
    groups: dict[int, list[int]] = {}
    for map_index, pointer in enumerate(old_pointers):
        groups.setdefault(pointer, []).append(map_index)
    cursor = STAIR_RELOCATION_START
    total = 0
    for _, map_indices in groups.items():
        representative = map_indices[0]
        original_entries = []
        seen_destinations = set()
        for stair in project.rom.stairs:
            if stair.map_index != representative or stair.destination_pc_offset in seen_destinations:
                continue
            seen_destinations.add(stair.destination_pc_offset)
            if stair.destination_pc_offset in deleted_sources:
                continue
            if stair.destination_pc_offset in overrides:
                original_entries.append(overrides.pop(stair.destination_pc_offset))
            else:
                original_entries.append((stair.x, stair.y, stair.destination, stair.target_x or 0, stair.target_y or 0, stair.direction or 0))
        for map_index in map_indices:
            original_entries.extend(additions.get(map_index, []))
        location_size = len(original_entries) * 6
        block_size = location_size + len(original_entries) * 8
        if cursor + block_size > STAIR_RELOCATION_END:
            raise RomError("La banque $03 ne contient plus assez d’espace pour les escaliers")
        block_pointer = 0x8000 | (cursor & 0x7FFF)
        for map_index in map_indices:
            struct.pack_into("<H", rom, STAIR_POINTER_TABLE_PC + map_index * 2, block_pointer)
        destination_cursor = cursor + location_size
        for index, (x, y, destination, target_x, target_y, direction) in enumerate(original_entries):
            destination_pointer = 0x8000 | (destination_cursor & 0x7FFF)
            struct.pack_into("<3H", rom, cursor + index * 6, x, y, destination_pointer)
            struct.pack_into("<4H", rom, destination_cursor, destination, target_x, target_y, direction)
            destination_cursor += 8
        cursor += block_size
        total += len(original_entries)
    if overrides:
        raise RomError("Un escalier modifié ne correspond plus à une entrée ROM source")
    return total, cursor


def _rebuild_encounters(project: ArcanaProject, rom: bytearray, cursor: int) -> tuple[int, int]:
    by_chapter: dict[int, list] = {chapter: [] for chapter in range(1, 6)}
    for group in project.encounter_groups:
        if not group.enemy_ids:
            raise RomError(f"Le groupe de rencontres {group.chapter}:{group.group_id:X} est vide")
        if not 0 <= group.group_id <= 0x0F or len(group.enemy_ids) > 0x0F:
            raise RomError("Un groupe de rencontres dépasse la capacité du moteur")
        if not 0 <= group.zone <= 0xFF:
            raise RomError("Zone de rencontre hors limites")
        if any(not 0 <= enemy_id <= 0xFF for enemy_id in group.enemy_ids):
            raise RomError("Un ennemi de groupe de rencontres est hors limites")
        by_chapter[group.chapter].append(group)
    total = 0
    for chapter in range(1, 6):
        pointer = 0x8000 | (cursor & 0x7FFF)
        struct.pack_into("<H", rom, ENCOUNTER_POINTER_TABLE_PC + (chapter - 1) * 2, pointer)
        for group in by_chapter[chapter]:
            entry = bytes([group.flags | len(group.enemy_ids), group.zone, *group.enemy_ids])
            if cursor + len(entry) + 1 > TREASURE_RELOCATION_END:
                raise RomError("La banque $18 ne contient plus assez d’espace pour les rencontres")
            rom[cursor:cursor + len(entry)] = entry
            cursor += len(entry)
            total += 1
        rom[cursor] = 0x00
        cursor += 1
    return total, cursor


def _rebuild_shops(project: ArcanaProject, rom: bytearray, cursor: int) -> tuple[int, int]:
    original_lists = read_shop_lists(project.rom.data)
    total = 0
    for chapter, label in enumerate(VENDORS):
        assigned = {item.item_id for item in project.items if item.is_equipment and label in item.vendors}
        previous = original_lists[chapter]
        ordered = [item_id for item_id in previous if item_id in assigned]
        ordered += sorted(assigned - set(previous))
        if len(ordered) > SHOP_MAX_ITEMS:
            raise RomError(f"La boutique « {label} » dépasse la capacité de {SHOP_MAX_ITEMS} objets")
        if cursor + 2 * len(ordered) > STAIR_RELOCATION_END:
            raise RomError("La banque $03 ne contient plus assez d’espace pour les boutiques")
        pointer = 0x8000 | (cursor & 0x7FFF)
        struct.pack_into("<H", rom, SHOP_POINTER_TABLE_PC + chapter * 2, pointer)
        struct.pack_into("<H", rom, SHOP_SIZE_TABLE_PC + chapter * 2, len(ordered))
        if ordered:
            struct.pack_into(f"<{len(ordered)}H", rom, cursor, *ordered)
        cursor += 2 * len(ordered)
        total += len(ordered)
    return total, cursor


def _item_name_table(category: str) -> tuple[int, int, int] | None:
    if category == "Objet":
        return ITEM_NAMES_PC, ITEM_RECORD_SIZE, 17
    if category == "Carte":
        return CARD_NAMES_PC, CARD_RECORD_SIZE, 7
    if category in ("Arme", "Armure", "Bouclier", "Accessoire"):
        return EQUIPMENT_NAMES_PC, EQUIPMENT_RECORD_SIZE, 120
    return None


def _expected_category(item_id: int) -> str:
    if item_id <= 40:
        return "Arme"
    if item_id <= 80:
        return "Armure"
    if item_id <= 91:
        return "Bouclier"
    return "Accessoire"


def _inject_items(project: ArcanaProject, rom: bytearray, warnings: list[str]) -> int:
    injected = 0
    warned_attributes = False
    warned_vendors = False
    warned_category = False
    for item in project.items:
        table = _item_name_table(item.category)
        if table is None:
            continue
        base, record_size, max_id = table
        if not 1 <= item.item_id <= max_id:
            warnings.append(f"{item.display} : identifiant hors des tables ROM — conservé dans le projet uniquement.")
            continue
        try:
            name_bytes = item.name.encode("ascii")
        except UnicodeEncodeError:
            raise RomError(f"Le nom de « {item.name} » contient des caractères non injectables dans le ROM")
        if len(name_bytes) > record_size:
            raise RomError(f"Le nom « {item.name} » dépasse la limite de {record_size} caractères du ROM")
        offset = base + item.item_id * record_size
        rom[offset:offset + record_size] = name_bytes.ljust(record_size, b"\x00")
        if item.is_equipment:
            if not warned_category and item.category != _expected_category(item.item_id):
                warnings.append("La catégorie d’un équipement ne correspond pas à la plage de son identifiant — le jeu la détermine par l’identifiant.")
                warned_category = True
            if not 0 <= item.price <= 0xFFFF or not 0 <= item.defense <= 0xFFFF or not 0 <= item.attack <= 0xFFFF:
                raise RomError(f"Statistiques hors limites pour {item.name}")
            if not 0 <= item.magic_defense <= 0xFF:
                raise RomError(f"Défense magique hors limites pour {item.name}")
            struct.pack_into("<H", rom, PRICE_WEAPONS_PC + item.item_id * 2, item.price)
            flags = 0
            for character, bit in CHARACTER_BITS:
                if character in item.equippable_by:
                    flags |= bit
            if item.item_id <= 40:
                struct.pack_into("<H", rom, WEAPON_POWER_PC + item.item_id * 2, item.attack)
                rom[EQUIP_FLAGS_WEAPONS_PC + item.item_id] = flags
            elif item.item_id <= 80:
                index = item.item_id - 41
                struct.pack_into("<H", rom, ARMOR_DEFENSE_PC + index * 2, item.defense)
                rom[EQUIP_FLAGS_ARMOR_PC + index] = flags
            elif item.item_id <= 100:
                index = item.item_id - 81
                struct.pack_into("<H", rom, AMULET_DEFENSE_PC + index * 2, item.defense)
                rom[AMULET_MAGIC_DEFENSE_PC + index] = item.magic_defense
                rom[EQUIP_FLAGS_AMULETS_PC + index] = flags
            else:
                index = item.item_id - 101
                struct.pack_into("<H", rom, RING_DEFENSE_PC + index * 2, item.defense)
                rom[AMULET_MAGIC_DEFENSE_PC + 20 + index] = item.magic_defense
                rom[EQUIP_FLAGS_RINGS_PC + index] = flags
            if not warned_attributes and any((item.strength, item.intelligence, item.endurance, item.agility)):
                warnings.append("Les bonus de caractéristiques des équipements ne sont pas encore localisés dans le ROM — conservés dans le projet.")
                warned_attributes = True
        elif item.vendors and not warned_vendors:
            warnings.append("Les vendeurs ne proposent que des équipements — les affectations sur les objets/cartes sont conservées dans le projet.")
            warned_vendors = True
        injected += 1
    return injected


def _inject_enemy_sprite(rom: bytearray, enemy) -> None:
    from .sprites import (
        ENEMY_PALETTE_BANK_PC,
        ENEMY_PALETTE_TABLE_PC,
        OAM_ENTRY_SIZE,
        _lorom_pc,
        _parse_frame_entries,
        enemy_frame_table,
    )
    import struct as _struct

    tiles = bytes.fromhex(enemy.sprite_tiles)
    colors = bytes.fromhex(enemy.sprite_palette)
    pointer = _struct.unpack_from("<H", rom, ENEMY_PALETTE_TABLE_PC + enemy.enemy_id * 2)[0]
    header = _lorom_pc((rom[ENEMY_PALETTE_BANK_PC + enemy.enemy_id] << 16) | pointer)
    palette_size = _struct.unpack_from("<H", rom, header + 2)[0]
    gfx_offset = header + 4 + palette_size
    gfx_address = rom[gfx_offset] | (rom[gfx_offset + 1] << 8) | (rom[gfx_offset + 2] << 16)
    gfx_pc = _lorom_pc(gfx_address)
    destination = _struct.unpack_from("<H", rom, gfx_pc)[0]
    base_tile = max(0, (destination - 0x6000) // 16)
    original, used = decompress_hal(rom, gfx_pc + 2, 0x20000)
    if len(tiles) > len(original):
        raise RomError(f"Le sprite de {enemy.name} dépasse la taille graphique originale ({len(tiles)} > {len(original)} octets)")
    padded = tiles.ljust(len(original), b"\x00")
    compressed = compress_hal(padded)
    if len(compressed) > used:
        raise RomError(f"Le sprite compressé de {enemy.name} ne tient pas dans l’emplacement du ROM ({len(compressed)} > {used} octets)")
    rom[gfx_pc + 2:gfx_pc + 2 + used] = compressed.ljust(used, b"\x00")
    if len(colors) >= 2:
        limit = min(len(colors), palette_size)
        rom[header + 4:header + 4 + limit] = colors[:limit]
    frame_pointer = next((p for p in enemy_frame_table(rom, enemy.enemy_id) if p < 0xC000), None)
    if frame_pointer is None:
        raise RomError(f"Aucune frame propre trouvée pour {enemy.name}")
    frame_pc = _lorom_pc((0x09 << 16) | frame_pointer)
    original_entries = _parse_frame_entries(rom, frame_pc)
    span = len(original_entries) * OAM_ENTRY_SIZE
    columns = max(1, (enemy.sprite_w + 15) // 16)
    rows = max(1, (enemy.sprite_h + 15) // 16)
    if columns * rows * OAM_ENTRY_SIZE > span:
        raise RomError(f"Le cadre OAM de {enemy.name} est trop petit pour l’image ({columns}x{rows})")
    attr = original_entries[0][4] if original_entries else 0x32
    entries = bytearray()
    for row in range(rows):
        for column in range(columns):
            tile = base_tile + row * 32 + column * 2
            x = -columns * 8 + column * 16
            y = -rows * 8 + row * 16
            flags = 0x03 if row == rows - 1 and column == columns - 1 else 0x01
            entries += _struct.pack("<5B", flags, x & 0xFF, y & 0xFF, tile & 0xFF, attr)
    rom[frame_pc:frame_pc + len(entries)] = entries


def _inject_enemies(project: ArcanaProject, rom: bytearray, warnings: list[str]) -> int:
    injected = 0
    for enemy in project.enemies:
        if enemy.enemy_id >= ENEMY_TABLE_SLOTS:
            warnings.append(f"{enemy.display} : identifiant hors des tables de monstres du ROM — conservé dans le projet uniquement.")
            continue
        try:
            name_bytes = enemy.name.encode("ascii")
        except UnicodeEncodeError:
            raise RomError(f"Le nom de « {enemy.name} » contient des caractères non injectables dans le ROM")
        if len(name_bytes) > ENEMY_RECORD_SIZE:
            raise RomError(f"Le nom « {enemy.name} » dépasse la limite de {ENEMY_RECORD_SIZE} caractères du ROM")
        offset = ENEMY_NAMES_PC + enemy.enemy_id * ENEMY_RECORD_SIZE
        rom[offset:offset + ENEMY_RECORD_SIZE] = name_bytes.ljust(ENEMY_RECORD_SIZE, b"\x00")
        stats = (
            (ENEMY_HP_PC, enemy.hp), (ENEMY_EXP_PC, enemy.exp), (ENEMY_GP_PC, enemy.gp),
            (ENEMY_LVL_PC, enemy.level), (ENEMY_STR_PC, enemy.strength), (ENEMY_INT_PC, enemy.intelligence),
            (ENEMY_ENDUR_PC, enemy.endurance), (ENEMY_ALERT_PC, enemy.alertness),
            (ENEMY_ATK_ANIM_PC, enemy.attack_animation), (ENEMY_EQ_ARMOR_PC, enemy.equip_armor),
            (ENEMY_EQ_AMULET_PC, enemy.equip_amulet),
            (ENEMY_AFFINITY_PC, (enemy.race << 8) | enemy.element),
        )
        for base, value in stats:
            if not 0 <= value <= 0xFFFF:
                raise RomError(f"Statistique hors limites pour {enemy.name}")
            struct.pack_into("<H", rom, base + enemy.enemy_id * 2, value)
        if not 0 <= enemy.spell <= 0xFF:
            raise RomError(f"Sort hors limites pour {enemy.name}")
        rom[ENEMY_SPELL_PC + enemy.enemy_id] = enemy.spell
        if enemy.sprite_tiles:
            _inject_enemy_sprite(rom, enemy)
        injected += 1
    referenced = {enemy_id for group in project.encounter_groups for enemy_id in group.enemy_ids}
    if any(enemy_id >= ENEMY_TABLE_SLOTS for enemy_id in referenced):
        warnings.append("Un groupe de rencontres référence un monstre hors des tables du ROM — ses statistiques ne seront pas injectées.")
    return injected


def _inject_spells(project: ArcanaProject, rom: bytearray) -> int:
    from .spells import (
        SPELL_ACCURACY_PC,
        SPELL_AFFINITY_PC,
        SPELL_NAME_COUNT,
        SPELL_NAME_RECORD_SIZE,
        SPELL_NAMES_PC,
        SPELL_POWER_PC,
        SPELL_STAT_COUNT,
    )
    injected = 0
    for spell in project.spells:
        if spell.spell_id >= SPELL_STAT_COUNT:
            continue
        if spell.spell_id < SPELL_NAME_COUNT and spell.name:
            try:
                name_bytes = spell.name.encode("ascii")
            except UnicodeEncodeError:
                raise RomError(f"Le nom de sort « {spell.name} » contient des caractères non injectables")
            if len(name_bytes) >= SPELL_NAME_RECORD_SIZE:
                raise RomError(f"Le nom de sort « {spell.name} » dépasse {SPELL_NAME_RECORD_SIZE - 1} caractères")
            offset = SPELL_NAMES_PC + spell.spell_id * SPELL_NAME_RECORD_SIZE
            rom[offset:offset + SPELL_NAME_RECORD_SIZE] = name_bytes.ljust(SPELL_NAME_RECORD_SIZE - 1, b" ") + b"\x00"
        if not 0 <= spell.accuracy <= 0xFF or not 0 <= spell.power <= 0xFFFF or not 0 <= spell.element <= 0xFFFF:
            raise RomError(f"Statistiques hors limites pour le sort {spell.display}")
        rom[SPELL_ACCURACY_PC + spell.spell_id] = spell.accuracy
        struct.pack_into("<H", rom, SPELL_POWER_PC + spell.spell_id * 2, spell.power)
        struct.pack_into("<H", rom, SPELL_AFFINITY_PC + spell.spell_id * 2, spell.element)
        injected += 1
    return injected


def build_rom(project: ArcanaProject, destination: str | Path) -> BuildReport:
    output_path = Path(destination)
    source = project.rom
    rom = bytearray(source.data)
    unique_offsets = sorted({entry.pc_offset for entry in source.maps})
    start = unique_offsets[0]
    last_offset = unique_offsets[-1]
    _, last_size = decompress_hal(source.data, last_offset)
    end = last_offset + last_size
    address_to_data = {entry.snes_address: compress_hal(bytes(project.maps[entry.snes_address])) for entry in source.maps}
    compressed_total = sum(len(data) for data in address_to_data.values())
    available = end - start
    if compressed_total > available:
        raise RomError(f"Les cartes compressées occupent {compressed_total} octets, mais seulement {available} sont disponibles dans la banque $13.")
    rom[start:end] = b"\xFF" * available
    cursor = start
    relocated = {}
    offset_by_address = {entry.snes_address: entry.pc_offset for entry in source.maps}
    for old_address in sorted(address_to_data, key=offset_by_address.get):
        data = address_to_data[old_address]
        relocated[old_address] = 0x8000 | (cursor & 0x7FFF)
        rom[cursor:cursor + len(data)] = data
        cursor += len(data)
    for entry in source.maps:
        struct.pack_into("<H", rom, MAP_POINTER_TABLE_PC + entry.index * 2, relocated[entry.snes_address])
    treasures_written, bank18_cursor = _rebuild_treasures(project, rom)
    encounters_written, _ = _rebuild_encounters(project, rom, bank18_cursor)
    stairs_written, bank03_cursor = _rebuild_stairs(project, rom)
    shop_slots_written, _ = _rebuild_shops(project, rom, bank03_cursor)
    warnings: list[str] = []
    items_written = _inject_items(project, rom, warnings)
    enemies_written = _inject_enemies(project, rom, warnings)
    spells_written = _inject_spells(project, rom)
    checksum = _update_checksum(rom)
    output_path.write_bytes(rom)
    verification = output_path.read_bytes()
    if len(verification) != len(source.data):
        raise RomError("La taille du ROM construit est invalide")
    for entry in source.maps:
        pointer = struct.unpack_from("<H", verification, MAP_POINTER_TABLE_PC + entry.index * 2)[0]
        offset = (0x13 & 0x7F) * 0x8000 + (pointer & 0x7FFF)
        decoded, _ = decompress_hal(verification, offset, 1025)
        if decoded != bytes(project.maps[entry.snes_address]):
            raise RomError(f"Échec de vérification de la carte {entry.name}")
    return BuildReport(
        output_path, len(address_to_data), compressed_total, available, checksum,
        treasures_written, stairs_written, items_written, shop_slots_written,
        encounters_written, enemies_written, spells_written, tuple(warnings),
    )
