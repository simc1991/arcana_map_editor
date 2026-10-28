from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TileStyle:
    name: str
    category: str
    floor: str
    accent: str
    symbol: str = ""


TILE_STYLES = {
    "void": TileStyle("Mur / vide", "Décor", "#17202a", "#263646"),
    "encounter": TileStyle("Rencontre normale", "Rencontre", "#686454", "#98a06a", "×"),
    "danger": TileStyle("Rencontre fréquente", "Rencontre", "#765242", "#d0875f", "!"),
    "safe": TileStyle("Sol sûr", "Terrain", "#5e625d", "#858c84"),
    "stairs": TileStyle("Escalier / passage", "Transition", "#535d70", "#d5d9e2", "⇅"),
    "transition": TileStyle("Transition", "Transition", "#5a536e", "#c4a7e7", "◇"),
    "fog": TileStyle("Brouillard", "Terrain", "#485d64", "#9dc6c8", "≈"),
    "boss": TileStyle("Boss / événement", "Événement", "#713f48", "#ff6b75", "★"),
    "chest": TileStyle("Coffre", "Objet", "#6a5936", "#f2c14e", "▣"),
    "door": TileStyle("Porte / événement", "Événement", "#554a66", "#d0a9f5", "◆"),
    "unknown": TileStyle("Tuile spéciale", "Technique", "#554a66", "#b995d6", "?"),
}


def tile_style(value: int) -> TileStyle:
    if value == 0:
        return TILE_STYLES["void"]
    family = value & 0xF0
    if family == 0x10:
        return TILE_STYLES["encounter"]
    if family == 0x20:
        return TILE_STYLES["danger"]
    if family == 0x30:
        return TILE_STYLES["safe"]
    if family == 0x40:
        return TILE_STYLES["stairs"]
    if family == 0x50:
        return TILE_STYLES["transition"]
    if family == 0x60:
        return TILE_STYLES["fog"]
    if family == 0x70:
        return TILE_STYLES["boss"]
    if family == 0x80:
        return TILE_STYLES["chest"]
    if family == 0x90:
        return TILE_STYLES["door"]
    return TILE_STYLES["unknown"]


def is_walkable(value: int) -> bool:
    return value != 0


def event_kind(value: int) -> str | None:
    family = value & 0xF0
    return {
        0x10: "Rencontre",
        0x20: "Rencontre +",
        0x40: "Escalier",
        0x50: "Transition",
        0x60: "Brouillard",
        0x70: "Événement",
        0x80: "Coffre",
        0x90: "Porte / événement",
    }.get(family)


def tile_details(value: int) -> str:
    family = value & 0xF0
    variant = value & 0x0F
    if family == 0x10:
        return f"Table de rencontres {variant:X}, fréquence normale (1/12)"
    if family == 0x20:
        return f"Table de rencontres {variant:X}, fréquence élevée (1/4)"
    if family == 0x40:
        return f"Passage ou escalier, variante {variant:X}"
    if family == 0x50:
        return f"Transition de zone, variante {variant:X}"
    if family == 0x60:
        return f"Effet de brouillard, variante {variant:X}"
    if family == 0x70:
        return f"Déclencheur de boss ou événement, variante {variant:X}"
    if family == 0x80:
        return f"Emplacement de coffre, variante {variant:X}"
    if family == 0x90:
        return f"Porte ou événement spécial du donjon, variante {variant:X}"
    if value == 0:
        return "Case infranchissable"
    return f"Case praticable, variante {variant:X}"
