from __future__ import annotations

from dataclasses import dataclass, field

from .i18n import tr
from .rendering import event_kind, tile_details

EVENT_TYPES = {
    "Encounter": 0x10,
    "Encounter +": 0x20,
    "Stairs": 0x40,
    "Transition": 0x50,
    "Fog": 0x60,
    "Event": 0x70,
    "Chest": 0x80,
    "Door / event": 0x90,
}


def event_types() -> dict[str, int]:
    return {tr(name): value for name, value in EVENT_TYPES.items()}


@dataclass
class MapEvent:
    map_address: int
    x: int
    y: int
    value: int
    name: str = ""
    notes: str = ""
    properties: dict[str, str | int] = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return event_kind(self.value) or tr("Event")

    @property
    def key(self) -> str:
        return event_key(self.map_address, self.x, self.y)

    @property
    def display_name(self) -> str:
        return self.name.strip() or default_event_name(self.kind, self.x, self.y)

    @property
    def details(self) -> str:
        return tile_details(self.value)


def event_key(map_address: int, x: int, y: int) -> str:
    return f"{map_address:06X}:{x:02d}:{y:02d}"


def default_event_name(kind: str, x: int, y: int) -> str:
    return f"{kind} ({x}, {y})"


def default_properties(value: int) -> dict[str, str | int]:
    family = value & 0xF0
    variant = value & 0x0F
    if family in (0x10, 0x20):
        return {"groupe": variant, "fréquence": "1/4" if family == 0x20 else "1/12"}
    if family == 0x80:
        return {"contenu": "À identifier", "quantité": 1}
    if family in (0x40, 0x50):
        return {"destination": "À définir", "x_cible": 0, "y_cible": 0, "direction": "Nord"}
    if family in (0x70, 0x90):
        return {"déclenchement": "Contact joueur", "condition": "Aucune"}
    if family == 0x60:
        return {"intensité": variant}
    return {}
