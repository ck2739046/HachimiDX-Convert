from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtGui import QDoubleValidator
from ..ui_style import UI_Style


def create_line_edit(default_text=None, placeholder=None, length=None, is_number=False):
    """
    创建文本输入框
    Args:
        default_text: str，可选，默认None
        placeholder: str，可选，默认None
        length: int，可选，默认None
        is_number: bool，可选，默认False，不设置QDoubleValidator

    Returns:
        QLineEdit: 配置好的文本输入框
    """
    
    line_edit = QLineEdit()
    line_edit.setStyleSheet(f"background-color: {UI_Style.COLORS['grey']}; padding-left: 8px;")

    if length:
        line_edit.setFixedSize(length, UI_Style.element_height)
    else:
        line_edit.setFixedHeight(UI_Style.element_height)

    if placeholder:
        line_edit.setPlaceholderText(placeholder)

    if is_number:
        line_edit.setValidator(QDoubleValidator())

    if default_text:
        line_edit.setText(default_text)

    return line_edit
