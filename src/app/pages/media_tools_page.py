from PyQt6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from ..ui_style import UI_Style
from ..widgets import SegmentedNavBar
from .media_subpages.arcade_timing import ArcadeTimingPage
from .media_subpages.simple_align import SimpleAlignPage
from .media_subpages.run_ffmpeg import RunFFmpegPage
from .media_subpages.others import OthersPage

class MediaToolsPage(QWidget):
    """
    Media Tools 主页面
    包含内部导航栏和子页面 Stack
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 0. 顶部增加空隙，让内部导航栏与整体导航栏分离
        layout.addSpacing(UI_Style.widget_spacing)

        # 1. 内部导航栏
        nav_items = ["Arcade Timing",
                     "Simple Align",
                     "Run FFmpeg",
                     "Others"]
        self.nav_bar = SegmentedNavBar(nav_items, height=UI_Style.sub_navbar_height)
        layout.addWidget(self.nav_bar)

        # 2. 内容 Stack
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # 添加子页面
        self.stack.addWidget(ArcadeTimingPage())
        self.stack.addWidget(SimpleAlignPage())
        self.stack.addWidget(RunFFmpegPage())
        self.stack.addWidget(OthersPage())

        # 连接信号
        self.nav_bar.currentChanged.connect(self.stack.setCurrentIndex)
