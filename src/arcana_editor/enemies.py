from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import struct

ENEMY_NAMES_PC = 0x29FE9
ENEMY_RECORD_SIZE = 17
ENEMY_COUNT = 79
ENEMY_TABLE_SLOTS = 80
ENEMY_AFFINITY_PC = 0x2C92D
ENEMY_STR_PC = 0x2C9CD
ENEMY_INT_PC = 0x2CA95
ENEMY_ENDUR_PC = 0x2CB35
ENEMY_ALERT_PC = 0x2CBD5
ENEMY_ATK_ANIM_PC = 0x2CC75
ENEMY_EQ_ARMOR_PC = 0x2CD15
ENEMY_EQ_AMULET_PC = 0x2CDB5
ENEMY_HP_PC = 0x2CE55
ENEMY_EXP_PC = 0x2CEF5
ENEMY_GP_PC = 0x2CF95
ENEMY_LVL_PC = 0x2D035
ENEMY_SPELL_PC = 0x2D235

RACES = {
    0x00: "Aucune", 0x01: "Bête", 0x02: "Mort-vivant", 0x03: "Démon",
    0x04: "Dragon", 0x05: "Glace", 0x06: "Plante", 0x07: "Insecte",
}
ELEMENTS = {
    0x00: "Neutre", 0x01: "Feu", 0x02: "Eau", 0x03: "Vent",
    0x04: "Terre", 0x05: "Foudre", 0x06: "Lumière", 0x07: "Ténèbres",
}


@dataclass
class Enemy:
    enemy_id: int
    name: str
    hp: int = 0
    exp: int = 0
    gp: int = 0
    level: int = 0
    strength: int = 0
    intelligence: int = 0
    endurance: int = 0
    alertness: int = 0
    race: int = 0
    element: int = 0
    attack_animation: int = 0
    equip_armor: int = 0
    equip_amulet: int = 0
    spell: int = 0
    sprite: str = ""
    custom: bool = False
    enabled: bool = True

    @property
    def key(self) -> str:
        return f"{self.enemy_id:02X}"

    @property
    def display(self) -> str:
        return f"${self.enemy_id:02X} — {self.name}"

    def clone(self, **changes: object) -> "Enemy":
        return replace(self, **changes)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Enemy":
        fields = cls.__dataclass_fields__
        return cls(**{key: value for key, value in payload.items() if key in fields})


def _words(data: bytes, offset: int, count: int) -> tuple[int, ...]:
    return struct.unpack_from(f"<{count}H", data, offset)


def read_enemies(data: bytes) -> tuple[Enemy, ...]:
    names = []
    for index in range(ENEMY_TABLE_SLOTS):
        raw = data[ENEMY_NAMES_PC + index * ENEMY_RECORD_SIZE:ENEMY_NAMES_PC + (index + 1) * ENEMY_RECORD_SIZE]
        names.append(raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip())
    hp = _words(data, ENEMY_HP_PC, ENEMY_TABLE_SLOTS)
    exp = _words(data, ENEMY_EXP_PC, ENEMY_TABLE_SLOTS)
    gp = _words(data, ENEMY_GP_PC, ENEMY_TABLE_SLOTS)
    lvl = _words(data, ENEMY_LVL_PC, ENEMY_TABLE_SLOTS)
    strength = _words(data, ENEMY_STR_PC, ENEMY_TABLE_SLOTS)
    intelligence = _words(data, ENEMY_INT_PC, ENEMY_TABLE_SLOTS)
    endurance = _words(data, ENEMY_ENDUR_PC, ENEMY_TABLE_SLOTS)
    alertness = _words(data, ENEMY_ALERT_PC, ENEMY_TABLE_SLOTS)
    affinity = _words(data, ENEMY_AFFINITY_PC, ENEMY_TABLE_SLOTS)
    atk_anim = _words(data, ENEMY_ATK_ANIM_PC, ENEMY_TABLE_SLOTS)
    eq_armor = _words(data, ENEMY_EQ_ARMOR_PC, ENEMY_TABLE_SLOTS)
    eq_amulet = _words(data, ENEMY_EQ_AMULET_PC, ENEMY_TABLE_SLOTS)
    spells = data[ENEMY_SPELL_PC:ENEMY_SPELL_PC + ENEMY_TABLE_SLOTS]
    enemies = []
    for index in range(ENEMY_COUNT):
        name = names[index] or f"Ennemi ${index:02X}"
        word = affinity[index]
        enemies.append(Enemy(
            index, name,
            hp=hp[index], exp=exp[index], gp=gp[index], level=lvl[index],
            strength=strength[index], intelligence=intelligence[index],
            endurance=endurance[index], alertness=alertness[index],
            element=word & 0xFF, race=(word >> 8) & 0xFF,
            attack_animation=atk_anim[index], equip_armor=eq_armor[index],
            equip_amulet=eq_amulet[index], spell=spells[index] if index < len(spells) else 0,
        ))
    return tuple(enemies)
