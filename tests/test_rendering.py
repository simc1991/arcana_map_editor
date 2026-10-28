from arcana_editor.rendering import event_kind, is_walkable, tile_details, tile_style


def test_semantic_tile_rendering() -> None:
    assert not is_walkable(0x00)
    assert is_walkable(0x30)
    assert tile_style(0x10).category == "Encounter"
    assert tile_style(0x80).symbol == "▣"
    assert tile_style(0xF4).category == "Technical"


def test_event_classification() -> None:
    assert event_kind(0x10) == "Encounter"
    assert event_kind(0x2F) == "Encounter +"
    assert event_kind(0x41) == "Stairs"
    assert event_kind(0x70) == "Event"
    assert event_kind(0x80) == "Chest"
    assert event_kind(0x90) == "Door / event"
    assert event_kind(0x92) == "Door / event"
    assert tile_style(0x90).name == "Door / event"
    assert event_kind(0x30) is None
    assert "1/12" in tile_details(0x13)
    assert "1/4" in tile_details(0x24)
    assert "Chest" in tile_details(0x80)
