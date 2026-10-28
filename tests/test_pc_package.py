from pathlib import Path

import pytest

from arcana_editor.pc_package import build_pc_package
from arcana_editor.project import ArcanaProject
from arcana_editor.rom import ArcanaRom

ROM = Path(__file__).parents[1] / "Arcana (USA).sfc"


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_pc_package_builds_rom_and_launcher(tmp_path: Path) -> None:
    rom = ArcanaRom(ROM)
    project = ArcanaProject.from_rom(rom)
    emulator = tmp_path / "fake-emu.exe"
    emulator.write_bytes(b"MZ fake emulator")
    folder, report = build_pc_package(project, tmp_path / "Arcana-PC", emulator_path=emulator)
    assert (folder / "arcana.sfc").stat().st_size == len(rom.data)
    assert (folder / "arcana.sfc").is_file()
    assert (folder / "fake-emu.exe").read_bytes() == b"MZ fake emulator"
    bat = (folder / "Jouer.bat").read_text()
    assert "fake-emu.exe" in bat and "arcana.sfc" in bat
    assert (folder / "LISEZ-MOI.txt").is_file()


def test_pc_package_requires_emulator(tmp_path: Path) -> None:
    from arcana_editor.pc_package import find_emulator
    from arcana_editor.rom import RomError
    with pytest.raises(RomError):
        find_emulator(tmp_path / "inexistant.exe")
