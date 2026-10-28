from __future__ import annotations

from dataclasses import dataclass
import struct

ENEMY_NAMES_PC = 0x29FE9
ENEMY_RECORD_SIZE = 17
ENEMY_COUNT = 79
ENCOUNTER_POINTER_TABLE_PC = 0xC113D
ENCOUNTER_CHAPTERS = 5


@dataclass(frozen=True)
class EncounterGroup:
    chapter: int
    group_id: int
    zone: int
    enemy_ids: tuple[int, ...]
    enemy_names: tuple[str, ...]

    @property
    def display(self) -> str:
        enemies = ", ".join(self.enemy_names) if self.enemy_names else "Aucun ennemi"
        return f"Groupe ${self.group_id:X} — Zone ${self.zone:02X} — {enemies}"


def _enemy_names(data: bytes) -> tuple[str, ...]:
    names = []
    for index in range(ENEMY_COUNT):
        raw = data[ENEMY_NAMES_PC + index * ENEMY_RECORD_SIZE:ENEMY_NAMES_PC + (index + 1) * ENEMY_RECORD_SIZE]
        names.append(raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip() or f"Ennemi ${index:02X}")
    return tuple(names)


def read_encounter_groups(data: bytes) -> tuple[EncounterGroup, ...]:
    names = _enemy_names(data)
    pointers = struct.unpack_from(f"<{ENCOUNTER_CHAPTERS}H", data, ENCOUNTER_POINTER_TABLE_PC)
    groups = []
    for chapter, pointer in enumerate(pointers, 1):
        offset = 0xC0000 + (pointer & 0x7FFF)
        end = 0xC0000 + ((pointers[chapter] & 0x7FFF) if chapter < ENCOUNTER_CHAPTERS else 0x1270)
        group_id = 0
        while offset < end and group_id < 16:
            count = data[offset] & 0x0F
            if count == 0 or offset + count + 2 > end:
                break
            zone = data[offset + 1]
            enemy_ids = tuple(data[offset + 2:offset + 2 + count])
            enemy_names = tuple(names[enemy_id] if enemy_id < len(names) else f"Ennemi ${enemy_id:02X}" for enemy_id in enemy_ids)
            groups.append(EncounterGroup(chapter, group_id, zone, enemy_ids, enemy_names))
            offset += count + 2
            group_id += 1
    return tuple(groups)


def chapter_for_map(map_index: int) -> int:
    if map_index < 2:
        return 1
    if map_index < 5:
        return 2
    if map_index < 8:
        return 3
    if map_index < 22:
        return 4
    return 5
