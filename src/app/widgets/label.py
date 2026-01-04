from PyQt6.QtWidgets import QLabel
from ..ui_style import UI_Style

def create_label(text=None, color=None, size=None, bold=False):
    """
    创建文本标签
    
    Args:
        text: str，可选，默认空字符串
        color: #xxx，可选，默认 UI_Style.COLORS['text_primary']
        size: int，可选，默认 UI_Style.default_text_size
        bold: bool，可选，默认False
    
    Returns:
        QLabel: 配置好的文本标签
    """

    if not text:
        text = ""

    if not color:
        color = UI_Style.COLORS['text_primary']

    if not size:
        size = UI_Style.default_text_size

    label = QLabel(text)

    if bold:
        label.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: bold;")
    else:
        label.setStyleSheet(f"color: {color}; font-size: {size}px;")
    
    return label
