from __future__ import annotations

from pathlib import Path
import shutil

from .builder import BuildReport, build_rom
from .project import ArcanaProject
from .rom import RomError

DEFAULT_EMULATOR = Path(__file__).resolve().parents[2] / "tools" / "snes9x-x64.exe"
ROM_NAME = "arcana.sfc"


def find_emulator(explicit: str | Path | None = None) -> Path:
    if explicit:
        candidate = Path(explicit)
        if candidate.is_file():
            return candidate
        raise RomError(f"Émulateur introuvable : {candidate}")
    if DEFAULT_EMULATOR.is_file():
        return DEFAULT_EMULATOR
    raise RomError("Aucun émulateur trouvé — déposez snes9x-x64.exe dans le dossier tools/ ou indiquez son chemin.")


def build_pc_package(
    project: ArcanaProject,
    destination: str | Path,
    emulator_path: str | Path | None = None,
    rom_name: str = ROM_NAME,
) -> tuple[Path, BuildReport]:
    emulator = find_emulator(emulator_path)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    rom_target = destination / rom_name
    report = build_rom(project, rom_target)
    shutil.copy2(emulator, destination / emulator.name)
    bat = destination / "Jouer.bat"
    bat.write_text(
        "@echo off\r\n"
        'start "" "%~dp0' + emulator.name + '" "%~dp0' + rom_name + '"\r\n',
        encoding="ascii",
    )
    (destination / "LISEZ-MOI.txt").write_text(
        "Double-cliquez sur Jouer.bat pour lancer le jeu.\r\n"
        f"Le ROM modifié est {rom_name} ; l'émulateur embarqué est {emulator.name}.\r\n"
        "Ce package contient une copie du jeu : ne le partagez qu'avec des personnes\r\n"
        "qui possèdent l'original. Préférez le patch IPS pour la distribution.\r\n",
        encoding="utf-8",
    )
    return destination, report
