"""
Main Window - 主窗口框架
"""

import sys
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from app.widgets import SquareWidget
from app.widgets.nav_bar import SegmentedNavBar
from app.pages.media_tools_page import MediaToolsPage
from app import ui_style
from settings import SettingsManage
from locales.locale_manage import LocaleManage


class LeftPanel(QWidget):
    """
    左侧面板 - 包含两个正方形占位符
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()


    def setup_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ui_style.widget_spacing)
        
        # 上方：MajdataView 占位符
        self.majdata_placeholder = SquareWidget()
        layout.addWidget(self.majdata_placeholder)
        
        # 下方：VideoPlayer 占位符
        self.video_placeholder = SquareWidget()
        layout.addWidget(self.video_placeholder)


    def sizeHint(self):
        init_size, isSuccess, error_msg, default_init_size = SettingsManage.get_persistent_settings("main_app_init_size")
        if isSuccess and init_size:
            return QSize(*init_size)
        elif not isSuccess:
            print(LocaleManage.get("app.main_window.init_size_warning", error=error_msg))
            if default_init_size:
                print(LocaleManage.get("app.main_window.using_default_init_size"))
                return QSize(*default_init_size)
            else:
                print(LocaleManage.get("app.main_window.init_size_critical_error"))
                sys.exit(1)


    def resizeEvent(self, event):
        """
        根据高度动态调整宽度，以保持内部两个子控件为正方形
        计算公式：
        Height = 2 * Width + Spacing
        Width = (Height - Spacing) / 2
        """
        
        # 计算目标宽度
        spacing = 10
        target_width = (self.height() - spacing) // 2

        # 设置宽度
        if target_width > 0 and self.width() != target_width:
            self.setFixedWidth(target_width)
            
        super().resizeEvent(event)






class RightPanel(QWidget):
    """
    右侧面板 - 包含主导航栏和主内容区
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()


    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ui_style.widget_spacing)

        # 1. 主导航栏
        nav_items = ["Majdata", "Auto Convert", "Media Tools", "Tasks", "Settings"]
        self.nav_bar = SegmentedNavBar(nav_items, height=50)
        layout.addWidget(self.nav_bar)

        # 2. 主内容 Stack
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # 添加页面
        # 0: Majdata (Placeholder)
        self.stack.addWidget(self.create_placeholder("Majdata Page"))
        # 1: Auto Convert (Placeholder)
        self.stack.addWidget(self.create_placeholder("Auto Convert Page"))
        # 2: Media Tools
        self.stack.addWidget(MediaToolsPage())
        # 3: Tasks (Placeholder)
        self.stack.addWidget(self.create_placeholder("Tasks Page"))
        # 4: Settings (Placeholder)
        self.stack.addWidget(self.create_placeholder("Settings Page"))

        # 连接信号
        self.nav_bar.currentChanged.connect(self.stack.setCurrentIndex)
        





    # 临时的，后续会删掉
    def create_placeholder(self, text):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {ui_style.COLORS['text_primary']}; font-size: 24px; background-color: {ui_style.COLORS['surface']};")
        return label






class MainWindow(QMainWindow):
    """
    主窗口
    布局：左侧两个正方形 | 右侧功能区
    """
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    

    
    def setup_ui(self):
        """设置主窗口"""
        
        # 设置窗口标题和图标
        self.setWindowTitle("Hachimi DX")
        icon_path, isSuccess, error_msg = SettingsManage.get_path("app_icon")
        if isSuccess and icon_path:
            self.setWindowIcon(QIcon(icon_path))
        if not isSuccess:
            print(LocaleManage.get("app.main_window.set_icon_failed", error=error_msg))

        # 获取窗口尺寸配置
        init_size, isSuccess, error_msg, default_init_size = SettingsManage.get_persistent_settings("main_app_init_size")
        min_size, isSuccess, error_msg, default_min_size = SettingsManage.get_persistent_settings("main_app_min_size")
        
        if isSuccess and init_size:
            self.resize(*init_size)
        elif not isSuccess:
            print(LocaleManage.get("app.main_window.init_size_warning", error=error_msg))
            if default_init_size:
                print(LocaleManage.get("app.main_window.using_default_init_size"))
                self.resize(*default_init_size)
            else:
                print(LocaleManage.get("app.main_window.init_size_critical_error"))
                sys.exit(1)
        
        if isSuccess and min_size:
            self.setMinimumSize(*min_size)
        elif not isSuccess:
            print(LocaleManage.get("app.main_window.min_size_warning", error=error_msg))
            if default_min_size:
                print(LocaleManage.get("app.main_window.using_default_min_size"))
                self.setMinimumSize(*default_min_size)
            else:
                print(LocaleManage.get("app.main_window.min_size_critical_error"))
                sys.exit(1)

        # 设置背景色
        self.setStyleSheet(f"background-color: {ui_style.COLORS['bg']};")
        
        # 创建中心 widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局：水平分为左右两部分
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(ui_style.widget_spacing,
                                       ui_style.widget_spacing,
                                       ui_style.widget_spacing,
                                       ui_style.widget_spacing)
        main_layout.setSpacing(ui_style.widget_spacing)
        
        # 左侧面板
        self.left_panel = LeftPanel()
        main_layout.addWidget(self.left_panel)
        
        # 右侧面板
        self.right_panel = RightPanel()
        main_layout.addWidget(self.right_panel)
