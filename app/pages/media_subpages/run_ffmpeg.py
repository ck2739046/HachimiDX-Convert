from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from app.pages.base_tool_page import BaseToolPage
from app.ui_style import COLORS

class RunFfmpegPage(BaseToolPage):
    def setup_content(self):
        label = QLabel("Run FFmpeg Page (Placeholder)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px;")
        self.content_layout.addWidget(label)
