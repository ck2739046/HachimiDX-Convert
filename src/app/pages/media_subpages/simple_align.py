from PyQt6.QtWidgets import QLabel, QVBoxLayout
from PyQt6.QtCore import Qt
from ..base_output_page import BaseOutputPage
from ...ui_style import UI_Style

class SimpleAlignPage(BaseOutputPage):
    def setup_content(self):

        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.addStretch()  # 添加弹性空间，使内容从顶部开始显示

        label = QLabel("Simple Align Page (Placeholder)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {UI_Style.COLORS['text_primary']}; font-size: 18px;")
        self.content_layout.addWidget(label)
