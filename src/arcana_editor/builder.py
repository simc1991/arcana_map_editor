from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

from .compression import compress_hal
from .encounters import chapter_for_map
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
    warnings: tuple[str, ...]


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


def _rebuild_treasures(project: ArcanaProject, rom: bytearray) -> int:
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
    return sum(len(entries) for entries in by_chapter.values())


def _rebuild_stairs(project: ArcanaProject, rom: bytearray) -> int:
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
    return total


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
    treasures_written = _rebuild_treasures(project, rom)
    stairs_written = _rebuild_stairs(project, rom)
    checksum = _update_checksum(rom)
    warnings = []
    if project.item_overrides:
        warnings.append("Les modifications de la base d’objets attendent encore l’injection des tables d’objets et de boutiques.")
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
    return BuildReport(output_path, len(address_to_data), compressed_total, available, checksum, treasures_written, stairs_written, tuple(warnings))
