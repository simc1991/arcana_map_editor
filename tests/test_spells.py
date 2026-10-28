from pathlib import Path

import pytest

from arcana_editor.rom import ArcanaRom
from arcana_editor.spells import read_spells

ROM = Path(__file__).parents[1] / "Arcana (USA).sfc"


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_spells_are_decoded_from_rom() -> None:
    rom = ArcanaRom(ROM)
    assert rom.spells == read_spells(rom.data)
    assert len(rom.spells) == 91
    assert rom.spells[1].name == "Lightning 1"
    assert rom.spells[4].name == "Smash 1"
    assert rom.spells[1].power > 0
    assert rom.spells[1].accuracy > 0
