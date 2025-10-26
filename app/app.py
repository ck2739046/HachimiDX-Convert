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
    print("---mai chart analyze quit in exception_handler---")
    print("Press ignore the following QProcess error:")
    sys.exit(1)


#--------------------------------------------------------------
# Initialize Class

class FlaskThread(threading.Thread):
    def run(self):
        server.app.run(port=5273)

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

class ChromeHandler:
    def __init__(self):
        self.chrome_hwnd = None
        self.chrome_process = None
    
    def start_chrome(self):
        self.chrome_process = QProcess()
        pywebview = os.path.join(os.path.dirname(__file__), 'static', 'launch_web.exe')
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
                time.sleep(0.4) # wait for loading
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
            print("mai chart analyze quit normally")

#--------------------------------------------------------------
# Main Class

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.chrome_handler = ChromeHandler()
        self.last_selection = "" # 全局变量，song_input用的，记录上次选择的歌曲
        self.video_fps = 0       # 全局变量，上/下一帧按钮用的，存储视频fps
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
        # Create video_layout: left video and right video
        video_layout = QHBoxLayout()
        video_layout.setSpacing(9)
        
        # Create single media player with audio output
        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        # Create video widget
        self.videoWidget = QVideoWidget()
        self.videoWidget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding) # let video fill the widget
        self.mediaPlayer.setVideoOutput(self.videoWidget)
        video_layout.addWidget(self.videoWidget)

        # Add video layout to main layout
        layout.addLayout(video_layout)

        #------------------------------------------------------
        # Create controls_layout: playButton and positionSlider
        controls_layout = QHBoxLayout()
        
        # Play/Pause button
        self.playButton = QPushButton()
        self.playButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.playButton.clicked.connect(self.play_video)
        self.playButton.setEnabled(False)  # 初始状态为禁用
        controls_layout.addWidget(self.playButton)
        
        # Previous frame button
        self.prevFrameButton = QPushButton()
        self.prevFrameButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft))
        self.prevFrameButton.clicked.connect(self.goto_last_frame)
        self.prevFrameButton.setEnabled(False)  # 初始状态为禁用
        controls_layout.addWidget(self.prevFrameButton)
        
        # Next frame button
        self.nextFrameButton = QPushButton()
        self.nextFrameButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight))
        self.nextFrameButton.clicked.connect(self.goto_next_frame)
        self.nextFrameButton.setEnabled(False)  # 初始状态为禁用
        controls_layout.addWidget(self.nextFrameButton)
        
        # Position slider
        self.positionSlider = QSlider(Qt.Orientation.Horizontal)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.set_position)
        self.positionSlider.sliderReleased.connect(self.on_slider_released)
        self.positionSlider.sliderPressed.connect(self.on_slider_pressed)
        controls_layout.addWidget(self.positionSlider)
        
        # Add controls to main layout
        layout.addLayout(controls_layout)

        # Initialize slider state
        self.was_playing = False

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

    def on_slider_pressed(self):
        # When slider is pressed (click), pause the video temporarily
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
            self.was_playing = True
        else:
            self.was_playing = False

    def on_slider_released(self):
        # When slider is released (including click), update the position
        position = self.positionSlider.value()
        self.mediaPlayer.setPosition(position)
        # Resume playback if it was playing before
        if self.was_playing:
            self.mediaPlayer.play()

    def goto_last_frame(self):
        # 如果视频没有加载，不执行任何操作
        if not self.mediaPlayer.source().isValid(): return
        if self.video_fps <= 1: return
        # 如果视频正在播放，先暂停
        self.was_playing = False
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
        # 获取当前帧时间（毫秒）
        current_pos = self.mediaPlayer.position()
        # 计算帧间隔（基于实际fps）
        frame_interval = int(1000 / self.video_fps) + 1 # 避免浮点数误差
        # 设置新位置（上一帧）
        new_pos = max(0, current_pos - frame_interval)
        self.mediaPlayer.setPosition(new_pos)

    def goto_next_frame(self):
        # 如果视频没有加载，不执行任何操作
        if not self.mediaPlayer.source().isValid(): return
        if self.video_fps <= 1: return
        # 如果视频正在播放，先暂停
        self.was_playing = False
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
        # 获取当前帧时间（毫秒）
        current_pos = self.mediaPlayer.position()
        # 计算帧间隔（基于实际fps）
        frame_interval = int(1000 / self.video_fps) + 1 # 避免浮点数误差
        # 设置新位置（下一帧）
        duration = self.mediaPlayer.duration()
        new_pos = min(duration, current_pos + frame_interval)
        self.mediaPlayer.setPosition(new_pos)

    def load_video(self, filepath):
        # 加载新视频
        self.mediaPlayer.setSource(QUrl.fromLocalFile(filepath))
        # 启用播放按钮和帧导航按钮
        self.playButton.setEnabled(True)
        self.prevFrameButton.setEnabled(True)
        self.nextFrameButton.setEnabled(True)
        # Update button color after load
        self.playButton.setStyleSheet("background-color: #C0C0C0;")
        self.prevFrameButton.setStyleSheet("background-color: #C0C0C0;")
        self.nextFrameButton.setStyleSheet("background-color: #C0C0C0;")
        # 重置参数
        self.positionSlider.setValue(0)
        self.was_playing = False
        # 视频加载后暂停
        self.mediaPlayer.pause()
    
    def clear_videos(self):
        # 停止播放
        self.mediaPlayer.stop()
        # 卸载视频源
        self.mediaPlayer.setSource(QUrl())
        # 重置进度条
        self.positionSlider.setRange(0, 0)
        self.positionSlider.setValue(0)
        # 重置播放按钮状态
        self.playButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        # 禁用播放按钮和帧导航按钮
        self.playButton.setEnabled(False)
        self.prevFrameButton.setEnabled(False)
        self.nextFrameButton.setEnabled(False)

#--------------------------------------------------------------
# Sub setup_layout: setup middle right control panel

    def setup_control_panel(self, control_widget):
        layout = QHBoxLayout(control_widget)
        
        # Song editable combobox
        self.song_input = FolderComboBox()
        self.song_input.setEditable(True)
        self.song_input.setFixedWidth(180)
        self.song_input.currentTextChanged.connect(self.on_song_changed)
        layout.addWidget(self.song_input)

        # Track choose
        self.track_choose = QComboBox()
        self.track_choose.setFixedWidth(100)
        layout.addWidget(self.track_choose)
        
        # Level choose
        self.level_choose = QComboBox()
        self.level_choose.setFixedWidth(41)
        layout.addWidget(self.level_choose)
        
        # First input
        self.first_input = QLineEdit()
        self.first_input.setFixedWidth(65)
        self.first_input.setPlaceholderText("&first")
        self.first_input.setEnabled(False)  # 初始禁用
        self.first_input.textChanged.connect(self.on_first_changed)
        layout.addWidget(self.first_input)
        
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
    #Update track and level combobox and auto load videos
    def on_song_changed(self):
        # Check song
        song = self.song_input.currentText()
        if not song or song == "---" or song == self.last_selection:
            # 临时禁用
            self.track_choose.setEnabled(False)
            self.level_choose.setEnabled(False)
            self.first_input.setEnabled(False)
            return
        song_path = os.path.join(server.song_folder, song)
        if not os.path.exists(song_path):
            return
        # Clear combobox
        self.track_choose.clear()
        self.level_choose.clear()
        self.first_input.clear()
        # Get all mp3/ogg files in the song_path
        audio_files = []
        for f in os.listdir(song_path):
            if f.endswith('.mp3') or f.endswith('.ogg'):
                audio_files.append(f)
        # Update track combobox
        if audio_files:
            self.track_choose.setEnabled(True)
            audio_files.sort()
            for audio_file in audio_files:
                self.track_choose.addItem(audio_file)
            self.track_choose.setCurrentIndex(len(audio_files) - 1)
        # Get &first and all levels in maidata.txt
        maidata_path = os.path.join(song_path, 'maidata.txt')
        if not os.path.exists(maidata_path):
            return
        with open(maidata_path, encoding='utf-8') as f:
            data = f.read()
        levels = []
        first_value = None
        for line in data.splitlines():
            if line.startswith('&inote_'):
                levels.append(line[7])
            if line.startswith('&first'):
                first_value = line.split('=')[1].strip()  # 去掉'&first='部分
        # Update level combobox
        if levels:
            self.level_choose.setEnabled(True)
            levels.sort(reverse=True)
            for level in levels:
                self.level_choose.addItem(level)
            self.level_choose.setCurrentIndex(0)
        # Set first input
        if first_value:
            self.first_input.setEnabled(True)
            self.first_input.setText(first_value)
        # 自动加载视频
        self.auto_load_videos(song_path)
        # 更新last_selection
        self.last_selection = song

    def auto_load_videos(self, song_path):
        # 安全清理当前视频（如果有）
        self.clear_videos()
        # 查找以"_tracked"结尾的MP4文件
        mp4_files = [f for f in os.listdir(song_path) if f.endswith('.mp4')]
        tracked_video = None
        for file in mp4_files:
            if file.endswith('_tracked.mp4'):
                tracked_video = file
                break
        # 检查是否找到视频
        if not tracked_video:
            print("未找到_tracked视频文件")
            return
        tracked_path = os.path.join(song_path, tracked_video)
        # 使用OpenCV获取视频FPS
        try:
            cap = cv2.VideoCapture(tracked_path)
            self.video_fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
        except Exception as e:
            print(f"获取视频FPS错误: {e}")
            self.video_fps = 0
        # 加载视频
        self.load_video(tracked_path)

    def on_first_changed(self):
        # 过滤无效输入
        song = self.song_input.currentText()
        if not song or song == "---": return
        first_text = self.first_input.text().strip()
        if not first_text: return  
        # 验证输入格式
        try:
            first_value = float(first_text)
            if first_value < -1000 or first_value > 1000:
                print("first out of range (±999)")
                return
            decimal_part = first_text.split('.')[-1] if '.' in first_text else '0'
            if len(decimal_part) > 3:
                print("first is up to 3 decimal places (0.001)")
                return
        except ValueError:
            #print("first value format error")
            return
        # 更新maidata.txt文件
        song_path = os.path.join(server.song_folder, song)
        maidata_path = os.path.join(song_path, 'maidata.txt')
        if not os.path.exists(maidata_path): return
        try:
            with open(maidata_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith('&first='):
                    lines[i] = f'&first={first_text}\n'
                    break
            with open(maidata_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)    
        except Exception as e:
            print(f"error updating maidata.txt &first value: {e}")

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