"""
Square Widget - 保持宽高比为 1:1 的容器
"""

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtGui import QPainter, QColor
from app import ui_style


class SquareWidget(QWidget):
    """
    正方形 Widget
    实际尺寸控制由父容器 LeftPanel 通过 resizeEvent 动态计算宽度来实现
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.background_color = ui_style.COLORS['grey']
    
    
    def paintEvent(self, event):
        """
        绘制背景色
        """
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(self.background_color))
