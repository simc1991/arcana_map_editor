from pathlib import Path
from types import SimpleNamespace

import pytest

from arcana_editor.app import ArcanaEditor
from arcana_editor.event_editor import EventEditor

ROM = Path(__file__).parents[1] / "Arcana (USA).sfc"


@pytest.mark.skipif(not ROM.exists(), reason="ROM propriétaire non inclus au dépôt")
def test_event_editor_and_chest_picker_interactions() -> None:
    app = ArcanaEditor()
    try:
        app._load_rom(ROM)
        app.update_idletasks()
        app.project.set_tile(0, 0, 0, 0x90)
        app.tile_value.set(0x80)
        purple_pointer = SimpleNamespace(x=2, y=2)
        app._canvas_press(purple_pointer)
        assert app.project.map_for_entry(0)[0] == 0x90
        assert app.project.event_at(0, 0, 0).kind == "Porte / événement"
        found = app.project.events_for_entry(0)[0]
        before = app.project.map_for_entry(0)[found.y * 32 + found.x]
        pointer = SimpleNamespace(x=found.x * app.tile_size + 2, y=found.y * app.tile_size + 2)
        app._canvas_press(pointer)
        assert app.stroke_before is None
        assert app.project.map_for_entry(0)[found.y * 32 + found.x] == before
        app._map_event_double_click(pointer)
        app.update_idletasks()
        dialogs = [widget for widget in app.winfo_children() if widget.winfo_class() == "Toplevel"]
        assert len(dialogs) == 1
        assert "Éditeur d’événement" in dialogs[0].title()
        dialogs[0].destroy()
        chest = app.project.event_at(0, 7, 2)
        assert chest is not None
        assert chest.properties["contenu"] == "Gold"
        dialog = EventEditor(app, chest, lambda *_: None, app.project.items)
        dialog.update_idletasks()
        content = dialog.property_vars["contenu"]
        assert content.get().startswith("Gold")
        dialog._open_item_picker(content)
        dialog.update_idletasks()
        pickers = [widget for widget in dialog.winfo_children() if widget.winfo_class() == "Toplevel"]
        assert len(pickers) == 1
        trees = []
        stack = [pickers[0]]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if widget.winfo_class() == "Treeview":
                trees.append(widget)
        assert len(trees) == 1
        assert len(trees[0].get_children()) == 145
    finally:
        app.destroy()
