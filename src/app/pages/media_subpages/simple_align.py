from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from ..base_output_page import BaseOutputPage
from ...ui_style import UI_Style

class SimpleAlignPage(BaseOutputPage):
    def setup_content(self):
        label = QLabel("Simple Align Page (Placeholder)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {UI_Style.COLORS['text_primary']}; font-size: 18px;")
        self.content_layout.addWidget(label)
