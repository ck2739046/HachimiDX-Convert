from __future__ import annotations

from typing import Optional

from PyQt6.QtGui import QWindow
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget

from ..ui_style import UI_Style


class MajdataPage(QWidget):

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()



    def _setup_ui(self) -> None:

        self._majdataedit_placeholder: Optional[QWidget] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top placeholder for future control bar
        top = QFrame()
        top.setFixedHeight(40)
        top.setStyleSheet(f"background-color: {UI_Style.COLORS['text_secondary']};")
        layout.addWidget(top)

        # MajdataEdit Embed area
        self._majdataedit_placeholder = QWidget()
        self._majdataedit_placeholder.setStyleSheet(f"background-color: {UI_Style.COLORS['grey']};")
        embed_layout = QVBoxLayout(self._majdataedit_placeholder)
        embed_layout.setContentsMargins(0, 0, 0, 0)
        embed_layout.setSpacing(0)
        layout.addWidget(self._majdataedit_placeholder, 1)



    def set_edit_hwnd(self, hwnd: int) -> None:
        """Embed MajdataEdit by hwnd."""

        # while self._embed_layout.count():
        #     item = self._embed_layout.takeAt(0)
        #     w = item.widget()
        #     if w is not None:
        #         w.setParent(None)
        #         w.deleteLater()

        win = QWindow.fromWinId(hwnd)
        container = QWidget.createWindowContainer(win, self) # parent = self
        self._majdataedit_placeholder.layout().addWidget(container, 1)
