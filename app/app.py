from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QStackedWidget)
from PyQt6.QtCore import QUrl, QProcess, Qt, QTimer, pyqtSignal, QObject, QEventLoop
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
import ctypes
from ctypes import wintypes


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
    def __init__(self, window_title, working_dir=None):
        self.window_title = window_title
        self.exe_hwnd = None
        self.exe_process = None
        self.working_dir = working_dir


    def start_external_program(self, program_path, args=None):
        self.exe_process = QProcess()
        if self.working_dir:
            self.exe_process.setWorkingDirectory(self.working_dir)
        
        # 连接输出信号到处理函数
        self.exe_process.readyReadStandardOutput.connect(self._on_stdout_ready)
        self.exe_process.readyReadStandardError.connect(self._on_stderr_ready)
        # 设置为异步模式，以便可以读取输出
        self.exe_process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        
        if args:
            self.exe_process.start(program_path, args)
        else:
            self.exe_process.start(program_path)

    
    def _on_stdout_ready(self):
        if self.exe_process:
            output = self.exe_process.readAllStandardOutput().data().decode('utf-8', errors='replace')
            if output:
                print(f"[{self.window_title} STDOUT] {output.rstrip()}")
    

    def _on_stderr_ready(self):
        if self.exe_process:
            output = self.exe_process.readAllStandardError().data().decode('utf-8', errors='replace')
            if output:
                print(f"[{self.window_title} STDERR] {output.rstrip()}")


    def find_external_program_hwnd(self, timeout=5):

        def callback(hwnd, extra):
            name = win32gui.GetWindowText(hwnd)
            # 通过排除 '-' 来避免找到 Explorer.exe 窗口
            if name.startswith(self.window_title) and '-' not in name:
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


    def close_external_program(self, control_file_path=None):

        if not self.exe_hwnd:
            return

        # 如果没有控制文件 - 直接强制关闭
        if not control_file_path:
            if self.exe_process:
                self.exe_process.kill()
                self.exe_process.waitForFinished(500)
                print(f"{self.window_title} force closed")
            return

        # 如果有控制文件 - 通过控制文件请求程序关闭
        try:
            with open(control_file_path, 'w') as f:
                f.write("exit")
            print(f"{self.window_title} shutdown via control file")
        except Exception as e:
            print(f"Error writing to control file for {self.window_title}: {e}")
            # 如果写文件失败，强制关闭
            if self.exe_process:
                self.exe_process.kill()
                self.exe_process.waitForFinished(500)
                print(f"{self.window_title} force closed")
            return

        # 使用 QEventLoop 实现非阻塞等待（让事件循环继续处理stdout/stderr）
        event_loop = QEventLoop()
        check_timer = QTimer()
        timeout_timer = QTimer()
        
        # 检查计时器：每100ms检查一次进程状态
        check_count = [0]  # 使用列表以便在lambda中修改

        def check_process():
            check_count[0] += 1
            if self.exe_process and self.exe_process.state() == QProcess.ProcessState.NotRunning:
                print(f"{self.window_title} closed normally - {check_count[0] * 100}ms")
                check_timer.stop()
                timeout_timer.stop()
                event_loop.quit()
        
        check_timer.timeout.connect(check_process)
        check_timer.start(100)
        
        # 超时计时器：5秒后强制关闭
        def on_timeout():
            print(f"{self.window_title} did not close normally after 5s, forcing shutdown...")
            check_timer.stop()
            if self.exe_process:
                self.exe_process.kill()
                self.exe_process.waitForFinished(500)
                print(f"{self.window_title} force closed")
            event_loop.quit()
        
        timeout_timer.timeout.connect(on_timeout)
        timeout_timer.setSingleShot(True)
        timeout_timer.start(5000)  # 5秒
        
        # 进入事件循环等待（不阻塞Qt主事件循环的消息处理）
        event_loop.exec()






# debug
#--------------------------------------------------------------
# Main Window

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        # 配色方案变量
        self.color_bg = "#2b2b2b"
        self.color_border = "#454545"
        self.color_surface = "#17203D"
        self.color_surface_hover = "#212C47"
        self.color_text_primary = "#E8E8E8"
        self.color_text_secondary = "#8D99AE"
        self.color_accent = "#3A86FF"

        # 左下视频播放器变量
        self.media_player = None
        self.media_controller = None
        self.proxy_server = None

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
        
        # majdata tab 页面变量
        self.majdata_control_txt = os.path.join(os.path.dirname(__file__), "Majdata",  "HachimiDX-Convert-Majdata-Control.txt")
        self.majdata_folder_input = None
        self.majdata_maidata_choose = None
        self.majdata_track_choose = None
        self.majdata_last_selection = "" # folder_input用的，记录上次选择的歌曲

        # 程序初始化
        majdata_working_dir = os.path.join(os.path.dirname(__file__), "Majdata")
        self.Majdata_View_Handler = ExternalProgramHandler("MajdataView", majdata_working_dir)
        self.Majdata_Edit_Handler = ExternalProgramHandler("MajdataEdit", majdata_working_dir)
        self.start_External_Programs()
        self.setup_window()
        self.setup_layout()
        # self.setup_proxy_server()


    def closeEvent(self, event):

        print("\n---HachimiDX-Convert closing---")
        # 先停止代理服务器
        print("\n--Closing Server...")
        if self.proxy_server:
            self.proxy_server.stop()
            print("Proxy server stopped")
        # 关闭 MajdataView（强制模式，无控制文件）
        print("\n--Closing MajdataView...")
        self.Majdata_View_Handler.close_external_program()
        # 关闭 MajdataEdit（优雅模式，有控制文件）
        print("\n--Closing MajdataEdit...")
        self.Majdata_Edit_Handler.close_external_program(self.majdata_control_txt)
        # 打印最终退出信息
        print("\n---HachimiDX-Convert MainWindow quit normally---")
        event.accept()


    def start_External_Programs(self):
        # 先确保control不存在
        if os.path.exists(self.majdata_control_txt):
            os.remove(self.majdata_control_txt)
        # 确认majdata程序存在
        majdata_view_path = os.path.join(os.path.dirname(__file__), "Majdata", "MajdataView.exe")
        majdata_edit_path = os.path.join(os.path.dirname(__file__), "Majdata", "MajdataEdit.exe")
        if not os.path.exists(majdata_view_path) or not os.path.exists(majdata_edit_path):
            raise FileNotFoundError("Error: MajdataView.exe or MajdataEdit.exe not found in App/Majdata/")
        # 启动程序
        self.Majdata_View_Handler.start_external_program(majdata_view_path)
        self.Majdata_Edit_Handler.start_external_program(majdata_edit_path, ["--embed_mode"])
        # 获取窗口句柄
        self.Majdata_View_Handler.find_external_program_hwnd()
        self.Majdata_Edit_Handler.find_external_program_hwnd()


    def setup_proxy_server(self):
        # 创建媒体播放器控制器
        self.media_controller = server.MediaPlayerController(self.media_player)
        # 创建纯监听服务器（仅监听8013，不转发）
        self.proxy_server = server.MajdataListenerServer(
            listen_port=8013,
            media_controller=self.media_controller
        )
        # 启动监听服务器
        self.proxy_server.start()
        print("Majdata监听服务器启动 (纯监听模式)")
        

    def setup_window(self):
        self.setWindowTitle("HachimiDX-Convert")
        icon_path = os.path.join(os.path.dirname(__file__), 'static', 'maimai.ico')
        self.setWindowIcon(QIcon(icon_path))
        self.setFixedSize(1300, 900)


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
        
        # 左上widget - 正方形 - 嵌入MajdataView窗口
        upper_left_window = QWindow.fromWinId(self.Majdata_View_Handler.exe_hwnd)
        upper_left_widget = self.createWindowContainer(upper_left_window, self)
        upper_left_widget.setFixedSize(square_size, square_size)

        # 左下widget - 正方形 - 视频播放器
        lower_left_widget = QVideoWidget()
        lower_left_widget.setFixedSize(square_size, square_size)
        lower_left_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding) # let video fill the widget
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(lower_left_widget)



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
            page_widget = self.setup_tab_content_pages(title) # 调用外部函数创建具体的页面布局
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


    # debug
    # ----------------------------------------------------------------------
    # 创建各个标签页
    def setup_tab_content_pages(self, title):

        def show_window_size(): # 调试用的
            # 获取原始窗口尺寸 (通过ctypes)
            user32 = ctypes.windll.user32
            rect = wintypes.RECT()
            user32.GetWindowRect(self.Majdata_Edit_Handler.exe_hwnd, ctypes.byref(rect))
            window_width = rect.right - rect.left
            window_height = rect.bottom - rect.top
            print(f"MajdataEdit original size: {window_width}x{window_height}")
            # 获取嵌入窗口尺寸
            embedded_width = MajdataEdit_widget.width()
            embedded_height = MajdataEdit_widget.height()
            print(f"MajdataEdit embedded size: {embedded_width}x{embedded_height}")


        if title == "MajdataEdit":
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(0)
            # 上面是选择文件区域
            majdata_control_panel_widget = self.setup_Majdata_Control_Panel()
            page_layout.addWidget(majdata_control_panel_widget)
            # 下面嵌入MajdataEdit窗口
            MajdataEdit_window = QWindow.fromWinId(self.Majdata_Edit_Handler.exe_hwnd)
            MajdataEdit_widget = self.createWindowContainer(MajdataEdit_window, self)
            page_layout.addWidget(MajdataEdit_widget)
        else:
            page = QWidget()
            page.setStyleSheet("background-color: #1C2541; border-radius: 5px; margin: 8px;")
            page_layout = QVBoxLayout(page)
            page_label = QLabel(f"{title} 内容区域")
            page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_label.setStyleSheet("color: #E0E0E0; font-size: 18px; padding: 20px;")
            page_layout.addWidget(page_label)
        return page
    

    def setup_Majdata_Control_Panel(self):

        widget = QWidget()
        widget.setFixedHeight(50)
        widget.setStyleSheet(f"background-color: {self.color_surface}; margin: 8px")
        layout = QHBoxLayout(widget)
        # folder editable combobox
        self.majdata_folder_input = FolderComboBox()
        self.majdata_folder_input.setEditable(True)
        self.majdata_folder_input.setFixedWidth(200)
        self.majdata_folder_input.currentTextChanged.connect(self.on_majdata_folder_changed)
        layout.addWidget(self.majdata_folder_input)
        # Maidata choose
        self.majdata_maidata_choose = QComboBox()
        self.majdata_maidata_choose.setFixedWidth(100)
        layout.addWidget(self.majdata_maidata_choose)
        # Track choose
        self.majdata_track_choose = QComboBox()
        self.majdata_track_choose.setFixedWidth(100)
        layout.addWidget(self.majdata_track_choose)
        # Load button
        load_button = QPushButton("Load")
        load_button.setFixedWidth(60)
        load_button.clicked.connect(self.on_majdata_load_clicked)
        layout.addWidget(load_button)
        # Add spacing for future buttons
        layout.addStretch()

        return widget


        


    # debug
    # ----------------------------------------------------------------------
    # 业务逻辑函数

    # 导航栏按钮点击切换标签页
    @pyqtSlot()
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



    # Majdata folder changed
    @pyqtSlot()
    def on_majdata_folder_changed(self, text):
        # Check song
        song = self.majdata_folder_input.currentText()
        if (not song or
            song == "---" or
            song == self.majdata_last_selection):
            return
        song_path = os.path.join(server.song_folder, song)
        if not os.path.exists(song_path):
            return







    @pyqtSlot()
    def on_majdata_load_clicked(self):
        pass



#--------------------------------------------------------------
# Main

def main():
    # Set up global exception handler
    sys.excepthook = exception_handler
    
    qt_app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()
