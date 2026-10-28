from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import struct
import zlib

from .encounters import EncounterGroup, chapter_for_map, enemy_names, read_encounter_groups
from .items import GameItem, read_item_catalog

ROM_SIZE = 0x100000
KNOWN_SHA256 = "aac9d6f2b8408e4bbdc83ebbba755428caf8021fefbfac7220fb4c772abd9944"
KNOWN_CRC32 = 0xC891B297
MAP_POINTER_TABLE_PC = 0x18380
MAP_COUNT = 34
MAP_BANK = 0x13
MAP_WIDTH = 32
MAP_HEIGHT = 32
TREASURE_POINTER_TABLE_PC = 0xC0A99
TREASURE_CHAPTERS = 5
STAIR_POINTER_TABLE_PC = 0x1A5EB
MAP_NAMES = (
    "Balnea 1F", "Balnea 2F", "Draven Pass", "Crimson Valley", "Forest of Doubt",
    "Ice Mine", "Icicle Labyrinth", "Polar Labyrinth", "Stavery 1F (Chapter 4)",
    "Stavery 2F (Chapter 4)", "Stavery 3F (Chapter 4)", "Stavery 4F (Chapter 4)",
    "Stavery 5F (Chapter 4)", "Stavery 6F (Chapter 4)", "Stavery 7F (Chapter 4)",
    "Stavery 8F (Chapter 4)", "Stavery 9F (Chapter 4)", "Stavery 10F (Chapter 4)",
    "Stavery 11F (Chapter 4)", "Stavery 12F (Chapter 4)", "Bintel Castle", "A Tunnel",
    "Stavery 1F (Chapter 5)", "Stavery 2F (Chapter 5)", "Stavery 3F (Chapter 5)",
    "Stavery 4F (Chapter 5)", "Stavery 5F (Chapter 5)", "Stavery 6F (Chapter 5)",
    "Stavery 7F (Chapter 5)", "Stavery 8F (Chapter 5)", "Stavery 9F (Chapter 5)",
    "Stavery 10F (Chapter 5)", "Stavery 11F (Chapter 5)", "Stavery 12F (Chapter 5)",
)


class RomError(ValueError):
    pass


@dataclass(frozen=True)
class RomInfo:
    title: str
    sha256: str
    crc32: int
    checksum: int
    checksum_complement: int
    copier_header_size: int

    @property
    def is_known_dump(self) -> bool:
        return self.sha256 == KNOWN_SHA256


@dataclass(frozen=True)
class MapEntry:
    index: int
    name: str
    snes_address: int
    pc_offset: int


@dataclass(frozen=True)
class TreasureEntry:
    chapter: int
    map_index: int
    x: int
    y: int
    facing: int
    treasure_type: int
    value: int
    pc_offset: int


@dataclass(frozen=True)
class StairEntry:
    map_index: int
    x: int
    y: int
    destination: int
    target_x: int | None
    target_y: int | None
    direction: int | None
    location_pc_offset: int
    destination_pc_offset: int

    @property
    def is_dungeon_destination(self) -> bool:
        return bool(self.destination & 0x0100)


def snes_lorom_to_pc(address: int) -> int:
    bank = (address >> 16) & 0xFF
    offset = address & 0xFFFF
    if offset < 0x8000:
        raise RomError(f"Adresse LoROM invalide : ${address:06X}")
    return (bank & 0x7F) * 0x8000 + (offset & 0x7FFF)


def decompress_hal(data: bytes, offset: int, max_output: int = 0x100000) -> tuple[bytes, int]:
    source = offset
    output = bytearray()
    while True:
        if source >= len(data):
            raise RomError("Flux compressé tronqué")
        header = data[source]
        source += 1
        if header == 0xFF:
            return bytes(output), source - offset
        if header & 0xE0 == 0xE0:
            if source >= len(data):
                raise RomError("Commande longue tronquée")
            command = (header << 3) & 0xE0
            length = (((header & 0x03) << 8) | data[source]) + 1
            source += 1
        else:
            command = header & 0xE0
            length = (header & 0x1F) + 1
        if command == 0x00:
            end = source + length
            if end > len(data):
                raise RomError("Bloc littéral tronqué")
            output.extend(data[source:end])
            source = end
        elif command == 0x20:
            if source >= len(data):
                raise RomError("Répétition tronquée")
            output.extend([data[source]] * length)
            source += 1
        elif command == 0x40:
            if source + 2 > len(data):
                raise RomError("Répétition de mot tronquée")
            output.extend(data[source:source + 2] * length)
            source += 2
        elif command == 0x60:
            if source >= len(data):
                raise RomError("Séquence tronquée")
            start = data[source]
            output.extend((start + i) & 0xFF for i in range(length))
            source += 1
        elif command in (0x80, 0xA0, 0xC0):
            if source + 2 > len(data):
                raise RomError("Référence tronquée")
            position = (data[source] << 8) | data[source + 1]
            source += 2
            for i in range(length):
                read_at = position - i if command == 0xC0 else position + i
                if not 0 <= read_at < len(output):
                    raise RomError(f"Référence invalide vers ${read_at:04X}")
                value = output[read_at]
                if command == 0xA0:
                    value = int(f"{value:08b}"[::-1], 2)
                output.append(value)
        else:
            raise RomError(f"Commande HAL inconnue : ${command:02X}")
        if len(output) > max_output:
            raise RomError("Taille décompressée excessive")


class ArcanaRom:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        header_size = len(raw) % 0x8000
        if header_size not in (0, 512):
            raise RomError(f"Taille ROM inattendue : {len(raw)} octets")
        self.data = raw[header_size:]
        if len(self.data) != ROM_SIZE:
            raise RomError(f"Arcana USA doit faire {ROM_SIZE} octets sans en-tête")
        header = self.data[0x7FC0:0x8000]
        title = header[:21].decode("ascii", errors="replace").rstrip()
        if title != "ARCANA" or header[21] != 0x20:
            raise RomError("Le fichier n’est pas un ROM Arcana USA LoROM reconnu")
        digest = sha256(self.data).hexdigest()
        self.info = RomInfo(
            title=title,
            sha256=digest,
            crc32=zlib.crc32(self.data),
            checksum=struct.unpack_from("<H", header, 30)[0],
            checksum_complement=struct.unpack_from("<H", header, 28)[0],
            copier_header_size=header_size,
        )
        if (self.info.checksum ^ self.info.checksum_complement) != 0xFFFF:
            raise RomError("Checksum interne SNES invalide")
        self.maps = self._read_map_entries()
        self.items: tuple[GameItem, ...] = read_item_catalog(self.data)
        self.treasures = self._read_treasures()
        self.stairs = self._read_stairs()
        self.encounter_groups: tuple[EncounterGroup, ...] = read_encounter_groups(self.data)
        self.enemy_names: tuple[str, ...] = enemy_names(self.data)

    def encounters_for_map(self, map_index: int) -> tuple[EncounterGroup, ...]:
        chapter = chapter_for_map(map_index)
        return tuple(group for group in self.encounter_groups if group.chapter == chapter)

    def _read_map_entries(self) -> tuple[MapEntry, ...]:
        entries = []
        for index, name in enumerate(MAP_NAMES):
            pointer = struct.unpack_from("<H", self.data, MAP_POINTER_TABLE_PC + index * 2)[0]
            address = (MAP_BANK << 16) | pointer
            entries.append(MapEntry(index, name, address, snes_lorom_to_pc(address)))
        return tuple(entries)

    def _read_treasures(self) -> tuple[TreasureEntry, ...]:
        pointers = struct.unpack_from(f"<{TREASURE_CHAPTERS}H", self.data, TREASURE_POINTER_TABLE_PC)
        treasures = []
        for chapter, pointer in enumerate(pointers, 1):
            offset = snes_lorom_to_pc((0x18 << 16) | pointer)
            while struct.unpack_from("<H", self.data, offset)[0] != 0xFFFF:
                area, x, y, facing, treasure_type, value = struct.unpack_from("<6H", self.data, offset)
                treasures.append(TreasureEntry(chapter, area & 0xFF, x, y, facing, treasure_type, value, offset))
                offset += 12
        return tuple(treasures)

    def _read_stairs(self) -> tuple[StairEntry, ...]:
        pointers = struct.unpack_from(f"<{MAP_COUNT}H", self.data, STAIR_POINTER_TABLE_PC)
        stairs = []
        for map_index, pointer in enumerate(pointers):
            offset = snes_lorom_to_pc((0x03 << 16) | pointer)
            minimum_destination = len(self.data)
            while offset + 6 <= minimum_destination:
                x, y, destination_pointer = struct.unpack_from("<3H", self.data, offset)
                destination_offset = snes_lorom_to_pc((0x03 << 16) | destination_pointer)
                if destination_offset <= offset or destination_offset >= len(self.data):
                    break
                minimum_destination = min(minimum_destination, destination_offset)
                destination = struct.unpack_from("<H", self.data, destination_offset)[0]
                if destination & 0x0100:
                    destination, target_x, target_y, direction = struct.unpack_from("<4H", self.data, destination_offset)
                else:
                    target_x = target_y = direction = None
                stairs.append(StairEntry(map_index, x, y, destination, target_x, target_y, direction, offset, destination_offset))
                offset += 6
                if offset >= minimum_destination:
                    break
        return tuple(stairs)

    def stair_at(self, map_index: int, x: int, y: int) -> StairEntry | None:
        return next((entry for entry in self.stairs if entry.map_index == map_index and entry.x == x and entry.y == y), None)

    def stair_for_tile(self, map_index: int, x: int, y: int) -> StairEntry | None:
        exact = self.stair_at(map_index, x, y)
        if exact:
            return exact
        adjacent = [
            entry for entry in self.stairs
            if entry.map_index == map_index and abs(entry.x - x) + abs(entry.y - y) == 1
        ]
        return adjacent[0] if len(adjacent) == 1 else None

    def stair_properties(self, stair: StairEntry) -> dict[str, str | int]:
        if stair.is_dungeon_destination:
            destination_index = stair.destination & 0xFF
            direction_names = {0: "Nord", 2: "Est", 4: "Sud", 6: "Ouest"}
            return {
                "destination": self.maps[destination_index].name,
                "destination_map_index": destination_index,
                "x_cible": stair.target_x or 0,
                "y_cible": stair.target_y or 0,
                "direction": direction_names.get(stair.direction or 0, "Nord"),
                "rom_source_stair": stair.destination_pc_offset,
            }
        return {
            "destination": f"Ville / zone ${stair.destination:02X}",
            "destination_map_index": -1,
            "x_cible": 0,
            "y_cible": 0,
            "direction": "Nord",
            "rom_source_stair": stair.destination_pc_offset,
            "destination_externe": stair.destination,
        }

    def treasure_at(self, map_index: int, x: int, y: int) -> TreasureEntry | None:
        return next((entry for entry in self.treasures if entry.map_index == map_index and entry.x == x and entry.y == y), None)

    def treasure_properties(self, treasure: TreasureEntry) -> dict[str, str | int]:
        if treasure.treasure_type == 3:
            return {"contenu": "Gold", "quantité": treasure.value, "type_trésor": 3, "rom_source_treasure": treasure.pc_offset}
        categories = {0: {"Carte"}, 1: {"Objet"}, 2: {"Arme", "Armure", "Bouclier", "Accessoire"}}.get(treasure.treasure_type, set())
        item = next((candidate for candidate in self.items if candidate.item_id == treasure.value and candidate.category in categories), None)
        if not item:
            return {"contenu": f"Objet inconnu #{treasure.value:02X}", "quantité": 1, "type_trésor": treasure.treasure_type, "rom_source_treasure": treasure.pc_offset}
        return {
            "contenu": item.name,
            "quantité": 1,
            "item_key": item.key,
            "item_id": item.item_id,
            "catégorie": item.category,
            "type_trésor": treasure.treasure_type,
            "rom_source_treasure": treasure.pc_offset,
        }

    def read_map(self, index: int) -> bytes:
        entry = self.maps[index]
        output, _ = decompress_hal(self.data, entry.pc_offset, MAP_WIDTH * MAP_HEIGHT + 1)
        if len(output) != MAP_WIDTH * MAP_HEIGHT:
            raise RomError(f"Carte {entry.name} : {len(output)} octets au lieu de 1024")
        return output

    def unique_maps(self) -> dict[int, bytes]:
        return {entry.snes_address: self.read_map(entry.index) for entry in self.maps}
