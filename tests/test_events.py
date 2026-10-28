from arcana_editor.events import EVENT_TYPES, MapEvent, default_event_name, default_properties, event_key


def test_event_identity_and_defaults() -> None:
    event = MapEvent(0x13EBF6, 4, 7, 0x80)
    assert event.key == "13EBF6:04:07"
    assert event.kind == "Coffre"
    assert event.display_name == "Coffre (4, 7)"
    assert default_event_name("Escalier", 2, 3) == "Escalier (2, 3)"


def test_friendly_properties_by_type() -> None:
    assert default_properties(0x13) == {"groupe": 3, "fréquence": "1/12"}
    assert default_properties(0x24)["fréquence"] == "1/4"
    assert default_properties(0x80)["contenu"] == "À identifier"
    assert default_properties(0x40)["direction"] == "Nord"
    assert EVENT_TYPES["Événement"] == 0x70
    assert event_key(0x13EBF6, 31, 0) == "13EBF6:31:00"
