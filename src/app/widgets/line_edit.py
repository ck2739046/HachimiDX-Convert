from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtGui import QDoubleValidator, QIntValidator
from ..ui_style import UI_Style


def create_line_edit(default_text=None, placeholder=None, length=None, validator=None):
    """
    创建文本输入框
    Args:
        default_text: str，可选，默认None
        placeholder: str，可选，默认None
        length: int，可选，默认None
        validator: str，可选，默认None，取值可以是 int 或 float/double

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

    if validator == 'int':
        line_edit.setValidator(QIntValidator())
    elif validator in ('float', 'double'):
        line_edit.setValidator(QDoubleValidator())

    if default_text:
        line_edit.setText(default_text)

    return line_edit
