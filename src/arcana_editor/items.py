from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import struct

ITEM_NAMES_PC = 0x2EE9A
ITEM_RECORD_SIZE = 20
ITEM_COUNT = 18
EQUIPMENT_NAMES_PC = 0x2D67D
EQUIPMENT_RECORD_SIZE = 17
EQUIPMENT_COUNT = 121
CARD_NAMES_PC = 0x2F038
CARD_RECORD_SIZE = 11
CARD_COUNT = 8
PRICE_WEAPONS_PC = 0x2DE86
PRICE_ARMOR_PC = 0x2DED8
PRICE_AMULETS_PC = 0x2DF28
PRICE_RINGS_PC = 0x2DF50
EQUIP_FLAGS_WEAPONS_PC = 0x2DF78
EQUIP_FLAGS_ARMOR_PC = 0x2DFA1
EQUIP_FLAGS_AMULETS_PC = 0x2DFC9
EQUIP_FLAGS_RINGS_PC = 0x2DFDD
WEAPON_POWER_PC = 0x2DFF1
ARMOR_DEFENSE_PC = 0x2E043
AMULET_DEFENSE_PC = 0x2E093
RING_DEFENSE_PC = 0x2E0BB
AMULET_MAGIC_DEFENSE_PC = 0x2E226
CHARACTER_BITS = (("Rooks", 0x01), ("Teefa", 0x02), ("Salah", 0x04), ("Darwin", 0x08), ("Axs", 0x10))
VENDORS = (
    "Outfitter — Chapitre 1",
    "Outfitter — Chapitre 2",
    "Outfitter — Chapitre 3",
    "Outfitter — Chapitre 4",
    "Outfitter — Chapitre 5",
)
EQUIPMENT_CATEGORIES = {"Arme", "Armure", "Bouclier", "Accessoire"}


@dataclass
class GameItem:
    category: str
    item_id: int
    name: str
    description: str = ""
    price: int = 0
    resale_value: int = 0
    attack: int = 0
    defense: int = 0
    magic_defense: int = 0
    strength: int = 0
    intelligence: int = 0
    endurance: int = 0
    agility: int = 0
    equippable_by: list[str] = field(default_factory=list)
    vendors: list[str] = field(default_factory=list)
    custom: bool = False
    enabled: bool = True

    @property
    def key(self) -> str:
        return f"{self.category}:{self.item_id:02X}"

    @property
    def display(self) -> str:
        return f"{self.name}  —  {self.category} #{self.item_id:02X}"

    @property
    def is_equipment(self) -> bool:
        return self.category in EQUIPMENT_CATEGORIES

    def clone(self, **changes: object) -> "GameItem":
        return replace(self, equippable_by=list(self.equippable_by), vendors=list(self.vendors), **changes)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "GameItem":
        fields = cls.__dataclass_fields__
        return cls(**{key: value for key, value in payload.items() if key in fields})


def _read_fixed_names(data: bytes, offset: int, record_size: int, count: int) -> list[str]:
    names = []
    for index in range(count):
        raw = data[offset + index * record_size:offset + (index + 1) * record_size]
        names.append(raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip())
    return names


def _price(data: bytes, category: str, item_id: int) -> int:
    if category == "Arme":
        offset = PRICE_WEAPONS_PC + item_id * 2
    elif category == "Armure":
        offset = PRICE_ARMOR_PC + (item_id - 41) * 2
    elif item_id <= 100:
        offset = PRICE_AMULETS_PC + (item_id - 81) * 2
    else:
        offset = PRICE_RINGS_PC + (item_id - 101) * 2
    return struct.unpack_from("<H", data, offset)[0]


def _equipment_stats(data: bytes, category: str, item_id: int) -> tuple[int, int, int, list[str]]:
    if category == "Arme":
        attack = struct.unpack_from("<H", data, WEAPON_POWER_PC + item_id * 2)[0]
        defense = magic_defense = 0
        flags = data[EQUIP_FLAGS_WEAPONS_PC + item_id]
    elif category == "Armure":
        attack = magic_defense = 0
        index = item_id - 41
        defense = struct.unpack_from("<H", data, ARMOR_DEFENSE_PC + index * 2)[0]
        flags = data[EQUIP_FLAGS_ARMOR_PC + index]
    elif item_id <= 100:
        attack = 0
        index = item_id - 81
        defense = struct.unpack_from("<H", data, AMULET_DEFENSE_PC + index * 2)[0]
        magic_defense = data[AMULET_MAGIC_DEFENSE_PC + index]
        flags = data[EQUIP_FLAGS_AMULETS_PC + index]
    else:
        attack = 0
        index = item_id - 101
        defense = struct.unpack_from("<H", data, RING_DEFENSE_PC + index * 2)[0]
        magic_defense = data[AMULET_MAGIC_DEFENSE_PC + 20 + index]
        flags = data[EQUIP_FLAGS_RINGS_PC + index]
    characters = [name for name, bit in CHARACTER_BITS if flags & bit]
    return attack, defense, magic_defense, characters


def read_item_catalog(data: bytes) -> tuple[GameItem, ...]:
    catalog = [GameItem("Monnaie", 0, "Gold")]
    consumables = _read_fixed_names(data, ITEM_NAMES_PC, ITEM_RECORD_SIZE, ITEM_COUNT)
    catalog.extend(GameItem("Objet", item_id, name) for item_id, name in enumerate(consumables) if item_id and name)
    equipment = _read_fixed_names(data, EQUIPMENT_NAMES_PC, EQUIPMENT_RECORD_SIZE, EQUIPMENT_COUNT)
    for item_id, name in enumerate(equipment):
        if not item_id or not name:
            continue
        if item_id <= 40:
            category = "Arme"
        elif item_id <= 80:
            category = "Armure"
        elif item_id <= 91:
            category = "Bouclier"
        else:
            category = "Accessoire"
        price = _price(data, category, item_id)
        attack, defense, magic_defense, characters = _equipment_stats(data, category, item_id)
        catalog.append(GameItem(
            category, item_id, name, price=price, resale_value=price // 2,
            attack=attack, defense=defense, magic_defense=magic_defense, equippable_by=characters,
        ))
    cards = _read_fixed_names(data, CARD_NAMES_PC, CARD_RECORD_SIZE, CARD_COUNT)
    catalog.extend(GameItem("Carte", item_id, name) for item_id, name in enumerate(cards) if item_id and name)
    return tuple(catalog)
