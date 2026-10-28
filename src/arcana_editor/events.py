from __future__ import annotations

from dataclasses import dataclass, field

from .rendering import event_kind, tile_details

EVENT_TYPES = {
    "Rencontre": 0x10,
    "Rencontre +": 0x20,
    "Escalier": 0x40,
    "Transition": 0x50,
    "Brouillard": 0x60,
    "Événement": 0x70,
    "Coffre": 0x80,
    "Porte / événement": 0x90,
}


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
        return event_kind(self.value) or "Événement"

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
    kind = event_kind(value)
    variant = value & 0x0F
    if kind in ("Rencontre", "Rencontre +"):
        return {"groupe": variant, "fréquence": "1/4" if kind == "Rencontre +" else "1/12"}
    if kind == "Coffre":
        return {"contenu": "À identifier", "quantité": 1}
    if kind in ("Escalier", "Transition"):
        return {"destination": "À définir", "x_cible": 0, "y_cible": 0, "direction": "Nord"}
    if kind in ("Événement", "Porte / événement"):
        return {"déclenchement": "Contact joueur", "condition": "Aucune"}
    if kind == "Brouillard":
        return {"intensité": variant}
    return {}
