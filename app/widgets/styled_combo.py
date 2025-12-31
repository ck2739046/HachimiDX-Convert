from __future__ import annotations

from PyQt6.QtWidgets import QComboBox

from app import ui_style


class StyledComboBox(QComboBox):
    """A simple styled combo box consistent with legacy create_combo_box."""

    def __init__(self, *, width: int | None = None, parent=None):
        super().__init__(parent)
        self.setEditable(False)
        self.setStyleSheet(f"background-color: {ui_style.COLORS['grey']}; padding-left: 8px;")
        if width is not None:
            self.setFixedSize(width, ui_style.element_height)
        else:
            self.setFixedHeight(ui_style.element_height)

    def set_items(self, items: list[str], default_index: int = 0) -> None:
        self.clear()
        self.addItems(items)
        if 0 <= default_index < len(items):
            self.setCurrentIndex(default_index)
