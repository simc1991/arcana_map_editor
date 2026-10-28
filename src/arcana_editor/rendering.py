from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TileStyle:
    name: str
    category: str
    floor: str
    accent: str
    symbol: str = ""


def _tile_styles() -> dict[str, TileStyle]:
    from .i18n import tr
    return {
        "void": TileStyle(tr("Wall / empty"), tr("Scenery"), "#17202a", "#263646"),
        "encounter": TileStyle(tr("Normal encounter"), tr("Encounter"), "#686454", "#98a06a", "\u2694"),
        "danger": TileStyle(tr("Frequent encounter"), tr("Encounter"), "#765242", "#d0875f", "!"),
        "safe": TileStyle(tr("Safe floor"), tr("Terrain"), "#5e625d", "#858c84"),
        "stairs": TileStyle(tr("Stairs / passage"), tr("Transition"), "#535d70", "#d5d9e2", "\u21a7"),
        "transition": TileStyle(tr("Transition"), tr("Transition"), "#5a536e", "#c4a7e7", "\u21c4"),
        "fog": TileStyle(tr("Fog"), tr("Terrain"), "#485d64", "#9dc6c8", "\u2601"),
        "boss": TileStyle(tr("Boss / event"), tr("Event"), "#713f48", "#ff6b75", "\u2620"),
        "chest": TileStyle(tr("Chest"), tr("Item"), "#6a5936", "#f2c14e", "\u25a3"),
        "door": TileStyle(tr("Door / event"), tr("Event"), "#554a66", "#d0a9f5", "\u25eb"),
        "unknown": TileStyle(tr("Special tile"), tr("Technical"), "#554a66", "#b995d6", "?"),
    }


TILE_STYLES = _tile_styles()


def tile_style(value: int) -> TileStyle:
    TILE_STYLES = _tile_styles()
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
    from .i18n import tr
    family = value & 0xF0
    return {
        0x10: tr("Encounter"),
        0x20: tr("Encounter +"),
        0x40: tr("Stairs"),
        0x50: tr("Transition"),
        0x60: tr("Fog"),
        0x70: tr("Event"),
        0x80: tr("Chest"),
        0x90: tr("Door / event"),
    }.get(family)


def tile_details(value: int) -> str:
    from .i18n import tr
    family = value & 0xF0
    variant = value & 0x0F
    if family == 0x10:
        return tr("Encounter table") + f" {variant:X}, " + tr("normal frequency (1/12)")
    if family == 0x20:
        return tr("Encounter table") + f" {variant:X}, " + tr("high frequency (1/4)")
    if family == 0x40:
        return tr("Passage or stairs, variant") + f" {variant:X}"
    if family == 0x50:
        return tr("Zone transition, variant") + f" {variant:X}"
    if family == 0x60:
        return tr("Fog effect, variant") + f" {variant:X}"
    if family == 0x70:
        return tr("Boss or event trigger, variant") + f" {variant:X}"
    if family == 0x80:
        return tr("Chest slot, variant") + f" {variant:X}"
    if family == 0x90:
        return tr("Dungeon door or special event, variant") + f" {variant:X}"
    if value == 0:
        return tr("Impassable tile")
    return tr("Walkable tile, variant") + f" {variant:X}"
