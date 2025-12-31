from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget
from 
from app import ui_style


class FileSelectRow(QWidget):
    """Reusable file selection row: button + read-only path display."""

    fileSelected = pyqtSignal(str)

    def __init__(
        self,
        file_filter_type: ,
        parent=None,
    ):
        super().__init__(parent)
        self._file_filter = file_filter
        self._path: str | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.button = QPushButton(button_text)
        self.button.setFixedSize(120, ui_style.element_height)
        self.button.setStyleSheet(
            f"""
            QPushButton {{ background-color: {ui_style.COLORS['accent']}; color: {ui_style.COLORS['text_primary']}; border: none; }}
            QPushButton:hover {{ background-color: {ui_style.COLORS['accent_hover']}; }}
            """
        )

        self.path_edit = QLineEdit("")
        self.path_edit.setReadOnly(True)
        self.path_edit.setFixedHeight(ui_style.element_height)
        self.path_edit.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.path_edit.setFrame(False)
        self.path_edit.setStyleSheet(f"color: {ui_style.COLORS['text_secondary']}; font-size: 13px;")

        layout.addWidget(self.button)
        layout.addWidget(self.path_edit, 1)

        self.button.clicked.connect(self._on_pick)

    @property
    def path(self) -> str | None:
        return self._path

    def set_path(self, path: str | None) -> None:
        self._path = path
        self.path_edit.setText(path or "")

    def _on_pick(self) -> None:
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter(self._file_filter)
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if not file_dialog.exec():
            return
        selected_files = file_dialog.selectedFiles()
        if not selected_files:
            return
        self.set_path(selected_files[0])
        self.fileSelected.emit(selected_files[0])
