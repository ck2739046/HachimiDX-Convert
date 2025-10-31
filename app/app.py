from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QStackedWidget)
from PyQt6.QtCore import QUrl, QProcess, Qt
from PyQt6.QtGui import QWindow, QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QStyle, QSlider, QFileDialog, QToolTip
import threading
import sys
import win32gui
import time
import win32con
from PyQt6.QtCore import pyqtSlot
import server
import os
import psutil
import cv2
import os


# 设置环境变量来禁用Qt多媒体库的调试输出
os.environ['QT_LOGGING_RULES'] = 'qt.multimedia.ffmpeg*=false;' \
                                 'qt.multimedia.playbackengine.codec*=false' # 误报，实际可以使用硬件加速


def exception_handler(exctype, value, traceback):
    # Close external programs before exiting
    try:
        for proc in psutil.process_iter(['name']):
            try:
                if 'MajdataView' in proc.info['name']: # 先关闭view，防止edit弹窗
                    proc.kill()
                    print("MajdataView force closed")
                if 'MajdataEdit' in proc.info['name']:
                    proc.kill()
                    print("MajdataEdit force closed")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except:
        pass
    # Print the original error
    sys.__excepthook__(exctype, value, traceback)
    print("---HachimiDX-Convert quit abnormally---")
    sys.exit(1)






#--------------------------------------------------------------
# Flask backend

class FlaskThread(threading.Thread):
    def run(self):
        server.app.run(port=5273)






#--------------------------------------------------------------
# Custom FolderComboBox (support recover last selection)

class FolderComboBox(QComboBox):

    def mousePressEvent(self, event):
        current_text = self.currentText() # Save current text before clear
        self.clear()
        self.addItem("---")  # 添加占位符
        if os.path.exists(server.song_folder):
            subdirs = [d for d in os.listdir(server.song_folder) 
                      if os.path.isdir(os.path.join(server.song_folder, d))]
            self.addItems(subdirs)
            
        # Restore previous selection if it exists
        if current_text and current_text != "---":
            index = self.findText(current_text)
            if index >= 0:
                self.setCurrentIndex(index)
            else:
                self.setCurrentText(current_text)
                
        super().mousePressEvent(event)






#--------------------------------------------------------------
# External Program Embedder

class ExternalProgramHandler:
    def __init__(self, window_title):
        self.window_title = window_title
        self.exe_hwnd = None
        self.exe_process = None


    def start_external_program(self, program_path):
        self.exe_process = QProcess()
        self.exe_process.start(program_path)


    def find_external_program_hwnd(self, timeout=5):

        def callback(hwnd, extra):
            if win32gui.GetWindowText(hwnd).startswith(self.window_title):
                extra.append(hwnd)
            return True
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            external_windows = []
            win32gui.EnumWindows(callback, external_windows)
            if external_windows:
                self.exe_hwnd = external_windows[0]
                print(f"Found {self.window_title} hwnd: {self.exe_hwnd}")
                return
            time.sleep(0.1) # while循环冷却
        raise Exception(f"External program hwnd not found - {self.window_title}")


    def close_external_program(self):
        if self.exe_hwnd:
            try:
                win32gui.PostMessage(self.exe_hwnd, win32con.WM_CLOSE, 0, 0)
            except:
                pass
        time.sleep(0.2)
        if self.exe_process:
            self.exe_process.kill()
            print(f"{self.window_title} quit normally")






# debug
#--------------------------------------------------------------
# Main Window

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        # 配色方案变量
        self.color_bg = "#2b2b2b"
        self.color_border = "#454545"
        #self.color_base = "#0B132B"
        self.color_surface = "#17203D"
        self.color_surface_hover = "#212C47"
        self.color_text_primary = "#E8E8E8"
        self.color_text_secondary = "#8D99AE"
        self.color_accent = "#3A86FF"
        # 全局变量
        self.last_selection = "" # 全局变量，song_input用的，记录上次选择的歌曲
        self.video_fps = 0       # 全局变量，上/下一帧按钮用的，存储视频fps
        # 导航栏变量
        self.nav_titles = ["MajdataEdit", "Auto Convert", "Audio & PV", "Others"] # 总配置项
        self.current_tab_index = 0     # 当前标签页索引
        self.tab_stacked_widget = None # 内容区堆叠widget
        self.nav_buttons = []          # 4个导航按钮列表
        self.inactive_button_style = f"""
            QPushButton {{
                background-color: {self.color_surface}; color: {self.color_text_secondary};
                border: none; font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.color_surface_hover};
            }}"""
        self.active_button_style = f"""
            QPushButton {{
                background-color: {self.color_accent}; color: {self.color_text_primary};
                border: none; font-size: 14px; font-weight: bold;
            }}"""
        # 程序初始化
        self.Majdata_View_Handler = ExternalProgramHandler("MajdataView")
        self.Majdata_Edit_Handler = ExternalProgramHandler("MajdataEdit")
        self.start_External_Programs()
        self.setup_window()
        self.setup_layout()


    def closeEvent(self, event):
        self.Majdata_View_Handler.close_external_program() # 先关闭view，防止edit弹窗
        self.Majdata_Edit_Handler.close_external_program()
        time.sleep(0.5) # wait program close
        print("---HachimiDX-Convert MainWindow quit normally---")
        event.accept()


    def start_External_Programs(self):
        # 确认majdata程序存在
        majdata_view_path = os.path.join(os.path.dirname(__file__), "Majdata", "MajdataView.exe")
        majdata_edit_path = os.path.join(os.path.dirname(__file__), "Majdata", "MajdataEdit.exe")
        if not os.path.exists(majdata_view_path) or not os.path.exists(majdata_edit_path):
            raise FileNotFoundError("Error: MajdataView.exe or MajdataEdit.exe not found in App/Majdata/")
        # 启动程序
        self.Majdata_View_Handler.start_external_program(majdata_view_path)
        self.Majdata_Edit_Handler.start_external_program(majdata_edit_path)
        # 获取窗口句柄
        self.Majdata_View_Handler.find_external_program_hwnd()
        self.Majdata_Edit_Handler.find_external_program_hwnd()
        

    def setup_window(self):
        self.setWindowTitle("HachimiDX-Convert")
        icon_path = os.path.join(os.path.dirname(__file__), 'static', 'maimai.ico')
        self.setWindowIcon(QIcon(icon_path))
        self.setFixedSize(1400, 900)


    def setup_layout(self):
        # 创建中央widget和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主水平布局 - 分为左右两部分
        main_layout = QHBoxLayout(central_widget)


        # ----------------------------------------------------------------------
        # 左边区域
        
        # 左侧区域 - 上下布局两个正方形widget
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 2, 0) # 右侧+2px间隙，与其他间距保持一致
        left_layout.setSpacing(10)
        square_size = 436 # (900-3*10)/2 + 1px补偿
        
        # 左上widget - 正方形
        upper_left_widget = QWidget()
        upper_left_widget.setFixedSize(square_size, square_size)
        upper_left_widget.setStyleSheet(f"background-color: {self.color_bg};")
        
        # 左下widget - 正方形
        lower_left_widget = QWidget()
        lower_left_widget.setFixedSize(square_size, square_size)
        lower_left_widget.setStyleSheet(f"background-color: {self.color_bg};")


        # ----------------------------------------------------------------------
        # 右边区域

        # 右侧区域 - 上下布局包含导航栏和内容区
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # 右侧顶部导航栏
        navigation_bar = QWidget()
        navigation_bar.setFixedHeight(50)
        navigation_bar.setStyleSheet(f"background-color: {self.color_bg};")
        nav_layout = QHBoxLayout(navigation_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)
        # 在导航栏中创建4个按钮
        for i, title in enumerate(self.nav_titles):
            nav_button = QPushButton(title)
            nav_button.setFixedHeight(50)
            # 先全部设置为未选中状态样式
            nav_button.setStyleSheet(self.inactive_button_style)
            nav_button.clicked.connect(lambda checked, index=i: self.switch_tab(index))
            nav_layout.addWidget(nav_button)
            self.nav_buttons.append(nav_button)
        # 设置第一个按钮为选中状态
        self.nav_buttons[0].setStyleSheet(self.active_button_style)
        
        # 右侧内容区域
        tab_content_area = QWidget()
        tab_content_area.setStyleSheet(f"background-color: {self.color_bg};")
        tab_content_layout = QVBoxLayout(tab_content_area)
        tab_content_layout.setContentsMargins(0, 0, 0, 0)
        tab_content_layout.setSpacing(0)
        # 创建堆叠widget来管理不同的内容页面
        self.tab_stacked_widget = QStackedWidget()
        # 创建4个内容页面
        for i, title in enumerate(self.nav_titles):
            page_widget = self.setup_tab_content_pages_layout(title) # 调用外部函数创建具体的页面布局
            self.tab_stacked_widget.addWidget(page_widget)
        tab_content_layout.addWidget(self.tab_stacked_widget)
        # 设置初始显示的页面
        self.tab_stacked_widget.setCurrentIndex(0)

        # 将上下窗口添加到左侧布局
        left_layout.addWidget(upper_left_widget)
        left_layout.addWidget(lower_left_widget)
        # 将导航栏和内容区添加到右侧布局
        right_layout.addWidget(navigation_bar)
        right_layout.addWidget(tab_content_area)
        # 将左右布局添加到主布局
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)


    def setup_tab_content_pages_layout(self, title):
        page = QWidget()
        page.setStyleSheet("background-color: #1C2541; border-radius: 5px; margin: 8px;")
        page_layout = QVBoxLayout(page)
        page_label = QLabel(f"{title} 内容区域")
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_label.setStyleSheet("color: #E0E0E0; font-size: 18px; padding: 20px;")
        page_layout.addWidget(page_label)
        return page

        


    # debug
    # ----------------------------------------------------------------------
    # 业务逻辑函数

    def switch_tab(self, index):

        # 更新导航栏按钮样式
        for i, button in enumerate(self.nav_buttons):
            if i == index:
                # 选中状态的样式
                button.setStyleSheet(self.active_button_style)
            else:
                # 未选中状态的样式
                button.setStyleSheet(self.inactive_button_style)
        # 切换堆叠widget的当前页面
        self.tab_stacked_widget.setCurrentIndex(index)
        self.current_tab_index = index


#--------------------------------------------------------------
# Main

def main():
    # Set up global exception handler
    sys.excepthook = exception_handler

    flask_thread = FlaskThread(daemon=True)
    flask_thread.start()
    
    qt_app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()
