from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from ..widgets import OutputLogWidget
from ..ui_style import UI_Style

class BaseToolPage(QWidget):
    """
    工具页面基类
    包含：
    1. 内容区域 (self.content_area)
    2. 日志输出区域 (self.output_widget)

    需要子类重写 setup_content() 方法来填充内容区域
    该类提供 create_row() 方法来简化行布局的创建
    该类提供 self.content_layout 供子类使用
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
        self.content_layout.addStretch()  # 添加弹性空间，使内容从顶部开始显示
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


    def create_row(self, *widgets, add_stretch=False):
        """
        创建一个水平布局行并添加所有传入的 widgets，然后自动将这个行加入页面。
        
        Args:
            *widgets: 要添加到行中的 widgets
            add_stretch: 是否在末尾添加弹性空间，默认 False
        
        Returns:
            QWidget: 包含所有 widgets 的行容器
        """
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setSpacing(5)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        for widget in widgets:
            row_layout.addWidget(widget)
        
        if add_stretch:
            row_layout.addStretch()

        self.content_layout.addWidget(row)
        
        return row
