from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import struct

SPELL_NAMES_PC = 0x2E340
SPELL_NAME_RECORD_SIZE = 22
SPELL_NAME_COUNT = 32
SPELL_ACCURACY_PC = 0x2EAF0
SPELL_POWER_PC = 0x2EB4B
SPELL_AFFINITY_PC = 0x2EC01
SPELL_STAT_COUNT = 91


@dataclass
class Spell:
    spell_id: int
    name: str
    accuracy: int = 0
    power: int = 0
    element: int = 0

    @property
    def key(self) -> str:
        return f"{self.spell_id:02X}"

    @property
    def display(self) -> str:
        return f"${self.spell_id:02X} — {self.name}" if self.name else f"${self.spell_id:02X}"

    def clone(self, **changes: object) -> "Spell":
        return replace(self, **changes)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Spell":
        fields = cls.__dataclass_fields__
        return cls(**{key: value for key, value in payload.items() if key in fields})


def read_spells(data: bytes) -> tuple[Spell, ...]:
    names = []
    for index in range(SPELL_NAME_COUNT):
        raw = data[SPELL_NAMES_PC + index * SPELL_NAME_RECORD_SIZE:SPELL_NAMES_PC + (index + 1) * SPELL_NAME_RECORD_SIZE]
        names.append(raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip())
    accuracy = data[SPELL_ACCURACY_PC:SPELL_ACCURACY_PC + SPELL_STAT_COUNT]
    power = struct.unpack_from(f"<{SPELL_STAT_COUNT}H", data, SPELL_POWER_PC)
    affinity = struct.unpack_from(f"<{SPELL_STAT_COUNT}H", data, SPELL_AFFINITY_PC)
    spells = []
    for index in range(SPELL_STAT_COUNT):
        spells.append(Spell(
            index, names[index] if index < len(names) else "",
            accuracy=accuracy[index], power=power[index], element=affinity[index],
        ))
    return tuple(spells)
