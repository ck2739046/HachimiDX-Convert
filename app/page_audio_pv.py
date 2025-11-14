from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLineEdit, QMessageBox)
from PyQt6.QtGui import QDoubleValidator, QCursor
from PyQt6.QtCore import Qt
import os
import sys
import time
import re

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config

from process_widgets import ProcessControlButton, OutputTextWidget
import ui_helpers



class AudioPvPage(QWidget):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.colors = ui_helpers.COLORS
        
        # Section 1: 分析 &first 数值
        self.video_path_label_1 = None
        self.selected_video_path_1 = None
        self.initial_bpm_input = None
        self.result_label = None
        
        # Section 2: 对齐文件
        self.audio_video_path_label = None
        self.selected_audio_video_path = None
        
        # 进程控制按钮
        self.analyze_button = None # 第二行
        # 输出区组件
        self.output_widget = None
        
        # 设置页面布局
        self.setup_ui()
    
    

    def setup_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        
        # 上半部分：配置区
        config_widget = self.create_config_area()
        page_layout.addWidget(config_widget)
        
        # 下半部分：输出区
        self.output_widget = OutputTextWidget(max_lines=400)
        page_layout.addWidget(self.output_widget)
        
        # 配置所有进程控制按钮
        self._configure_buttons()
    
    

    # debug
    def create_config_area(self):

        widget = QWidget()
        widget.setStyleSheet(f"background-color: {self.colors['bg']};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题分隔线：分析 &first 数值
        layout.addWidget(ui_helpers.create_divider("分析 &first 数值", 0, 5, width=100))
        # 第一行：选择谱面确认视频
        first_row = self.setup_1st_row()
        layout.addWidget(first_row)
        # 第二行：Initial BPM + 开始分析按钮 + 结果 label
        second_row = self.setup_2nd_row()
        layout.addWidget(second_row)
        
        # 标题分隔线：对齐文件
        layout.addWidget(ui_helpers.create_divider("对齐文件"))
        # 第三行：选择音频/视频
        third_row = self.setup_3rd_row()
        layout.addWidget(third_row)
        
        layout.addSpacing(5)
        layout.addStretch()  # 添加弹性空间
        return widget
    

    
    def setup_1st_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        
        # 按钮: "选择谱面确认视频"
        select_video_button = QPushButton("选择谱面确认视频")
        select_video_button.setStyleSheet(f'''
            QPushButton {{
                background-color: {self.colors['accent']};
            }}QPushButton:hover {{
                background-color: {self.colors['accent_hover']};
            }}''')
        select_video_button.setFixedSize(120, 25)
        select_video_button.clicked.connect(self._on_select_video_1)
        row_layout.addWidget(select_video_button)
        
        # LineEdit: 显示选择的视频路径
        self.video_path_label_1 = QLineEdit("")
        self.video_path_label_1.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 13px;")
        self.video_path_label_1.setReadOnly(True)
        self.video_path_label_1.setFixedHeight(25)
        self.video_path_label_1.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.video_path_label_1.setFrame(False)
        row_layout.addWidget(self.video_path_label_1)
        
        return row
    
    

    def _on_select_video_1(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("video/audio (*.mkv *.mp4 *.webm *.avi *.mp3 *.ogg *.wav)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.selected_video_path_1 = os.path.normpath(os.path.abspath(selected_files[0]))
                self.video_path_label_1.setText(self.selected_video_path_1)
    
    

    def setup_2nd_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        
        # Label_LineEdit_Helper Initial BPM
        initial_bpm_label = ui_helpers.create_label("Initial BPM:")
        row_layout.addWidget(initial_bpm_label)
        
        bpm_validator = QDoubleValidator(10.0, 999.0, 3, self)  # 10-999 的浮点数
        self.initial_bpm_input = ui_helpers.create_line_edit(70, validator=bpm_validator, placeholder="10~999")
        row_layout.addWidget(self.initial_bpm_input)
        
        bpm_help = ui_helpers.create_help_icon("启动拍的 BPM 数值")
        row_layout.addWidget(bpm_help)
        
        # 按钮: "开始分析"
        self.analyze_button = ProcessControlButton("开始分析")
        self.analyze_button.setFixedSize(80, 25)
        row_layout.addWidget(self.analyze_button)
        row_layout.addSpacing(5)
        
        # Label: 显示结果（默认隐藏）
        self.result_label = ui_helpers.create_label("估值:")
        self.result_label.setStyleSheet(f"color: {self.colors['accent']}; font-size: 13px; font-weight: bold;")
        self.result_label.hide()
        row_layout.addWidget(self.result_label)
        
        row_layout.addStretch()  # 添加弹性空间
        return row
    
    
    def setup_3rd_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        
        # 按钮: "选择音频/视频"
        select_audio_video_button = QPushButton("选择音频/视频")
        select_audio_video_button.setStyleSheet(f'''
            QPushButton {{
                background-color: {self.colors['accent']};
            }}QPushButton:hover {{
                background-color: {self.colors['accent_hover']};
            }}''')
        select_audio_video_button.setFixedSize(120, 25)
        select_audio_video_button.clicked.connect(self._on_select_audio_video)
        row_layout.addWidget(select_audio_video_button)
        
        # LineEdit: 显示选择的文件路径
        self.audio_video_path_label = QLineEdit("")
        self.audio_video_path_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 13px;")
        self.audio_video_path_label.setReadOnly(True)
        self.audio_video_path_label.setFixedHeight(25)
        self.audio_video_path_label.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.audio_video_path_label.setFrame(False)
        row_layout.addWidget(self.audio_video_path_label)
        
        return row
    
    

    def _on_select_audio_video(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("video/audio (*.mkv *.mp4 *.webm *.avi *.mp3 *.ogg *.wav)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.selected_audio_video_path = os.path.normpath(os.path.abspath(selected_files[0]))
                self.audio_video_path_label.setText(self.selected_audio_video_path)
    

    
    # debug
    # ----------------------------------------------------------------------
    # analyze_button
    
    def _prepare_analyze_args(self):
        # 验证视频路径
        if not self.selected_video_path_1:
            QMessageBox.warning(self, "参数错误", "请先选择谱面确认视频文件")
            return None
        
        # 验证 BPM 输入
        initial_bpm = self.initial_bpm_input.text().strip()
        if not initial_bpm:
            QMessageBox.warning(self, "参数错误", "请输入 Initial BPM")
            return None
        
        initial_bpm = round(float(initial_bpm), 3)
        if initial_bpm < 10 or initial_bpm > 999:
            QMessageBox.warning(self, "参数错误", "Initial BPM 应在 10~999 范围内")
            return None
        
        # 隐藏结果 label
        self.result_label.hide()
        
        # 输出日志
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始分析 &first 数值...\n")
        
        # 返回参数列表
        return [self.selected_video_path_1, str(initial_bpm)]
    
    
    def _on_analyze_finished(self, exit_code):
        if exit_code == 0:
            self.output_widget.append_text("\n✓ 分析完成")
            self.output_widget.append_text("=" * 20)
            
            # 从输出中提取结果
            output_text = self.output_widget.get_text()
            match = re.search(r'Detected start time:\s*([\d.]+)\s*ms', output_text)
            if match:
                detected_time = match.group(1)
                self.result_label.setText(f"估值: {float(detected_time):.3f} ms")
                self.result_label.show()
            else:
                self.output_widget.append_text("\n⚠ 无法解析分析结果")
        else:
            self.output_widget.append_text("\n✗ 分析失败")
            self.output_widget.append_text("=" * 20)
    
    
    # ----------------------------------------------------------------------
    # 按钮配置
    
    def _configure_buttons(self):
        self.analyze_button.configure(
            script_path=os.path.join(root, "tools", "detect_click_start.py"),
            args_generator=self._prepare_analyze_args,
            output_widget=self.output_widget,
            on_finished=self._on_analyze_finished
        )
