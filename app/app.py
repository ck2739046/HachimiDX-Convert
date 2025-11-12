from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QStackedWidget)
from PyQt6.QtCore import QUrl, QProcess, Qt, QTimer, pyqtSignal, QObject, QEventLoop
from PyQt6.QtGui import QWindow, QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QStyle, QSlider, QFileDialog, QToolTip
from PyQt6.QtCore import pyqtSlot
import threading
import sys
import win32gui
import time
import win32con
import server
import os
import psutil
import cv2
import ctypes
from ctypes import wintypes

root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config

from page_majdata import MajdataPage
from page_auto_convert import AutoConvertPage
import ui_helpers


# 设置环境变量来禁用Qt多媒体库的调试输出
os.environ['QT_LOGGING_RULES'] = 'qt.multimedia.ffmpeg*=false;' \
                                 'qt.multimedia.playbackengine.codec*=false' # 误报，实际可以使用硬件加速


# Signal emitter for cross-thread callback execution
class CallbackEmitter(QObject):
    callback_signal = pyqtSignal(object)  # Signal to emit callback functions
    def __init__(self):
        super().__init__()
    def emit_callback(self, callback):
        self.callback_signal.emit(callback)


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

    def __init__(self, all_songs_folder=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.all_songs_folder = all_songs_folder

    def mousePressEvent(self, event):
        current_text = self.currentText() # Save current text before clear
        self.clear()
        self.addItem("---")  # 添加占位符
        if os.path.exists(self.all_songs_folder):
            subdirs = [d for d in os.listdir(self.all_songs_folder) 
                      if os.path.isdir(os.path.join(self.all_songs_folder, d))]
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
            with open(control_file_path, 'w', encoding='utf-8') as f:
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
        
        # 超时计时器：15秒后强制关闭
        def on_timeout():
            print(f"{self.window_title} did not close normally after 15s, forcing shutdown...")
            check_timer.stop()
            if self.exe_process:
                self.exe_process.kill()
                self.exe_process.waitForFinished(500)
                print(f"{self.window_title} force closed")
            event_loop.quit()
        
        timeout_timer.timeout.connect(on_timeout)
        timeout_timer.setSingleShot(True)
        timeout_timer.start(15000)  # 15秒
        
        # 进入事件循环等待（不阻塞Qt主事件循环的消息处理）
        event_loop.exec()






# debug
#--------------------------------------------------------------
# Main Window

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        # 配色方案（从ui_helpers导入）
        self.colors = ui_helpers.COLORS

        # 重要变量
        self.all_songs_folder = os.path.abspath(tools.path_config.final_data_output_dir)
        self.majdata_control_txt = os.path.abspath(tools.path_config.majdata_control_txt)

        # 视频播放器变量
        self.media_player = None
        self.video_sync_server = None
        # Create callback emitter for cross-thread communication
        self.callback_emitter = CallbackEmitter()
        self.callback_emitter.callback_signal.connect(self._execute_callback)
        
        # 导航栏变量
        self.nav_titles = ["MajdataEdit", "Auto Convert", "Audio and PV", "Others"] # 总配置项
        self.current_tab_index = 0     # 当前标签页索引
        self.tab_stacked_widget = None # 内容区堆叠widget
        self.nav_buttons = []          # 4个导航按钮列表
        self.inactive_button_style = f"""
            QPushButton {{
                background-color: {self.colors['surface']}; color: {self.colors['text_secondary']};
                border: none; font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.colors['surface_hover']};
            }}"""
        self.active_button_style = f"""
            QPushButton {{
                background-color: {self.colors['accent']}; color: {self.colors['text_primary']};
                border: none; font-size: 14px; font-weight: bold;
            }}"""
        

        # 程序初始化
        majdata_working_dir = os.path.abspath(tools.path_config.majdata_dir)
        self.Majdata_View_Handler = ExternalProgramHandler("MajdataView", majdata_working_dir)
        self.Majdata_Edit_Handler = ExternalProgramHandler("MajdataEdit", majdata_working_dir)
        self.start_External_Programs()
        self.setup_window()
        self.setup_layout()


    def closeEvent(self, event):

        print("\n---HachimiDX-Convert closing---")
        # 停止视频同步服务器
        print("\n--Closing VideoSync Server...")
        if self.video_sync_server:
            self.video_sync_server.stop()
            print("VideoSync server stopped")
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
        majdata_view_path = os.path.abspath(tools.path_config.majdataView_exe)
        majdata_edit_path = os.path.abspath(tools.path_config.majdataEdit_exe)
        if not os.path.exists(majdata_view_path) or not os.path.exists(majdata_edit_path):
            raise FileNotFoundError("Error: MajdataView.exe or MajdataEdit.exe not found in App/Majdata/")
        # 启动程序
        self.Majdata_View_Handler.start_external_program(majdata_view_path)
        time.sleep(1)
        self.Majdata_Edit_Handler.start_external_program(majdata_edit_path, ["--embed_mode"])
        # 获取窗口句柄
        self.Majdata_View_Handler.find_external_program_hwnd()
        self.Majdata_Edit_Handler.find_external_program_hwnd()

    
    def setup_window(self):
        self.setWindowTitle("HachimiDX-Convert")
        icon_path = os.path.abspath(tools.path_config.app_icon)
        self.setWindowIcon(QIcon(icon_path))
        self.setFixedSize(1300, 900)


    def setup_layout(self):
        # 创建中央widget和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
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
        # media_player
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(lower_left_widget)
        audio_output = QAudioOutput()
        self.media_player.setAudioOutput(audio_output)
        self.media_player.volume = 0 # mute
        # # 连接播放状态改变信号，控制帧数
        # self.media_player.playbackStateChanged.connect(self.on_playback_state_changed)
        # Start video sync server
        self.video_sync_server = server.VideoSyncServer(self.media_player, listen_port=8014)
        self.video_sync_server.set_main_thread_callback(self.execute_in_main_thread)
        self.video_sync_server.start()


        # ----------------------------------------------------------------------
        # 右边区域

        # 右侧区域 - 上下布局包含导航栏和内容区
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # 右侧顶部导航栏
        navigation_bar = QWidget()
        navigation_bar.setFixedHeight(50)
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
        tab_content_area.setStyleSheet(f"background-color: {self.colors['bg']};")
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
        # MajdataEdit 页面
        if title == "MajdataEdit":
            page = MajdataPage(
                majdata_edit_handler=self.Majdata_Edit_Handler,
                media_player=self.media_player,
                all_songs_folder=self.all_songs_folder,
                majdata_control_txt=self.majdata_control_txt,
                colors=self.colors,
                folder_combobox_class=FolderComboBox,
                parent=self
            )
            return page
        
        # 自动转谱页面
        elif title == "Auto Convert":
            page = AutoConvertPage(
                colors=self.colors,
                parent=self
            )
            return page
        
        # 其他页面 - 占位符
        else:
            page = QWidget()
            page.setStyleSheet(f"background-color: {self.colors['bg']}; border-radius: 5px; margin: 8px;")
            page_layout = QVBoxLayout(page)
            page_label = QLabel(f"{title} 内容区域")
            page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_label.setStyleSheet("color: #E0E0E0; font-size: 18px; padding: 20px;")
            page_layout.addWidget(page_label)
            return page
    

    # debug
    # ----------------------------------------------------------------------
    # 业务逻辑函数

    # 在主线程执行回调函数 (视频播放器用的)
    def execute_in_main_thread(self, callback):
        self.callback_emitter.emit_callback(callback)
    
    @pyqtSlot(object)
    def _execute_callback(self, callback):
        try:
            callback()
        except Exception as e:
            import traceback
            print(f"[VideoSync] Error executing callback: {e}")
            traceback.print_exc()


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


    # # 视频暂停时，计算当前帧数
    # @pyqtSlot(QMediaPlayer.PlaybackState)
    # def on_playback_state_changed(self, state):
    #     if state == QMediaPlayer.PlaybackState.PausedState:
    #         # 视频暂停时，获取并显示当前帧数
    #         try:
    #             # 获取当前播放位置（毫秒）
    #             position_ms = self.media_player.position()
    #             # 计算当前帧数
    #             if self.video_fps > 0:
    #                 current_frame = int((position_ms / 1000.0) * self.video_fps)
    #                 # print(f"Current frame: {current_frame}")
    #         except Exception as e:
    #             print(f"Error calculating frame display: {e}")
        # elif state == QMediaPlayer.PlaybackState.PlayingState:
        # elif state == QMediaPlayer.PlaybackState.StoppedState:

        # # 使用OpenCV获取视频帧率
        # try:
        #     cap = cv2.VideoCapture(video_path)
        #     self.video_fps = cap.get(cv2.CAP_PROP_FPS)
        #     cap.release()
        # except Exception as e:
        #     print(f"Error getting video FPS: {e}")




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
