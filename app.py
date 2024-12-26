from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout
from PyQt6.QtCore import QUrl, QProcess, Qt
from PyQt6.QtGui import QWindow
from server import app
import threading
import sys
import win32gui
import time
import win32con

class FlaskThread(threading.Thread):
    def run(self):
        app.run(port=5000)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.chrome_hwnd = None # 存储Chrome窗口句柄
        self.setWindowTitle("Chart Player")
        self.setFixedSize(1536, 864) # 1080p 0.8x
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QGridLayout(central_widget)
        
        # Create placeholder widget for left side
        left_widget = QWidget()
        left_widget.setStyleSheet("background-color: #2b2b2b;")

        # Add left widgets to layout
        layout.addWidget(left_widget, 0, 0, 2, 1)
        
        # Create placeholder for bottom right
        bottom_right = QWidget()
        bottom_right.setStyleSheet("background-color: #2b2b2b;")
        layout.addWidget(bottom_right, 1, 1)
        
        # Start Chrome process
        self.chrome_process = QProcess()
        self.chrome_process.start(
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
            ["--new-window",
             "--app=http://localhost:5000",
             "--incognito"]
        )

        # Find Chrome window with timeout
        start_time = time.time()
        while time.time() - start_time < 10:  # 10 seconds timeout
            def callback(hwnd, extra):
                if win32gui.GetWindowText(hwnd).endswith("MajdataView"):
                    extra.append(hwnd)
                return True
            
            chrome_windows = []
            win32gui.EnumWindows(callback, chrome_windows)
            
            if chrome_windows:
                self.chrome_hwnd = chrome_windows[0] # Store Chrome window handle

                # Create QWindow from Chrome window
                window = QWindow.fromWinId(chrome_windows[0])
                chrome_widget = self.createWindowContainer(window, self)
                chrome_widget.setFixedSize(768, 432)
                
                # Add widgets to layout
                layout.addWidget(chrome_widget, 0, 1)  # Top right
            
                break
                
            time.sleep(0.1)  # Short sleep between attempts
        

    def closeEvent(self, event):
        # 通过窗口句柄关闭Chrome窗口
        if self.chrome_hwnd:
            try:
                win32gui.PostMessage(self.chrome_hwnd, win32con.WM_CLOSE, 0, 0)
            except:
                pass  # 如果窗口已经关闭，忽略错误
        event.accept()

def main():
    flask_thread = FlaskThread(daemon=True)
    flask_thread.start()
    
    qt_app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()