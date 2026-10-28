from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from .encounters import EncounterGroup
from .enemies import Enemy
from .events import MapEvent, default_properties, event_key
from .items import GameItem
from .rendering import event_kind
from .rom import ArcanaRom, MAP_HEIGHT, MAP_WIDTH, RomError

PROJECT_FORMAT = 7


@dataclass
class ArcanaProject:
    rom: ArcanaRom
    maps: dict[int, bytearray]
    event_metadata: dict[str, dict] = field(default_factory=dict)
    item_overrides: dict[str, dict] = field(default_factory=dict)
    encounter_overrides: dict[str, dict] = field(default_factory=dict)
    enemy_overrides: dict[str, dict] = field(default_factory=dict)
    path: Path | None = None
    dirty: bool = False

    @classmethod
    def from_rom(cls, rom: ArcanaRom) -> "ArcanaProject":
        return cls(rom=rom, maps={address: bytearray(data) for address, data in rom.unique_maps().items()})

    @property
    def encounter_groups(self) -> tuple[EncounterGroup, ...]:
        merged: dict[tuple[int, int], EncounterGroup] = {(group.chapter, group.group_id): group for group in self.rom.encounter_groups}
        for key, payload in self.encounter_overrides.items():
            chapter, group_id = (int(part) for part in key.split(":"))
            enemy_ids = tuple(int(value) for value in payload.get("enemy_ids", ()))
            names = self.rom.enemy_names
            merged[(chapter, group_id)] = EncounterGroup(
                chapter, group_id, int(payload.get("zone", 0)), enemy_ids,
                tuple(names[enemy_id] if enemy_id < len(names) else f"Ennemi ${enemy_id:02X}" for enemy_id in enemy_ids),
                int(payload.get("flags", 0)),
            )
        return tuple(sorted(merged.values(), key=lambda group: (group.chapter, group.group_id)))

    def save_encounter_group(self, group: EncounterGroup) -> None:
        if not 0 <= group.group_id <= 0x0F:
            raise ValueError("L’identifiant de groupe doit être compris entre 0 et 15")
        if not 0 <= group.zone <= 0xFF:
            raise ValueError("La zone doit être comprise entre 0 et 255")
        if not group.enemy_ids or len(group.enemy_ids) > 0x0F:
            raise ValueError("Un groupe doit contenir entre 1 et 15 ennemis")
        if any(not 0 <= enemy_id <= 0xFF for enemy_id in group.enemy_ids):
            raise ValueError("Un ennemi du groupe est hors limites")
        self.encounter_overrides[f"{group.chapter}:{group.group_id}"] = {
            "zone": group.zone,
            "enemy_ids": list(group.enemy_ids),
            "flags": group.flags,
        }
        self.dirty = True

    def remove_encounter_override(self, chapter: int, group_id: int) -> None:
        self.encounter_overrides.pop(f"{chapter}:{group_id}", None)
        self.dirty = True

    @property
    def enemies(self) -> tuple[Enemy, ...]:
        merged = {enemy.key: enemy.clone() for enemy in self.rom.enemies}
        for key, payload in self.enemy_overrides.items():
            enemy = Enemy.from_dict(payload)
            if enemy.enabled:
                merged[key] = enemy
            else:
                merged.pop(key, None)
        return tuple(sorted(merged.values(), key=lambda enemy: enemy.enemy_id))

    def save_enemy(self, enemy: Enemy, old_key: str | None = None) -> None:
        if not enemy.name.strip():
            raise ValueError("Le nom du monstre est obligatoire")
        if not 0 <= enemy.enemy_id <= 0xFF:
            raise ValueError("L’identifiant doit être compris entre 0 et 255")
        word_fields = ("hp", "exp", "gp", "level", "strength", "intelligence", "endurance", "alertness", "attack_animation", "equip_armor", "equip_amulet")
        for field_name in word_fields:
            if not 0 <= int(getattr(enemy, field_name)) <= 0xFFFF:
                raise ValueError(f"La statistique {field_name} doit être comprise entre 0 et 65535")
        for field_name in ("race", "element", "spell"):
            if not 0 <= int(getattr(enemy, field_name)) <= 0xFF:
                raise ValueError(f"La statistique {field_name} doit être comprise entre 0 et 255")
        if old_key and old_key != enemy.key:
            self.enemy_overrides.pop(old_key, None)
        collision = next((candidate for candidate in self.enemies if candidate.key == enemy.key and candidate.key != old_key), None)
        if collision:
            raise ValueError(f"L’identifiant {enemy.key} est déjà utilisé par {collision.name}")
        self.enemy_overrides[enemy.key] = enemy.to_dict()
        self.dirty = True

    def remove_custom_enemy(self, key: str) -> None:
        enemy = next((candidate for candidate in self.enemies if candidate.key == key), None)
        if not enemy or not enemy.custom:
            raise ValueError("Seuls les monstres créés dans le projet peuvent être supprimés")
        payload = enemy.to_dict()
        payload["enabled"] = False
        self.enemy_overrides[key] = payload
        self.dirty = True

    def next_enemy_id(self) -> int:
        used = {enemy.enemy_id for enemy in self.enemies}
        for enemy_id in range(1, 0x100):
            if enemy_id not in used:
                return enemy_id
        raise ValueError("Aucun identifiant de monstre libre")

    def encounters_for_map(self, map_index: int) -> tuple[EncounterGroup, ...]:
        from .encounters import chapter_for_map
        chapter = chapter_for_map(map_index)
        return tuple(group for group in self.encounter_groups if group.chapter == chapter)

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
            "editor_version": "0.9",
            "base_rom_sha256": self.rom.info.sha256,
            "maps": {f"{address:06X}": list(tiles) for address, tiles in sorted(self.maps.items())},
            "events": self.event_metadata,
            "items": self.item_overrides,
            "encounters": self.encounter_overrides,
            "enemies": self.enemy_overrides,
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
        if payload.get("format") not in (1, 2, 3, 4, 5, 6, PROJECT_FORMAT):
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
        encounters = payload.get("encounters", {})
        if not isinstance(encounters, dict):
            raise RomError("Groupes de rencontres invalides")
        enemies = payload.get("enemies", {})
        if not isinstance(enemies, dict):
            raise RomError("Base de données de monstres invalide")
        return cls(rom=rom, maps=maps, event_metadata=metadata, item_overrides=items, encounter_overrides=encounters, enemy_overrides=enemies, path=source)
