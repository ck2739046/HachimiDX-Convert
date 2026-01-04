from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from ..widgets import OutputLogWidget
from ..ui_style import UI_Style

class BaseToolPage(QWidget):
    """
    工具页面基类
    包含：
    1. 内容区域 (self.content_area)
    2. 日志输出区域 (self.output_widget)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()


    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(UI_Style.widget_spacing)

        # 1. 内容区域容器
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.setup_content() # 这个部分由子类填充
        layout.addWidget(self.content_area, 1)  # 拉伸因子为1，使其扩展

        # 2. 日志输出区域
        self.output_widget = OutputLogWidget()
        layout.addWidget(self.output_widget, 0)  # 拉伸因子为0，固定在底部
        

    def setup_content(self):
        """
        子类重写此方法来填充 content_area
        已经创建了 self.content_layout (QVBox) 供使用。

        示例：
            def setup_content(self):
                label = QLabel("Hello")
                self.content_layout.addWidget(label)
        """
        pass
