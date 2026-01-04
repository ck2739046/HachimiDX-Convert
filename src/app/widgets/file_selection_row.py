from PyQt6.QtWidgets import QPushButton, QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from ..ui_style import UI_Style
from .help_icon import create_help_icon

def create_file_selection_row(button_text: str, help_text: str = None):
    """
    创建文件选择行UI组件
    
    Args:
        button_text: str，按钮显示文本
        help_text: str，可选，默认None，不创建help_icon
    
    Returns:
        tuple: (button_widget, line_edit_widget, help_label_widget | None)
    """
    colors = UI_Style.COLORS

    # 创建文件选择按钮
    button = QPushButton(button_text)
    button.setStyleSheet(f'''
        QPushButton {{
            background-color: {colors['accent']};
        }}
        QPushButton:hover {{
            background-color: {colors['accent_hover']};
        }}
    ''')
    button.setFixedSize(120, UI_Style.element_height)
    
    # 创建可选的帮助图标
    help_label = None
    if help_text:
        help_label = create_help_icon(help_text)
    
    # 创建路径显示LineEdit
    line_edit = QLineEdit("")
    line_edit.setStyleSheet(f"color: {colors['text_secondary']}; font-size: {UI_Style.default_text_size}px;")
    line_edit.setReadOnly(True)
    line_edit.setFixedHeight(UI_Style.element_height)
    line_edit.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
    line_edit.setFrame(False)
    
    return button, line_edit, help_label
