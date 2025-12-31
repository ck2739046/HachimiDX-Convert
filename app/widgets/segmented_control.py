from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from app import ui_style


class SegmentedControl(QWidget):
    """Small segmented control based on QButtonGroup (similar to SegmentedNavBar)."""

    valueChanged = pyqtSignal(int)

    def __init__(self, items: list[str], *, height: int | None = None, parent=None):
        super().__init__(parent)
        self.items = items
        self.height = height or ui_style.element_height

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.idClicked.connect(self.valueChanged.emit)

        for idx, text in enumerate(items):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFixedHeight(self.height)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {ui_style.COLORS['surface']};
                    color: {ui_style.COLORS['text_secondary']};
                    border: none;
                    font-size: 13px;
                    font-weight: bold;
                    padding-left: 10px;
                    padding-right: 10px;
                }}
                QPushButton:hover {{ background-color: {ui_style.COLORS['surface_hover']}; }}
                QPushButton:checked {{
                    background-color: {ui_style.COLORS['accent']};
                    color: {ui_style.COLORS['text_primary']};
                }}
                QPushButton:checked:hover {{ background-color: {ui_style.COLORS['accent_hover']}; }}
                """
            )
            layout.addWidget(btn)
            self.button_group.addButton(btn, idx)

        if self.button_group.buttons():
            self.button_group.buttons()[0].setChecked(True)

    def index(self) -> int:
        return self.button_group.checkedId()

    def set_index(self, idx: int) -> None:
        btn = self.button_group.button(idx)
        if btn is not None:
            btn.setChecked(True)
