"""Main Window - 主窗口框架"""

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QWindow

from .widgets import SquareWidget
from .widgets import SegmentedNavBar
from .ui_style import UI_Style

from .pages.majdata_page import MajdataPage
from .pages.media_tools_page import MediaToolsPage
from .pages.tasks_page import TasksPage

import i18n
from src.services import SettingsManage, PathManage, MajdataSession


class LeftPanel(QWidget):
    """
    左侧面板 - 包含两个正方形占位符
    """
    _init_size = None # 频繁调用，所以缓存
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.majdataview_placeholder = None
        self.video_placeholder = None
        self.setup_ui()


    def setup_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(UI_Style.widget_spacing)
        
        # 上方：MajdataView
        self.majdataview_placeholder = SquareWidget()
        layout.addWidget(self.majdataview_placeholder)
        
        # 下方：VideoPlayer
        self.video_placeholder = SquareWidget()
        layout.addWidget(self.video_placeholder)


    def sizeHint(self):

        if self._init_size is None:
            result = SettingsManage.get("main_app_init_size")
            if result.is_ok:
                self._init_size = QSize(*result.value)
            else:
                print("--Warning: MainWindow.sizeHint: " + i18n.t("general.error_SettingsManage_get_failed", keyy="main_app_init_size"))
                self._init_size = super().sizeHint() # 默认行为
                
        return QSize(self._init_size)


    def resizeEvent(self, event):
        """
        根据高度动态调整宽度，以保持内部两个子控件为正方形。
        高度是 qt 自动计算，所以仅调整宽度。
        计算公式：
        Height = 2 * Width + Spacing
        Width = (Height - Spacing) / 2
        """
        
        # 计算目标宽度
        spacing = UI_Style.widget_spacing
        target_width = (self.height() - spacing) // 2
        # 设置宽度
        if target_width > 0 and self.width() != target_width:
            self.setFixedWidth(target_width)

        super().resizeEvent(event)


    def set_majdata_view_hwnd(self, hwnd: int) -> None:

        layout = self.majdataview_placeholder.layout()
        # 删除旧组件防止重复嵌入
        # while layout.count():
        #     item = layout.takeAt(0)
        #     w = item.widget()
        #     if w is not None:
        #         w.setParent(None)
        #         w.deleteLater()
        win = QWindow.fromWinId(int(hwnd))
        container = QWidget.createWindowContainer(win, self) # parent = self
        layout.addWidget(container)






class RightPanel(QWidget):
    """
    右侧面板 - 包含主导航栏和主内容区
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.majdata_page = None # 保存引用，后续要嵌入程序
        self.setup_ui()


    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. 主导航栏
        nav_items = ["Majdata", "Auto Convert", "Media Tools", "Tasks", "Settings"]
        self.nav_bar = SegmentedNavBar(nav_items, height=UI_Style.main_navbar_height)
        layout.addWidget(self.nav_bar)

        # 2. 主内容 Stack
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # 添加页面
        # 0: Majdata
        self.majdata_page = MajdataPage()
        self.stack.addWidget(self.majdata_page)
        # 1: Auto Convert (Placeholder)
        self.stack.addWidget(self.create_placeholder("Auto Convert Page"))
        # 2: Media Tools
        self.stack.addWidget(MediaToolsPage())
        # 3: Tasks (Placeholder)
        self.stack.addWidget(TasksPage())
        # 4: Settings (Placeholder)
        self.stack.addWidget(self.create_placeholder("Settings Page"))

        # 连接信号
        self.nav_bar.currentChanged.connect(self.stack.setCurrentIndex)


    def set_majdata_edit_hwnd(self, hwnd: int) -> None:
        self.majdata_page.set_edit_hwnd(int(hwnd))


    # 临时的，后续会删掉
    def create_placeholder(self, text):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {UI_Style.COLORS['text_primary']}; font-size: 24px; background-color: {UI_Style.COLORS['surface']};")
        return label






class MainWindow(QMainWindow):
    """
    主窗口
    布局：左侧两个正方形 | 右侧功能区
    """
    
    def __init__(self):
        super().__init__()
        self._majdata_session = None
        self._closing: bool = False
        self.setup_ui()
    

    
    def setup_ui(self):
        """设置主窗口"""
        
        # 设置窗口标题和图标
        self.setWindowTitle("Hachimi DX")
        self.setWindowIcon(QIcon(str(PathManage.APP_ICON_PATH)))

        # 获取窗口尺寸配置
        result = SettingsManage.get("main_app_min_size")
        if result.is_ok:
            min_size = result.value
            self.setMinimumSize(*min_size)
        else:
            print("--Warning: MainWindow.setup_ui: " + i18n.t("general.error_SettingsManage_get_failed", keyy="main_app_min_size"))

        result = SettingsManage.get("main_app_init_size")
        if not result.is_ok:
            print("--Warning: MainWindow.setup_ui: " + i18n.t("general.error_SettingsManage_get_failed", keyy="main_app_init_size"))
        else:
            init_size = result.value
            self.resize(*init_size)

        # 设置背景色
        self.setStyleSheet(f"background-color: {UI_Style.COLORS['bg']};")
        
        # 创建中心 widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局：水平分为左右两部分
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(UI_Style.widget_spacing,
                                       UI_Style.widget_spacing,
                                       UI_Style.widget_spacing,
                                       UI_Style.widget_spacing)
        main_layout.setSpacing(UI_Style.widget_spacing)
        
        # 左侧面板
        self.left_panel = LeftPanel()
        main_layout.addWidget(self.left_panel)
        
        # 右侧面板
        self.right_panel = RightPanel()
        main_layout.addWidget(self.right_panel)

        # 启动 MajdataSession
        self._majdata_session = MajdataSession(self)
        self._majdata_session.ready.connect(self._on_majdata_ready)
        result = self._majdata_session.start()
        # if not result.is_ok:
        #     print(f"--Warning: MajdataSession.start failed: {result.error_msg}")



    def closeEvent(self, event):
        # Non-blocking shutdown

        if self._closing:
            event.accept()
            return

        self._closing = True

        try:
            # 开始退出 majdata，后通过信号得知退出完成
            self._majdata_session.shutdown_finished.connect(lambda: QApplication.instance().quit())
            self._majdata_session.shutdown()
        except Exception:
            QApplication.instance().quit()

        event.ignore() # 此处忽略，不退出，等待 majdata 信号



    def _on_majdata_ready(self, view_hwnd: int, edit_hwnd: int) -> None:
        try:
            self.left_panel.set_majdata_view_hwnd(int(view_hwnd))
        except Exception as e:
            print(f"--Warning: Failed to embed MajdataView: {e}")

        try:
            self.right_panel.set_majdata_edit_hwnd(int(edit_hwnd))
        except Exception as e:
            print(f"--Warning: Failed to embed MajdataEdit: {e}")
