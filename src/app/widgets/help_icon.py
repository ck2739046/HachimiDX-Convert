from PyQt6.QtWidgets import QLabel, QToolTip
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QColor
from ..ui_style import UI_Style

def create_help_icon(text):
    """
    创建帮助图标（ⓘ），鼠标悬停时显示提示文本
    
    Args:
        text: str，提示文本内容
    
    Returns:
        QLabel: 配置好的帮助图标widget
    """
    colors = UI_Style.COLORS

    def enter_event():
        # show text
        # 必须先显示文字再设置样式，避免样式被覆盖
        QToolTip.showText(QCursor.pos(), text, help_label, help_label.rect())
        # set palette
        palette = QToolTip.palette()
        palette.setColor(palette.ColorRole.Window, QColor(colors['grey']))
        palette.setColor(palette.ColorRole.WindowText, QColor(colors['text_secondary']))
        QToolTip.setPalette(palette)
        # set font
        font = QToolTip.font()
        font.setBold(True)
        QToolTip.setFont(font)

    help_label = QLabel("ⓘ")
    help_label.setStyleSheet(f"font-size: {UI_Style.default_text_size}px;")
    help_label.setFixedSize(20, 20)
    help_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    help_label.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
    help_label.enterEvent = lambda event: enter_event()
    help_label.leaveEvent = lambda event: QToolTip.hideText()
    return help_label
