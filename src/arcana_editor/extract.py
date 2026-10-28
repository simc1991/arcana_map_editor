from __future__ import annotations

import argparse
import json
from pathlib import Path

from .rom import ArcanaRom


def extract(rom_path: Path, output: Path) -> None:
    rom = ArcanaRom(rom_path)
    maps_dir = output / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    unique = rom.unique_maps()
    for address, tiles in unique.items():
        (maps_dir / f"map_{address:06X}.bin").write_bytes(tiles)
    manifest = {
        "game": rom.info.title,
        "sha256": rom.info.sha256,
        "crc32": f"{rom.info.crc32:08X}",
        "layout": "LoROM",
        "editor_version": "0.7.1",
        "maps": [
            {
                "index": entry.index,
                "name": entry.name,
                "snes_address": f"{entry.snes_address:06X}",
                "file": f"maps/map_{entry.snes_address:06X}.bin",
                "width": 32,
                "height": 32,
            }
            for entry in rom.maps
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrait les cartes d’un ROM Arcana USA")
    parser.add_argument("rom", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    extract(args.rom, args.output)


if __name__ == "__main__":
    main()
