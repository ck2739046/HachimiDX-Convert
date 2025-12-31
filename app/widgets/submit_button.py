from __future__ import annotations

from PyQt6.QtWidgets import QPushButton

from app import ui_style


class SubmitButton(QPushButton):
    """Standard blue submit button consistent with legacy action buttons."""

    def __init__(self, text: str = "Submit", *, width: int = 120, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(width, ui_style.element_height)
        self.setStyleSheet(
            f"""
            QPushButton {{ background-color: {ui_style.COLORS['accent']}; color: {ui_style.COLORS['text_primary']}; border: none; }}
            QPushButton:hover {{ background-color: {ui_style.COLORS['accent_hover']}; }}
            QPushButton:disabled {{ background-color: {ui_style.COLORS['grey']}; color: {ui_style.COLORS['text_secondary']}; }}
            """
        )
