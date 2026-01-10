from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup
from PyQt6.QtCore import pyqtSignal
from ..ui_style import UI_Style


class SegmentedNavBar(QWidget):
    """
    通用分段导航栏
    """
    currentChanged = pyqtSignal(int)

    def __init__(self, items: list[str], height: int, parent=None):
        super().__init__(parent)
        self.items = items
        self.height = height
        self.setup_ui()


    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.idClicked.connect(self.currentChanged.emit)

        for i, text in enumerate(self.items):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFixedHeight(self.height)
            
            # 设置样式
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {UI_Style.COLORS['surface']};
                    color: {UI_Style.COLORS['text_secondary']};
                    border: none;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {UI_Style.COLORS['surface_hover']};
                }}
                QPushButton:checked {{
                    background-color: {UI_Style.COLORS['accent']};
                    color: {UI_Style.COLORS['text_primary']};
                    border: none;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:checked:hover {{
                    background-color: {UI_Style.COLORS['accent_hover']};
                }}
            """)

            layout.addWidget(btn)
            self.button_group.addButton(btn, i)

        # 默认选中第一个
        if self.button_group.buttons():
            self.button_group.buttons()[0].setChecked(True)
