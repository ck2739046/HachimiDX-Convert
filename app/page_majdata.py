from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel)
from PyQt6.QtCore import QUrl, pyqtSlot
from PyQt6.QtGui import QWindow
import os
import ui_helpers


class MajdataPage(QWidget):
    
    def __init__(self, 
                 majdata_edit_handler,  # ExternalProgramHandler 实例，用于获取 MajdataEdit 窗口句柄
                 media_player,          # QMediaPlayer 实例，用于控制视频播放
                 all_songs_folder,      # 歌曲文件夹路径
                 majdata_control_txt,   # MajdataEdit 控制文件路径
                 folder_combobox_class, # FolderComboBox 类引用
                 parent=None):          # 父 widget

        super().__init__(parent)
        
        # 保存传入的依赖
        self.majdata_edit_handler = majdata_edit_handler
        self.media_player = media_player
        self.all_songs_folder = all_songs_folder
        self.majdata_control_txt = majdata_control_txt
        self.colors = ui_helpers.COLORS
        self.FolderComboBox = folder_combobox_class
        
        # 其他公共变量
        self.majdata_song_input = None
        self.majdata_maidata_choose = None
        self.majdata_track_choose = None
        self.majdata_video_choose = None
        self.is_majdataview_play_video_checkbox = None
        self.majdata_last_selection = ""  # 记录上次选择的歌曲
        
        # 设置页面布局
        self.setup_ui()
    
    
    def setup_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        
        # 上面是选择文件控制面板
        control_panel_widget = self.create_control_panel()
        page_layout.addWidget(control_panel_widget)
        
        # 下面嵌入 MajdataEdit 窗口
        majdata_edit_window = QWindow.fromWinId(self.majdata_edit_handler.exe_hwnd)
        majdata_edit_widget = self.createWindowContainer(majdata_edit_window, self)
        page_layout.addWidget(majdata_edit_widget)
    
    
    def create_control_panel(self):
        widget = QWidget()
        widget.setFixedHeight(40)
        widget.setStyleSheet(f"background-color: {self.colors['text_secondary']};")
        layout = QHBoxLayout(widget)
        
        # Folder editable combobox
        self.majdata_song_input = self.FolderComboBox(self.all_songs_folder)
        self.majdata_song_input.setStyleSheet(f"background-color: {self.colors['grey']};")
        self.majdata_song_input.setEditable(True)
        self.majdata_song_input.setFixedSize(230, 25)
        self.majdata_song_input.currentTextChanged.connect(self.on_song_changed)
        layout.addWidget(self.majdata_song_input)
        
        # Maidata choose
        self.majdata_maidata_choose = ui_helpers.create_combo_box(150, show_tooltip=True)
        layout.addWidget(self.majdata_maidata_choose)
        
        # Track choose
        self.majdata_track_choose = ui_helpers.create_combo_box(150, show_tooltip=True)
        layout.addWidget(self.majdata_track_choose)
        
        # Video choose
        self.majdata_video_choose = ui_helpers.create_combo_box(150, show_tooltip=True)
        layout.addWidget(self.majdata_video_choose)

        # CheckBox_Helper is_majdataview_play_video
        self.is_majdataview_play_video_checkbox = ui_helpers.create_check_box()
        self.is_majdataview_play_video_checkbox.setChecked(True)  # 默认启用
        layout.addWidget(self.is_majdataview_play_video_checkbox)
        is_majdataview_play_video_help = ui_helpers.create_help_icon(
            "勾选：视频会在左上 MajdataView 和左下视频播放器中都播放\n" \
            "不勾选：视频只在左下视频播放器中播放")
        layout.addWidget(is_majdataview_play_video_help)
        
        # Load button
        load_button = QPushButton("Load")
        load_button.setStyleSheet(f"background-color: {self.colors['grey']};")
        load_button.setFixedSize(60, 25)
        load_button.clicked.connect(self.on_load_clicked)
        layout.addWidget(load_button)
        
        # layout.addStretch()
        return widget
    
    
    @pyqtSlot()
    def on_song_changed(self):
        # Check song
        song = self.majdata_song_input.currentText()
        if not song or song == "---" or song == self.majdata_last_selection:
            return
        song_path = os.path.join(self.all_songs_folder, song)
        if not os.path.exists(song_path):
            return
        
        # Update last selection
        self.majdata_last_selection = song
        
        # Clear combobox
        self.majdata_maidata_choose.clear()
        self.majdata_track_choose.clear()
        self.majdata_video_choose.clear()
        
        # Add all txt files to maidata_choose
        txt_files = [f for f in os.listdir(song_path)
                     if f.lower().endswith('.txt') and
                     f.lower() not in ('track_result.txt', 'detect_result.txt')]
        self.majdata_maidata_choose.addItems(sorted(txt_files))
        # 如果有 maidata.txt，优先选择它
        if 'maidata.txt' in txt_files:
            index = txt_files.index('maidata.txt')
            self.majdata_maidata_choose.setCurrentIndex(index)
        # 如果第一个选项以 '.bak.txt' 结尾，选择下一个
        elif txt_files and txt_files[0].lower().endswith('.bak.txt') and len(txt_files) > 1:
            self.majdata_maidata_choose.setCurrentIndex(1)
        # 否则默认选择第一个
        else:
            self.majdata_maidata_choose.setCurrentIndex(0)
        
        # Add all mp3/ogg files to track_choose
        audio_files = [f for f in os.listdir(song_path) 
                      if f.lower().endswith(('.mp3', '.ogg'))]
        self.majdata_track_choose.addItems(sorted(audio_files))
        self.majdata_track_choose.setCurrentIndex(0)
        
        # Add all mp4/mkv files to video_choose
        video_files = [f for f in os.listdir(song_path) 
                      if f.lower().endswith(('.mp4', '.mkv'))]
        self.majdata_video_choose.addItems(sorted(video_files))
        self.majdata_video_choose.setCurrentIndex(0)
    
    
    @pyqtSlot()
    def on_load_clicked(self):
        # Get selected items
        selected_song = self.majdata_song_input.currentText()
        selected_maidata = self.majdata_maidata_choose.currentText()
        selected_track = self.majdata_track_choose.currentText()
        selected_video = self.majdata_video_choose.currentText()
        is_play_video = self.is_majdataview_play_video_checkbox.isChecked()
        
        if not selected_song or not selected_maidata or not selected_track:
            return
        
        if selected_video and is_play_video:
            majdataview_has_video = True
        else:
            majdataview_has_video = False
        
        # Reset video player
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        
        # Create a control txt for MajdataEdit
        song_path = os.path.join(self.all_songs_folder, selected_song)
        control_txt = f"folder: {song_path}\nmaidata: {selected_maidata}\ntrack: {selected_track}"
        if majdataview_has_video:
            control_txt += f"\nmovie: {selected_video}"
        
        try:
            with open(self.majdata_control_txt, 'w', encoding='utf-8') as f:
                f.write(control_txt)
            print("Wrote MajdataEdit control file:")
            print(control_txt)
        except Exception as e:
            print(f"Error writing to MajdataEdit control file: {e}")
            return
        
        # Load video to media player (if applicable)
        # 在 control_file 创建完成后才检查 video 是否存在
        if not selected_video:
            return
        
        video_path = os.path.join(song_path, selected_video)
        self.media_player.setSource(QUrl.fromLocalFile(video_path))
        self.media_player.pause()
