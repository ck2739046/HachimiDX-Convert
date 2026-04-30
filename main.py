import sys
from pathlib import Path

# 定义 ROOT
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtGui import QFont
from src.core.schemas.op_result import print_op_result
from src.app import MainWindow
from src.services import AllServices, static_shutdown_majdata


def setup_font(app: QApplication) -> None:
    try:
        # 加载外部字体文件
        # font_path = PathManage.FONT_EN_PATH
        # font_id = QFontDatabase.addApplicationFont(str(font_path))
        # if font_id == -1:
            # print(f"[Font] 外部字体文件加载失败: {font_path.name}")
            # return
        # loaded = QFontDatabase.applicationFontFamilies(font_id)
        # if not loaded:
            # print(f"[Font] 外部字体注册后未获取到 family 名称")
            # return
        families = ["Microsoft YaHei UI"]
        font = QFont()
        font.setFamilies(families)
        app.setFont(font)
    except Exception as e:
        print(f"Error setting up font: {e}")


def build_str(input) -> str:
    return f"\n{'-' * 25}\n{input}\n{'-' * 25}\n"


def exception_handler(exctype, value, traceback):
    print(build_str("Error caught by main.py:"))
    # Print the original error
    sys.__excepthook__(exctype, value, traceback)
    print(build_str("End of error."))


def main() -> int:
    """程序主入口，返回退出码"""

    # 设置全局异常处理器
    sys.excepthook = exception_handler

    try:
        app = QApplication(sys.argv)
        app.aboutToQuit.connect(AllServices.shutdown_all)

        # print(f"Available styles: {QStyleFactory.keys()}")
        # print(f"Current style: {app.style().objectName()}")
        available_styles = QStyleFactory.keys()
        if "windows11" in available_styles:
            app.setStyle("windows11")

        # 设置全局字体
        setup_font(app)

        result = AllServices.initialize_all()
        if not result.is_ok:
            print(build_str("Initialization Error:"))
            print(print_op_result(result))
            print(build_str("End of Initialization Error."))
            return 1

        window = MainWindow()
        window.show()
        return app.exec()

    finally:
        # 确保清理外部程序
        static_shutdown_majdata()


if __name__ == "__main__":
    sys.exit(main())
