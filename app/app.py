from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox)
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
    # Close chrome before exiting
    try:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == 'launch_web.exe':
                    proc.kill()
                    print("Browser closed")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except:
        pass
    # Print the original error
    sys.__excepthook__(exctype, value, traceback)
    print("---HachimiDX-Convert quit in exception_handler---")
    print("Press ignore the following QProcess error:")
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
                time.sleep(0.5) # wait 0.5s for loading
                self.exe_hwnd = external_windows[0]
                return self.exe_hwnd
            time.sleep(0.1)
        print("External program window not found")
        return None

    def close_external_program(self):
        if self.exe_hwnd:
            try:
                win32gui.PostMessage(self.exe_hwnd, win32con.WM_CLOSE, 0, 0)
            except:
                pass
        time.sleep(0.2)
        if self.chrome_process:
            self.chrome_process.kill()
            print(" quit normally")







# debug
#--------------------------------------------------------------
# Main Window

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.Majdata_Edit_Handler = ExternalProgramHandler("MajdataEdit")
        self.Majdata_View_Handler = ExternalProgramHandler("MajdataView")
        self.setup_window()
        self.setup_layout()
        # 全局变量
        self.last_selection = "" # 全局变量，song_input用的，记录上次选择的歌曲
        self.video_fps = 0       # 全局变量，上/下一帧按钮用的，存储视频fps
        


    def setup_window(self):
        self.setWindowTitle("HachimiDX-Convert")
        icon_path = os.path.join(os.path.dirname(__file__), 'static', 'maimai.ico')
        self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(700, 450)  # 最小尺寸
        self.resize(1400, 900)         # 初始尺寸
        self.setAspectRatio(1400, 900) # 固定宽高比


    def setup_layout(self):


        
























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
