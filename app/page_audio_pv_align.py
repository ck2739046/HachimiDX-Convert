from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLineEdit, QMessageBox)
from PyQt6.QtGui import QDoubleValidator, QIntValidator, QCursor
from PyQt6.QtCore import Qt
import os
import sys
import time
import json
import re

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config

from process_widgets import ProcessControlButton, OutputTextWidget
import ui_helpers



class AudioPvAlignPage(QWidget):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.colors = ui_helpers.COLORS
        
        self.file_path_label_1 = None
        self.selected_file_path_1 = None
        self.file_path_label_2 = None
        self.selected_file_path_2 = None
        self.start_beat_count_combo = None
        self.initial_bpm_input = None

        # detect_and_align 返回的最终时间偏移量
        self.final_time_label = None
        self.final_time = None  
        
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
        
        # 第一行：选择基准文件
        first_row = self.setup_1st_row()
        layout.addWidget(first_row)
        # 第二行：选择待对齐文件
        second_row = self.setup_2nd_row()
        layout.addWidget(second_row)
        # 第三行：启动拍数量 + Initial BPM + 开始分析按钮/结果 label
        third_row = self.setup_3rd_row()
        layout.addWidget(third_row)
        # 第四行：开始裁剪按钮
        fourth_row = self.setup_4th_row()
        layout.addWidget(fourth_row)
        
        layout.addSpacing(5)
        layout.addStretch()  # 添加弹性空间
        return widget
    

    
    def setup_1st_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        
        # 按钮: "选择基准文件"
        select_file_button_1 = QPushButton("选择基准文件")
        select_file_button_1.setStyleSheet(f'''
            QPushButton {{
                background-color: {self.colors['accent']};
            }}QPushButton:hover {{
                background-color: {self.colors['accent_hover']};
            }}''')
        select_file_button_1.setFixedSize(120, 25)
        select_file_button_1.clicked.connect(self._on_select_file_1)
        row_layout.addWidget(select_file_button_1)
        
        # Helper: 基准文件说明
        file_1_help = ui_helpers.create_help_icon("可以是音频或视频，需要包含完整的几声启动拍")
        row_layout.addWidget(file_1_help)
        
        # LineEdit: 显示选择的文件路径
        self.file_path_label_1 = QLineEdit("")
        self.file_path_label_1.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 13px;")
        self.file_path_label_1.setReadOnly(True)
        self.file_path_label_1.setFixedHeight(25)
        self.file_path_label_1.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.file_path_label_1.setFrame(False)
        row_layout.addWidget(self.file_path_label_1)
        
        return row
    
    
    def _on_select_file_1(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("video/audio (*.mkv *.mp4 *.webm *.avi *.mp3 *.ogg *.wav)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.selected_file_path_1 = os.path.normpath(os.path.abspath(selected_files[0]))
                self.file_path_label_1.setText(self.selected_file_path_1)
    
    
    def setup_2nd_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        
        # 按钮: "选择待对齐文件"
        select_file_button_2 = QPushButton("选择待对齐文件")
        select_file_button_2.setStyleSheet(f'''
            QPushButton {{
                background-color: {self.colors['accent']};
            }}QPushButton:hover {{
                background-color: {self.colors['accent_hover']};
            }}''')
        select_file_button_2.setFixedSize(120, 25)
        select_file_button_2.clicked.connect(self._on_select_file_2)
        row_layout.addWidget(select_file_button_2)
        
        # Helper: 待对齐文件说明
        file_2_help = ui_helpers.create_help_icon("可以是音频或视频")
        row_layout.addWidget(file_2_help)
        
        # LineEdit: 显示选择的文件路径
        self.file_path_label_2 = QLineEdit("")
        self.file_path_label_2.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 13px;")
        self.file_path_label_2.setReadOnly(True)
        self.file_path_label_2.setFixedHeight(25)
        self.file_path_label_2.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.file_path_label_2.setFrame(False)
        row_layout.addWidget(self.file_path_label_2)
        
        return row
    

    def _on_select_file_2(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("video/audio (*.mkv *.mp4 *.webm *.avi *.mp3 *.ogg *.wav)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.selected_file_path_2 = os.path.normpath(os.path.abspath(selected_files[0]))
                self.file_path_label_2.setText(self.selected_file_path_2)
    
    
    def setup_3rd_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        
        # Label_ComboBox_Helper 启动拍数量
        start_beat_count_label = ui_helpers.create_label("启动拍数量:")
        row_layout.addWidget(start_beat_count_label)
        
        self.start_beat_count_combo = ui_helpers.create_combo_box(
            45, ["4", "7"], default_index=0)
        row_layout.addWidget(self.start_beat_count_combo)
        
        beat_count_help = ui_helpers.create_help_icon("歌曲开头的启动拍的数量，默认为4")
        row_layout.addWidget(beat_count_help)
        
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
        self.final_time_label = ui_helpers.create_label("default")
        self.final_time_label.setStyleSheet(f"color: {self.colors['accent']}; font-size: 13px; font-weight: bold;")
        self.final_time_label.hide()
        row_layout.addWidget(self.final_time_label)
        
        row_layout.addStretch()  # 添加弹性空间
        return row
    
    

    def setup_4th_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        
        row_layout.addStretch()  # 添加弹性空间
        return row
    

    
    # debug
    # ----------------------------------------------------------------------
    # analyze_button
    
    def _prepare_analyze_args(self):
        # 验证基准文件路径
        if not self.selected_file_path_1:
            QMessageBox.warning(self, "参数错误", "请先选择基准文件")
            return None
        
        # 验证待对齐文件路径
        if not self.selected_file_path_2:
            QMessageBox.warning(self, "参数错误", "请先选择待对齐文件")
            return None
        
        # 获取启动拍数量（从下拉框选择）
        start_beat_count = int(self.start_beat_count_combo.currentText())
        
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
        self.final_time_label.hide()
        
        # 输出日志
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始分析对齐...\n")
        
        # 构建参数字典
        params = {
            "reference_file": self.selected_file_path_1,
            "target_file": self.selected_file_path_2,
            "beat_count": start_beat_count,
            "bpm": initial_bpm
        }
        
        # 创建临时 JSON 文件保存参数
        if not os.path.exists(tools.path_config.temp_dir):
            os.makedirs(tools.path_config.temp_dir)
        temp_json_path = os.path.normpath(os.path.join(tools.path_config.temp_dir, "detect_and_align_args.json"))
        if os.path.exists(temp_json_path):
            os.remove(temp_json_path)
        with open(temp_json_path, 'w', encoding='utf-8') as temp_json:
            json.dump(params, temp_json, ensure_ascii=False, indent=2)
        
        # 返回 JSON 文件路径
        return [temp_json_path]
    
    
    def _on_analyze_finished(self, exit_code):
        if exit_code == 0:
        
            # 获取最近7行文本解析final_time
            recent_output = self.output_widget.get_recent_lines(7)
            # 匹配 detect_and_align.py 输出中的结果
            # 格式如: "目标文件需要提前 150.00 ms" 或 "目标文件需要延后 200.00 ms"
            match = re.search(r'目标文件需要(提前|延后)\s*([\d.]+)\s*ms', recent_output)
            if match:
                action = match.group(1)
                value = float(match.group(2))
                # 如果是"提前"，final_time 为正值；如果是"延后"，final_time 为负值
                self.final_time = value if action == "提前" else -value
                # 显示结果到标签
                self.final_time_label.setText(f"offset: {self.final_time:.2f} ms")
                self.final_time_label.show()

                self.output_widget.append_text("\n✓ 分析完成")
                self.output_widget.append_text("=" * 20)

            else:
                self.final_time = None
                self.output_widget.append_text("未能从输出中解析最终时间偏移量")
                self.output_widget.append_text("\n✗ 分析失败")
                self.output_widget.append_text("=" * 20)

        else:
            self.output_widget.append_text("\n✗ 分析失败")
            self.output_widget.append_text("=" * 20)
            self.final_time = None
    
    
    # ----------------------------------------------------------------------
    # 按钮配置
    
    def _configure_buttons(self):
        self.analyze_button.configure(
            script_path=os.path.join(root, "tools", "detect_and_align.py"),
            args_generator=self._prepare_analyze_args,
            output_widget=self.output_widget,
            on_finished=self._on_analyze_finished
        )
