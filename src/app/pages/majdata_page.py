from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QUrl, pyqtSlot
from PyQt6.QtGui import QWindow
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from src.services import PathManage, pause_majdata
from ..ui_style import UI_Style
from ..widgets import *
import i18n
from src.core.tools import show_notify_dialog
from src.core.schemas.op_result import OpResult, ok, err, print_op_result



class MajdataPage(QWidget):

    def __init__(self, media_player=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._media_player = media_player # QMediaPlayer 实例，用于控制视频播放
        self._majdataedit_placeholder: Optional[QWidget] = None

        self._main_output_dir: Optional[Path] = None
        self._main_output_dir_error: Optional[str] = None
        self._control_txt: Path = None
        self._option_placeholder = "---"
        self._last_selected_song: str = ""

        self._song_combo = None
        self._maidata_combo = None
        self._track_combo = None
        self._video_combo = None
        self._play_video_checkbox = None

        self._setup_ui()




    def _setup_ui(self) -> None:
    
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top control bar
        top_control_bar = self._setup_control_bar()
        layout.addWidget(top_control_bar)

        # MajdataEdit Embed area
        self._majdataedit_placeholder = QWidget()
        self._majdataedit_placeholder.setStyleSheet(f"background-color: {UI_Style.COLORS['grey']};")
        embed_layout = QVBoxLayout(self._majdataedit_placeholder)
        embed_layout.setContentsMargins(0, 0, 0, 0)
        embed_layout.setSpacing(0)
        layout.addWidget(self._majdataedit_placeholder, 1)



    def set_edit_hwnd(self, hwnd: int) -> None:
        """Embed MajdataEdit by hwnd."""

        # while self._embed_layout.count():
        #     item = self._embed_layout.takeAt(0)
        #     w = item.widget()
        #     if w is not None:
        #         w.setParent(None)
        #         w.deleteLater()

        win = QWindow.fromWinId(hwnd)
        container = QWidget.createWindowContainer(win, self) # parent = self
        self._majdataedit_placeholder.layout().addWidget(container, 1)



    def _setup_control_bar(self) -> QWidget:

        result = PathManage.get_main_output_dir()
        if result.is_ok:
            self._main_output_dir = result.value
        else:
            self._main_output_dir = None # 后续会通过 load 提示
            self._main_output_dir_error = print_op_result(result)
        
        self._control_txt = PathManage.MajdataEdit_CONTROL_TXT_PATH

        bar = QWidget()
        bar.setFixedHeight(50)
        bar.setStyleSheet(f"background-color: {UI_Style.COLORS['text_secondary']};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Folder editable combobox
        self._song_combo = create_folder_combo_box(str(self._main_output_dir), self._option_placeholder, 240)
        layout.addWidget(self._song_combo)
        _song_combo_help = create_help_icon(i18n.t("app.majdata_page.ui_song_help"))
        layout.addWidget(_song_combo_help)
        # Maidata choose
        self._maidata_combo = create_combo_box(140, show_tooltip = True)
        layout.addWidget(self._maidata_combo)
        # Track choose
        self._track_combo = create_combo_box(140, show_tooltip = True)
        layout.addWidget(self._track_combo)
        # Video choose
        self._video_combo = create_combo_box(140, show_tooltip = True)
        layout.addWidget(self._video_combo)
        # CheckBox: play video in MajdataView
        self._play_video_checkbox = create_check_box(True)
        layout.addWidget(self._play_video_checkbox)
        play_video_help = create_help_icon(i18n.t("app.majdata_page.ui_play_video_help"))
        layout.addWidget(play_video_help)
        # Load button
        load_btn = create_button("Load", 60)
        load_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_Style.COLORS['grey']};
            }}
            QPushButton:hover {{
                background-color: {UI_Style.COLORS['grey_hover']};
            }}
        """)
        layout.addWidget(load_btn)

        # connect
        self._song_combo.currentTextChanged.connect(self.on_song_changed)
        load_btn.clicked.connect(self.on_load_clicked)

        return bar







    def on_song_changed(self) -> None:
        """Scan and update maidata, track, video comboboxes when song changes."""

        if self._main_output_dir is None:
            return

        # Check song
        song = self._song_combo.currentText()
        if not song or song == self._option_placeholder or song == self._last_selected_song:
            return
        song_path = self._main_output_dir / song
        if not song_path.exists():
            return

        # Update last selection
        self._last_selected_song = song

        # Clear combobox
        self._maidata_combo.clear()
        self._track_combo.clear()
        self._video_combo.clear()

        # scan txt and add to maidata_combo
        txt_files = [f for f in os.listdir(song_path)
                     if f.lower().endswith(".txt")
                     and f.lower() not in ("track_result.txt", "detect_result.txt")]
        if txt_files:
            txt_files = sorted(txt_files)
            self._maidata_combo.addItems(txt_files)
            # 如果有 maidata.txt，优先选择它
            if "maidata.txt" in txt_files:
                index = txt_files.index("maidata.txt")
                self._maidata_combo.setCurrentIndex(index)
            # 否则默认选择第一个
            else:
                self._maidata_combo.setCurrentIndex(0)

        # scan mp3/ogg and add to track_combo
        audio_files = [f for f in os.listdir(song_path)
                       if f.lower().endswith((".mp3", ".ogg"))]
        if audio_files:
            self._track_combo.addItems(sorted(audio_files))
            self._track_combo.setCurrentIndex(0)

        # scan mp4 and add to video_combo
        video_files = [f for f in os.listdir(song_path)
                       if f.lower().endswith(".mp4")]
        if video_files:
            self._video_combo.addItems(sorted(video_files))
            self._video_combo.setCurrentIndex(0)



    @pyqtSlot()
    def on_load_clicked(self) -> None:

        if self._main_output_dir is None:
            show_notify_dialog(
                "app.majdata_page.load_button",
                self._main_output_dir_error
            )
            return
        
        selected_song = self._song_combo.currentText()

        # Special case for options placeholder
        if selected_song == self._option_placeholder:
            self.reset_majdataview()
            return
        
        selected_maidata = self._maidata_combo.currentText()
        selected_track = self._track_combo.currentText()
        selected_video = self._video_combo.currentText()
        is_play_video = self._play_video_checkbox.isChecked()

        if not selected_song or not selected_maidata or not selected_track:
            return

        majdataview_has_video = bool(selected_video and is_play_video)

        # Reset video player
        if self._media_player is not None:
            self._media_player.stop()
            self._media_player.setSource(QUrl())

        # Create a control txt for MajdataEdit
        song_path = self._main_output_dir / selected_song
        control_text = f"folder: {song_path}\nmaidata: {selected_maidata}\ntrack: {selected_track}"
        if majdataview_has_video:
            control_text += f"\nmovie: {selected_video}"

        try:
            self._control_txt.write_text(control_text, encoding="utf-8")
        except Exception as e:
            print(f"Error writing to MajdataEdit control file: {e}")
        
        # Load video to media player (if applicable)
        # 在 control_file 创建完成后才检查 video 是否存在
        if not selected_video:
            return

        video_path = song_path / selected_video
        if self._media_player is not None:
            self._media_player.setSource(QUrl.fromLocalFile(str(video_path)))
            self._media_player.pause()



    def reset_majdataview(self) -> None:

        # 1. Reset video player
        if self._media_player is not None:
            self._media_player.stop()
            self._media_player.setSource(QUrl())

        # 2. Pause majdata
        pause_majdata()

        # 3. Clear comboboxes
        self._maidata_combo.clear()
        self._track_combo.clear()
        self._video_combo.clear()

        # 4. Reset last selected song
        self._last_selected_song = ""

        return
