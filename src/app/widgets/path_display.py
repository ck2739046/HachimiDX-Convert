from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtGui import QCursor
from PyQt6.QtCore import Qt
from ..ui_style import UI_Style

def create_path_display():
    """
    创建路径显示LineEdit组件

    Returns:
        QLineEdit: 配置好的路径显示LineEdit组件
    """

    # 创建路径显示LineEdit
    line_edit = QLineEdit("")
    line_edit.setStyleSheet(f"color: {UI_Style.COLORS['text_secondary']}; font-size: {UI_Style.default_text_size}px;")
    line_edit.setReadOnly(True)
    line_edit.setFixedHeight(UI_Style.element_height)
    line_edit.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
    line_edit.setFrame(False)

    return line_edit
