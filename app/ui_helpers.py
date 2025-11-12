"""
UI Helper Functions and Shared Resources
提供统一的UI组件创建函数和配色方案
"""

from PyQt6.QtWidgets import QLabel, QComboBox, QLineEdit, QCheckBox, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QToolTip


# 配色方案
COLORS = {
    'bg': "#303030",
    'grey': "#454545",
    'surface': "#17203D",
    'surface_hover': "#212C47",
    'text_primary': "#E8E8E8",
    'text_secondary': "#8D99AE",
    'accent': "#3A86FF",
    'stop': "#DC3545",
}


def create_help_icon(text):
    """
    创建帮助图标（❓），鼠标悬停时显示提示文本
    
    Args:
        text: 提示文本内容
    
    Returns:
        QLabel: 配置好的帮助图标widget
    """
    help_label = QLabel("❓")
    help_label.setStyleSheet("font-size: 13px;")
    help_label.setFixedSize(10, 20)
    help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    help_label.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
    help_label.enterEvent = lambda event: QToolTip.showText(
        QCursor.pos(),
        text,
        help_label,
        help_label.rect()
    )
    help_label.leaveEvent = lambda event: QToolTip.hideText()
    return help_label


def create_combo_box(length, items=None, default_index=0):
    """
    创建下拉选择框
    
    Args:
        length: 宽度（像素）
        items: 选项列表，默认为None
        default_index: 默认选中的索引，默认为0
    
    Returns:
        QComboBox: 配置好的下拉选择框
    """
    combo = QComboBox()
    combo.setEditable(False)
    combo.setStyleSheet(f"background-color: {COLORS['grey']}; padding-left: 8px;")
    combo.setFixedSize(length, 25)
    
    if items:
        combo.addItems(items)
        if 0 <= default_index < len(items):
            combo.setCurrentIndex(default_index)
    
    return combo


def create_label(text):
    """
    创建文本标签
    
    Args:
        text: 标签文本内容
    
    Returns:
        QLabel: 配置好的文本标签
    """
    label = QLabel(text)
    label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px;")
    return label


def create_line_edit(length, validator=None, placeholder=None):
    """
    创建文本输入框
    
    Args:
        length: 宽度（像素）
        validator: 输入验证器（QValidator），默认为None
        placeholder: 占位符文本，默认为None
    
    Returns:
        QLineEdit: 配置好的文本输入框
    """
    line_edit = QLineEdit()
    line_edit.setStyleSheet(f"background-color: {COLORS['grey']}; padding-left: 8px;")
    line_edit.setFixedSize(length, 25)
    
    if validator:
        line_edit.setValidator(validator)
    
    if placeholder:
        line_edit.setPlaceholderText(placeholder)
    
    return line_edit


def create_check_box():
    """
    创建复选框
    
    Returns:
        QCheckBox: 配置好的复选框
    """
    checkbox = QCheckBox()
    checkbox.setFixedSize(20, 20)
    checkbox.setStyleSheet(f"""
        QCheckBox::indicator {{
            background-color: {COLORS['grey']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {COLORS['accent']};
        }}
    """)
    return checkbox


def create_divider():
    """
    创建分隔线
    
    Returns:
        QWidget: 包含分隔线的容器widget
    """
    divider_container = QWidget()
    divider_layout = QVBoxLayout(divider_container)
    divider_layout.setContentsMargins(0, 10, 0, 10)  # 上下各10像素间距
    divider_layout.setSpacing(0)
    
    divider_line = QWidget()
    divider_line.setFixedHeight(2)  # 细线高度
    divider_line.setStyleSheet(f"background-color: {COLORS['grey']};")
    
    divider_layout.addWidget(divider_line)
    
    return divider_container
