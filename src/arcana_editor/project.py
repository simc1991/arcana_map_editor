from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from .events import MapEvent, default_properties, event_key
from .items import GameItem
from .rendering import event_kind
from .rom import ArcanaRom, MAP_HEIGHT, MAP_WIDTH, RomError

PROJECT_FORMAT = 5


@dataclass
class ArcanaProject:
    rom: ArcanaRom
    maps: dict[int, bytearray]
    event_metadata: dict[str, dict] = field(default_factory=dict)
    item_overrides: dict[str, dict] = field(default_factory=dict)
    path: Path | None = None
    dirty: bool = False

    @classmethod
    def from_rom(cls, rom: ArcanaRom) -> "ArcanaProject":
        return cls(rom=rom, maps={address: bytearray(data) for address, data in rom.unique_maps().items()})

    def map_for_entry(self, index: int) -> bytearray:
        return self.maps[self.rom.maps[index].snes_address]

    @property
    def items(self) -> tuple[GameItem, ...]:
        merged = {item.key: item.clone() for item in self.rom.items}
        for key, payload in self.item_overrides.items():
            item = GameItem.from_dict(payload)
            if item.enabled:
                merged[key] = item
            else:
                merged.pop(key, None)
        return tuple(sorted(merged.values(), key=lambda item: (item.category, item.item_id, item.name.casefold())))

    def save_item(self, item: GameItem, old_key: str | None = None) -> None:
        if not item.name.strip():
            raise ValueError("Le nom de l’objet est obligatoire")
        if not 0 <= item.item_id <= 0xFF:
            raise ValueError("L’identifiant doit être compris entre 0 et 255")
        if old_key and old_key != item.key:
            self.item_overrides.pop(old_key, None)
        collision = next((candidate for candidate in self.items if candidate.key == item.key and candidate.key != old_key), None)
        if collision:
            raise ValueError(f"L’identifiant {item.key} est déjà utilisé par {collision.name}")
        self.item_overrides[item.key] = item.to_dict()
        self.dirty = True

    def next_item_id(self, category: str) -> int:
        used = {item.item_id for item in self.items if item.category == category}
        for item_id in range(1, 0x100):
            if item_id not in used:
                return item_id
        raise ValueError(f"Aucun identifiant libre dans la catégorie {category}")

    def remove_custom_item(self, key: str) -> None:
        item = next((candidate for candidate in self.items if candidate.key == key), None)
        if not item or not item.custom:
            raise ValueError("Seuls les objets créés dans le projet peuvent être supprimés")
        payload = item.to_dict()
        payload["enabled"] = False
        self.item_overrides[key] = payload
        self.dirty = True

    def set_tile(self, entry_index: int, x: int, y: int, value: int) -> None:
        if not 0 <= x < MAP_WIDTH or not 0 <= y < MAP_HEIGHT:
            raise IndexError((x, y))
        if not 0 <= value <= 0xFF:
            raise ValueError(value)
        tiles = self.map_for_entry(entry_index)
        position = y * MAP_WIDTH + x
        if tiles[position] != value:
            tiles[position] = value
            self.dirty = True

    def replace_map(self, entry_index: int, tiles: bytes | bytearray) -> None:
        if len(tiles) != MAP_WIDTH * MAP_HEIGHT:
            raise ValueError("Une carte doit contenir exactement 1024 tuiles")
        address = self.rom.maps[entry_index].snes_address
        if self.maps[address] != tiles:
            self.maps[address] = bytearray(tiles)
            self.dirty = True

    def events_for_entry(self, entry_index: int) -> list[MapEvent]:
        address = self.rom.maps[entry_index].snes_address
        events = []
        for position, value in enumerate(self.map_for_entry(entry_index)):
            if not event_kind(value):
                continue
            x, y = position % MAP_WIDTH, position // MAP_WIDTH
            metadata = self.event_metadata.get(event_key(address, x, y), {})
            properties = metadata.get("properties")
            if properties is None and event_kind(value) == "Coffre":
                treasure = self.rom.treasure_at(entry_index, x, y)
                properties = self.rom.treasure_properties(treasure) if treasure else default_properties(value)
            if properties is None and event_kind(value) in ("Escalier", "Transition", "Porte / événement"):
                stair = self.rom.stair_for_tile(entry_index, x, y)
                properties = self.rom.stair_properties(stair) if stair else default_properties(value)
            events.append(MapEvent(
                map_address=address,
                x=x,
                y=y,
                value=value,
                name=str(metadata.get("name", "")),
                notes=str(metadata.get("notes", "")),
                properties=dict(properties if properties is not None else default_properties(value)),
            ))
        return events

    def event_at(self, entry_index: int, x: int, y: int) -> MapEvent | None:
        return next((event for event in self.events_for_entry(entry_index) if event.x == x and event.y == y), None)

    def update_event(self, entry_index: int, event: MapEvent, old_x: int, old_y: int) -> None:
        address = self.rom.maps[entry_index].snes_address
        if event.map_address != address:
            raise ValueError("L’événement appartient à une autre carte")
        existing = self.event_at(entry_index, event.x, event.y)
        if existing and (event.x, event.y) != (old_x, old_y):
            raise ValueError("Un événement existe déjà à cette position")
        old_key = event_key(address, old_x, old_y)
        new_key = event_key(address, event.x, event.y)
        if (old_x, old_y) != (event.x, event.y):
            self.set_tile(entry_index, old_x, old_y, 0x30)
            self.event_metadata.pop(old_key, None)
        self.set_tile(entry_index, event.x, event.y, event.value)
        self.event_metadata[new_key] = {
            "map_index": entry_index,
            "name": event.name,
            "notes": event.notes,
            "properties": event.properties,
        }
        self.dirty = True

    def remove_event(self, entry_index: int, x: int, y: int) -> None:
        address = self.rom.maps[entry_index].snes_address
        existing = self.event_at(entry_index, x, y)
        key = event_key(address, x, y)
        self.set_tile(entry_index, x, y, 0x30)
        if existing and ("rom_source_treasure" in existing.properties or "rom_source_stair" in existing.properties):
            self.event_metadata[key] = {"map_index": entry_index, "deleted": True, "properties": existing.properties}
        else:
            self.event_metadata.pop(key, None)
        self.dirty = True

    def to_dict(self) -> dict:
        return {
            "format": PROJECT_FORMAT,
            "game": "Arcana (USA)",
            "editor_version": "0.7.1",
            "base_rom_sha256": self.rom.info.sha256,
            "maps": {f"{address:06X}": list(tiles) for address, tiles in sorted(self.maps.items())},
            "events": self.event_metadata,
            "items": self.item_overrides,
        }

    def save(self, path: str | Path | None = None) -> None:
        destination = Path(path) if path else self.path
        if destination is None:
            raise ValueError("Aucun chemin de projet")
        destination.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.path = destination
        self.dirty = False

    @classmethod
    def load(cls, rom: ArcanaRom, path: str | Path) -> "ArcanaProject":
        source = Path(path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("format") not in (1, 2, 3, 4, PROJECT_FORMAT):
            raise RomError("Version de projet non prise en charge")
        if payload.get("base_rom_sha256") != rom.info.sha256:
            raise RomError("Le projet ne correspond pas au ROM chargé")
        expected = set(rom.unique_maps())
        maps = {int(address, 16): bytearray(values) for address, values in payload.get("maps", {}).items()}
        if set(maps) != expected or any(len(tiles) != MAP_WIDTH * MAP_HEIGHT for tiles in maps.values()):
            raise RomError("Données de cartes invalides dans le projet")
        metadata = payload.get("events", {})
        if not isinstance(metadata, dict):
            raise RomError("Métadonnées d’événements invalides")
        items = payload.get("items", {})
        if not isinstance(items, dict):
            raise RomError("Base de données d’objets invalide")
        return cls(rom=rom, maps=maps, event_metadata=metadata, item_overrides=items, path=source)
