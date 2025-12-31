from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import QLabel, QToolTip

from app import ui_style


class HelpIcon(QLabel):
    """Small ""ⓘ"" tooltip icon consistent with legacy ui_helpers."""

    def __init__(self, text: str, parent=None):
        super().__init__("ⓘ", parent)
        self._text = text

        self.setStyleSheet("font-size: 13px;")
        self.setFixedSize(20, 20)
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))

    def enterEvent(self, event):
        QToolTip.showText(QCursor.pos(), self._text, self, self.rect())
        palette = QToolTip.palette()
        palette.setColor(palette.ColorRole.Window, QColor(ui_style.COLORS["grey"]))
        palette.setColor(palette.ColorRole.WindowText, QColor(ui_style.COLORS["text_secondary"]))
        QToolTip.setPalette(palette)
        font = QToolTip.font()
        font.setBold(True)
        QToolTip.setFont(font)
        return super().enterEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()
        return super().leaveEvent(event)
