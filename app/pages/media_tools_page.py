from PyQt6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from app import ui_style
from app.widgets.nav_bar import SegmentedNavBar
from app.pages.media_subpages.match_first import MatchFirstPage
from app.pages.media_subpages.simple_align import SimpleAlignPage
from app.pages.media_subpages.extract_game import ExtractGamePage
from app.pages.media_subpages.run_ffmpeg import RunFfmpegPage
from app.pages.media_subpages.others import OthersPage

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

        # 1. 内部导航栏
        nav_items = ["Match First",
                     "Simple Align",
                     "Extract Game",
                     "Run FFmpeg",
                     "Others"]
        self.nav_bar = SegmentedNavBar(nav_items, height=ui_style.sub_navbar_height)
        layout.addWidget(self.nav_bar)

        # 2. 内容 Stack
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # 添加子页面
        self.stack.addWidget(MatchFirstPage())
        self.stack.addWidget(SimpleAlignPage())
        self.stack.addWidget(ExtractGamePage())
        self.stack.addWidget(RunFfmpegPage())
        self.stack.addWidget(OthersPage())

        # 连接信号
        self.nav_bar.currentChanged.connect(self.stack.setCurrentIndex)
