from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QThread, QSize
from server import app
import threading
import sys

class FlaskThread(threading.Thread):
    def run(self):
        app.run(port=5000)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chart Player")
        self.setFixedSize(1536, 864) # 1080p 0.8x
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QGridLayout(central_widget)
        
        # Create placeholder widget for left side
        left_widget = QWidget()
        left_widget.setStyleSheet("background-color: #2b2b2b;")
        
        # Create web view for chart player
        self.web = QWebEngineView()
        self.web.setUrl(QUrl("http://localhost:5000"))
        self.web.setFixedSize(768, 432)
        
        # Add widgets to layout
        layout.addWidget(left_widget, 0, 0, 2, 1)  # Left side
        layout.addWidget(self.web, 0, 1)  # Top right
        
        # Create placeholder for bottom right
        bottom_right = QWidget()
        bottom_right.setStyleSheet("background-color: #2b2b2b;")
        layout.addWidget(bottom_right, 1, 1)
        
        # Set stretch factors
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

def main():
    flask_thread = FlaskThread(daemon=True)
    flask_thread.start()
    
    qt_app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()