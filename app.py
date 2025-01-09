from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox)
from PyQt6.QtCore import QUrl, QProcess, Qt
from PyQt6.QtGui import QWindow, QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QStyle, QSlider, QFileDialog
import threading
import sys
import win32gui
import time
import win32con
from PyQt6.QtCore import pyqtSlot
import server
import os
import psutil

#--------------------------------------------------------------
# Initialize Class

class FlaskThread(threading.Thread):
    def run(self):
        server.app.run(port=5273)

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
    print("Press ignore the following QProcess error:")
    sys.exit(1)

class FolderComboBox(QComboBox):

    def mousePressEvent(self, event):
        current_text = self.currentText() # Save current text before clear
        self.clear()
        if os.path.exists(server.song_folder):
            subdirs = [d for d in os.listdir(server.song_folder) 
                      if os.path.isdir(os.path.join(server.song_folder, d))]
            self.addItems(subdirs)
            
        # Restore previous selection if it exists
        if current_text:
            index = self.findText(current_text)
            if index >= 0:
                self.setCurrentIndex(index)
            else:
                self.setCurrentText(current_text)
                
        super().mousePressEvent(event)

class ChromeHandler:
    def __init__(self):
        self.chrome_hwnd = None
        self.chrome_process = None
    
    def start_chrome(self):
        self.chrome_process = QProcess()
        pywebview = os.path.join(os.path.dirname(__file__), 'launch_web.exe')
        self.chrome_process.start(pywebview)

    def find_chrome_window(self, timeout=5):

        def callback(hwnd, extra):
                if win32gui.GetWindowText(hwnd).startswith("MajdataView"):
                    extra.append(hwnd)
                return True
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            chrome_windows = []
            win32gui.EnumWindows(callback, chrome_windows)
            if chrome_windows:
                self.chrome_hwnd = chrome_windows[0]
                return self.chrome_hwnd
            time.sleep(0.1)
        print("Browser window not found")
        return None
    
    def close_chrome(self):
        if self.chrome_hwnd:
            try:
                win32gui.PostMessage(self.chrome_hwnd, win32con.WM_CLOSE, 0, 0)
            except:
                pass
        time.sleep(0.2)
        if self.chrome_process:
            self.chrome_process.kill()

#--------------------------------------------------------------
# Main Class

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.chrome_handler = ChromeHandler()
        self.setup_window()
        self.setup_layout()

    def setup_window(self):
        self.setWindowTitle("Mai Chart Analyze")
        self.setFixedSize(1536, 864)
        icon_path = os.path.join(os.path.dirname(__file__), 'static', 'maimai.ico')
        self.setWindowIcon(QIcon(icon_path))

    def setup_layout(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout to split left half and right half
        main_layout = QHBoxLayout(central_widget)
        
        # Left widget
        left_widget = QWidget()
        left_widget.setStyleSheet("background-color: #2b2b2b;")
        main_layout.addWidget(left_widget)
        
        # Right container widget
        right_widget = QWidget()
        right_layout = QGridLayout(right_widget)
        right_layout.setVerticalSpacing(0) # Remove vertical spacing
        right_layout.setContentsMargins(2, 0, 0, 0) # Remove outer margins, avoid double margins
        
        # Top right widget (Chrome MajdataView)
        self.setup_chrome()
        right_layout.addWidget(self.chrome_widget, 0, 0)
        
        # Middle right widget (Control Panel)
        control_widget = QWidget()
        control_widget.setFixedHeight(40)
        control_widget.setStyleSheet("background-color: #2b2b2b;")
        self.setup_control_panel(control_widget)
        right_layout.addWidget(control_widget, 1, 0)

        # Gap between middle and bottom
        gap = QWidget()
        gap.setFixedHeight(9)
        gap.setStyleSheet("background-color: #1e1e1e;")
        right_layout.addWidget(gap, 2, 0)
        
        # Bottom right widget (Video Player)
        bottom_right = QWidget()
        bottom_right.setStyleSheet("background-color: #2b2b2b;")
        self.setup_video_player(bottom_right)
        right_layout.addWidget(bottom_right, 3, 0)
        
        # Add the right container to main layout
        main_layout.addWidget(right_widget)
        
        # Set size ratio between left and right (1:1)
        main_layout.setStretch(0, 1)  # Left side
        main_layout.setStretch(1, 1)  # Right side

    def setup_chrome(self):
        self.chrome_handler.start_chrome()
        chrome_hwnd = self.chrome_handler.find_chrome_window()
        if chrome_hwnd:
            window = QWindow.fromWinId(chrome_hwnd)
            self.chrome_widget = self.createWindowContainer(window, self)
            self.chrome_widget.setFixedHeight(384)

    def closeEvent(self, event):
        self.chrome_handler.close_chrome()
        event.accept()

#--------------------------------------------------------------
# Sub setup_layout: setup bottom right video player

    def setup_video_player(self, container):
        # Create main layout: video_layout and controls_layout
        layout = QVBoxLayout(container)

        #------------------------------------------------------
        # Create video_layout: videoWidget and right_panel
        video_layout = QHBoxLayout()
        video_layout.setSpacing(9)
        
        # Create media player with audio output
        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        # Create video widget
        self.videoWidget = QVideoWidget()
        self.videoWidget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding) # let video fill the widget
        self.mediaPlayer.setVideoOutput(self.videoWidget)
        video_layout.addWidget(self.videoWidget)

        # Create right panel
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #1e1e1e;")
        video_layout.addWidget(right_panel)

        # Add video layout to main layout
        layout.addLayout(video_layout)

        #------------------------------------------------------
        # Create controls_layout: playButton and positionSlider
        controls_layout = QHBoxLayout()
        
        # Play/Pause button
        self.playButton = QPushButton()
        self.playButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.playButton.clicked.connect(self.play_video)
        controls_layout.addWidget(self.playButton)
        
        # Position slider
        self.positionSlider = QSlider(Qt.Orientation.Horizontal)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.set_position)
        controls_layout.addWidget(self.positionSlider)
        
        # Add controls to main layout
        layout.addLayout(controls_layout)

        #------------------------------------------------------
        # Connect media player signals
        self.mediaPlayer.positionChanged.connect(self.position_changed)
        self.mediaPlayer.durationChanged.connect(self.duration_changed)
        self.mediaPlayer.playbackStateChanged.connect(self.mediastate_changed)

    def play_video(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def mediastate_changed(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.playButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.playButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def position_changed(self, position):
        self.positionSlider.setValue(position)

    def duration_changed(self, duration):
        self.positionSlider.setRange(0, duration)

    def set_position(self, position):
        self.mediaPlayer.setPosition(position)

    def load_video(self, filepath):
        self.mediaPlayer.setSource(QUrl.fromLocalFile(filepath))
        self.playButton.setEnabled(True)
        # Update button color after load
        self.playButton.setStyleSheet("background-color: #C0C0C0;")

#--------------------------------------------------------------
# Sub setup_layout: setup middle right control panel

    def setup_control_panel(self, control_widget):
        layout = QHBoxLayout(control_widget)
        
        # Song editable combobox
        self.song_input = FolderComboBox()
        self.song_input.setEditable(True)
        self.song_input.setFixedWidth(130)
        self.song_input.currentTextChanged.connect(self.on_song_changed)
        layout.addWidget(self.song_input)

        # Track choose
        self.track_choose = QComboBox()
        self.track_choose.setFixedWidth(130)
        layout.addWidget(self.track_choose)
        
        # Level choose
        self.level_choose = QComboBox()
        self.level_choose.setFixedWidth(41)
        layout.addWidget(self.level_choose)
        
        # Load button
        load_button = QPushButton("Load")
        load_button.setFixedWidth(60)
        load_button.clicked.connect(self.on_load_clicked)
        layout.addWidget(load_button)

        # Refresh button
        refresh_button = QPushButton("Refresh")
        refresh_button.setFixedWidth(60)
        refresh_button.clicked.connect(self.on_refresh_clicked)
        layout.addWidget(refresh_button)

        # Load Video button
        load_video_button = QPushButton("Load Video")
        load_video_button.setFixedWidth(80)
        load_video_button.clicked.connect(self.on_load_video_clicked)
        layout.addWidget(load_video_button)
        
        # Add spacing for future buttons
        layout.addStretch()

    @pyqtSlot()
    def on_load_clicked(self):
        song = self.song_input.currentText()
        track = self.track_choose.currentText()
        level = self.level_choose.currentText()
        if not song or not track or not level: return
        server.MajdataView_load_chart(song, track, level)

    @pyqtSlot()
    def on_refresh_clicked(self):
        server.MajdataView_refresh_page()

    @pyqtSlot()
    def on_load_video_clicked(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video",
            "",
            "Video Files (*.mp4);;All Files (*.*)"
        )
        if filepath:
            self.load_video(filepath)

    @pyqtSlot()
    #Update track and level combobox
    def on_song_changed(self):

        # Check song
        song = self.song_input.currentText()
        if not song:
            return   
        song_path = os.path.join(server.song_folder, song)
        if not os.path.exists(song_path):
            return
        # Clear combobox
        self.track_choose.clear()
        self.level_choose.clear()
        # Get all mp3/ogg files in the song_path
        audio_files = []
        for f in os.listdir(song_path):
            if f.endswith('.mp3') or f.endswith('.ogg'):
                audio_files.append(f)
        # Update track combobox
        audio_files.sort()
        for audio_file in audio_files:
            self.track_choose.addItem(audio_file)
        self.track_choose.setCurrentIndex(len(audio_files) - 1)
        # Get all levels in maidata.txt
        maidata_path = os.path.join(song_path, 'maidata.txt')
        if not os.path.exists(maidata_path):
            return
        with open(maidata_path, encoding='utf-8') as f:
            data = f.read()
        levels = []
        for line in data.splitlines():
            if line.startswith('&inote_'):
                levels.append(line[7])
        # Update level combobox
        levels.sort(reverse=True)
        for level in levels:
            self.level_choose.addItem(level)
        self.level_choose.setCurrentIndex(0)

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