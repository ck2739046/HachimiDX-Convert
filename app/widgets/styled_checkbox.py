from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton

from app import ui_style


class StyledCheckBox(QCheckBox):
    """A custom painted checkbox matching legacy SimpleCheckBox style."""

    def __init__(self, *, size: int = 20, border_width: int = 1, parent=None):
        super().__init__(parent)

        colors = ui_style.COLORS
        self.checked_color = QColor(colors["accent"])
        self.checked_hover_color = QColor(colors["accent_hover"])
        self.unchecked_color = QColor(colors["grey"])
        self.unchecked_hover_color = QColor(colors["grey_hover"])
        self.border_color = QColor(colors["text_secondary"])

        self.size = size
        self.border_width = border_width
        self.is_hover = False

        self.setFixedSize(size, size)

        # Set indicator size via stylesheet.
        self.setStyleSheet(
            f"""
            QCheckBox::indicator {{
                width: {self.size}px;
                height: {self.size}px;
            }}
            """
        )

    def enterEvent(self, event):
        self.is_hover = True
        self.update()
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hover = False
        self.update()
        return super().leaveEvent(event)

    def paintEvent(self, event):
        # Draw text (even though we usually don't set text).
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        opt = QStyleOptionButton()
        opt.initFrom(self)
        indicator_rect = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opt, self)

        rect = QRectF(indicator_rect).adjusted(
            self.border_width,
            self.border_width,
            -self.border_width,
            -self.border_width,
        )

        if self.isChecked():
            bg_color = self.checked_hover_color if self.is_hover else self.checked_color
        else:
            bg_color = self.unchecked_hover_color if self.is_hover else self.unchecked_color

        painter.setPen(QPen(self.border_color, self.border_width))
        painter.setBrush(bg_color)
        painter.drawRoundedRect(rect, 4, 4)

        if self.isChecked():
            path = QPainterPath()
            w, h = rect.width(), rect.height()
            path.moveTo(rect.left() + w * 0.25, rect.top() + h * 0.5)
            path.lineTo(rect.left() + w * 0.45, rect.top() + h * 0.7)
            path.lineTo(rect.left() + w * 0.75, rect.top() + h * 0.3)

            pen = QPen(QColor("white"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
