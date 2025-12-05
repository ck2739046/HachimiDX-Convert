from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLineEdit, QMessageBox, QLabel)
from PyQt6.QtGui import QDoubleValidator, QIntValidator, QCursor, QPixmap
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
        self.duration_input = None
        self.modify_target_label = None


        # detect_align_all_in_one 返回的最终时间偏移量
        self.final_time_label = None
        self.final_time = None  
        
        # 进程控制按钮
        self.analyze_button = None # 第二行
        self.modify_target_button = None # 第四行
        # 输出区组件
        self.output_widget = None
        
        # 波形图显示widget
        self.waveform_label = None
        
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
        self.output_widget.setFixedHeight(390)
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
        # 第二行：选择目标文件
        second_row = self.setup_2nd_row()
        layout.addWidget(second_row)
        # 第三行：启动拍数量 + Initial BPM + Duration + 开始分析按钮/结果 label
        third_row = self.setup_3rd_row()
        layout.addWidget(third_row)
        # 第四行：开始裁剪按钮
        fourth_row = self.setup_4th_row()
        layout.addWidget(fourth_row)
        # 显示波形图
        layout.addSpacing(10)
        self.waveform_label = QLabel()
        self.waveform_label.setStyleSheet(f"background-color: {self.colors['bg']};")
        self.waveform_label.setMinimumHeight(220)
        self.waveform_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waveform_label.hide()  # 初始隐藏
        layout.addWidget(self.waveform_label)
        
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
        
        # 按钮: "选择目标文件"
        select_file_button_2 = QPushButton("选择目标文件")
        select_file_button_2.setStyleSheet(f'''
            QPushButton {{
                background-color: {self.colors['accent']};
            }}QPushButton:hover {{
                background-color: {self.colors['accent_hover']};
            }}''')
        select_file_button_2.setFixedSize(120, 25)
        select_file_button_2.clicked.connect(self._on_select_file_2)
        row_layout.addWidget(select_file_button_2)
        
        # Helper: 目标文件说明
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
            45, ["4", "5", "6", "7", "8"], default_index=0)
        row_layout.addWidget(self.start_beat_count_combo)
        
        beat_count_help = ui_helpers.create_help_icon("歌曲开头的启动拍的数量，默认为4")
        row_layout.addWidget(beat_count_help)
        
        # Label_LineEdit_Helper Duration
        duration_label = ui_helpers.create_label("搜索范围(秒):")
        row_layout.addWidget(duration_label)
        duration_validator = QIntValidator(5, 999, self)  # 最少5秒
        self.duration_input = ui_helpers.create_line_edit(70, validator=duration_validator, placeholder="5~999")
        self.duration_input.setText("10") # 默认10秒
        row_layout.addWidget(self.duration_input)
        duration_help = ui_helpers.create_help_icon(
            "仅加载基准音频的前多少秒进行分析\n" \
            "这个时间段应该包含所有启动拍")
        row_layout.addWidget(duration_help)

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

        # Helper
        analyze_help = ui_helpers.create_help_icon(
            "程序将根据输入参数进行音频对齐分析\n" \
            "首先根据基准文件的启动拍，预估音频的标准起始时间\n" \
            "然后对齐基准文件和目标文件的音频\n" \
            "最后计算目标文件音频相对于标准音频起始时间的偏移量\n" \
            "\n在理想情况下，音频应该和启动拍同时开始播放\n" \
            "但是游戏加载音频需要时间，实际上两者并非严格同时开始播放\n" \
            "导致估算出的标准音频起始时间可能存在 ±10ms 的误差\n" \
            "结果仅供参考\n" \
            "\n波形图: 红色虚线是程序估算的标准音频起始时间\n" \
            "波形图: 绿色虚线是目标文件音频的实际起始时间")
        row_layout.addWidget(analyze_help)
        
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
        
        # 按钮: "修改目标文件"
        self.modify_target_button = ProcessControlButton("修改目标文件")
        self.modify_target_button.setFixedSize(120, 25)
        row_layout.addWidget(self.modify_target_button)

        # Helper: 修改目标文件说明
        modify_target_help = ui_helpers.create_help_icon(
            "根据分析结果，修改目标文件\n" \
            "视频目标\n" \
            "  正偏移：裁剪视频开头\n" \
            "  负偏移：为视频开头添加黑屏片段\n" \
            "音频目标\n" \
            "  正偏移：裁剪音频开头\n" \
            "  负偏移：为音频开头添加静音片段")
        row_layout.addWidget(modify_target_help)

        # LineEdit: 显示选择的文件路径
        self.modify_target_label = QLineEdit("")
        self.modify_target_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 13px;")
        self.modify_target_label.setReadOnly(True)
        self.modify_target_label.setFixedHeight(25)
        self.modify_target_label.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.modify_target_label.setFrame(False)
        row_layout.addWidget(self.modify_target_label)
        
        # row_layout.addStretch()  # 添加弹性空间
        return row
    

    
    # debug
    # ----------------------------------------------------------------------
    # analyze_button
    
    def _prepare_analyze_args(self):
        # 验证基准文件路径
        if not self.selected_file_path_1:
            QMessageBox.warning(self, "参数错误", "请先选择基准文件")
            return None
        
        # 验证目标文件路径
        if not self.selected_file_path_2:
            QMessageBox.warning(self, "参数错误", "请先选择目标文件")
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
        
        # 验证 duration 输入
        duration_text = self.duration_input.text().strip()
        if not duration_text:
            QMessageBox.warning(self, "参数错误", "请输入 Duration")
            return None
        
        duration = round(int(duration_text), 3)
        if duration < 5 or duration > 999:
            QMessageBox.warning(self, "参数错误", "Duration 应为至少 5 秒")
            return None
        
        # 隐藏结果 label
        self.final_time_label.hide()
        
        # 隐藏并清除波形图
        if self.waveform_label:
            self.waveform_label.hide()
            self.waveform_label.clear()
        
        # 删除旧的波形图文件
        sound_wave_path = os.path.join(tools.path_config.temp_dir, 'sound_wave.png')
        sound_wave_path = os.path.normpath(os.path.abspath(sound_wave_path))
        if os.path.exists(sound_wave_path):
            try:
                os.remove(sound_wave_path)
            except:
                pass
        
        # 输出日志
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始分析对齐...\n")
        
        # 构建参数字典
        params = {
            "reference_file": self.selected_file_path_1,
            "target_file": self.selected_file_path_2,
            "beat_count": start_beat_count,
            "bpm": initial_bpm,
            "duration": duration
        }
        
        # 创建临时 JSON 文件保存参数
        if not os.path.exists(tools.path_config.temp_dir):
            os.makedirs(tools.path_config.temp_dir)
        temp_json_path = os.path.normpath(os.path.join(tools.path_config.temp_dir, "detect_align_all_in_one_args.json"))
        if os.path.exists(temp_json_path):
            os.remove(temp_json_path)
        with open(temp_json_path, 'w', encoding='utf-8') as temp_json:
            json.dump(params, temp_json, ensure_ascii=False, indent=2)
        
        # 返回 JSON 文件路径
        return [temp_json_path]
    
    
    def _on_analyze_finished(self, exit_code):

        if exit_code != 0:
            self.output_widget.append_text("\n✗ 分析失败")
            self.output_widget.append_text("=" * 20)
            self.final_time = None
            return
        
        # 获取最近12行文本解析final_time
        recent_output = self.output_widget.get_recent_lines(12)
        
        # 从 detect_align_all_in_one.py 输出的结果解析三个时间值
        click_start_time = None
        audio_start_time = None
        final_time = None
        
        # 解析click_start_time: "在基准文件中，音频从 xxx ms 开始"
        click_match = re.search(r'在基准文件中，音频从\s*([\d.]+)\s*ms\s*开始', recent_output)
        if click_match:
            click_start_time = float(click_match.group(1))
        
        # 解析audio_start_time: "在基准文件中，目标文件的音频从 xxx ms 开始"
        audio_match = re.search(r'在基准文件中，目标文件的音频从\s*([\d.]+)\s*ms\s*开始', recent_output)
        if audio_match:
            audio_start_time = float(audio_match.group(1))
        
        # 格式如: "目标文件需要提前 150.00 ms" 或 "目标文件需要延后 200.00 ms"
        match = re.search(r'目标文件需要(提前|延后)\s*([\d.]+)\s*ms', recent_output)
        if match:
            action = match.group(1)
            value = float(match.group(2))
            # 如果是"提前"，final_time 为正值；如果是"延后"，final_time 为负值
            final_time = value if action == "提前" else -value
        elif "已经对齐了，无需调整" in recent_output:
            final_time = 0.0

        # 解析失败
        if final_time is None or click_start_time is None or audio_start_time is None:
            self.final_time = None
            self.output_widget.append_text("未能从输出中解析最终时间偏移量")
            self.output_widget.append_text("\n✗ 分析失败")
            self.output_widget.append_text("=" * 20)
            return
        
        # 检查波形图是否生成成功
        sound_wave_path = os.path.join(tools.path_config.temp_dir, 'sound_wave.png')
        sound_wave_path = os.path.normpath(os.path.abspath(sound_wave_path))
        if "波形图已保存到" not in recent_output or not os.path.exists(sound_wave_path):
            self.final_time = None
            self.output_widget.append_text("未能生成音频波形图")
            self.output_widget.append_text("\n✗ 分析失败")
            self.output_widget.append_text("=" * 20)
            return

        # 解析成功
        self.output_widget.append_text("\n✓ 分析完成")
        self.output_widget.append_text("=" * 20)

        # 显示结果到标签
        self.final_time = final_time
        self.final_time_label.setText(f"offset: {self.final_time:.2f} ms")
        self.final_time_label.show()

        # 显示波形图片
        sound_wave_path = os.path.join(tools.path_config.temp_dir, 'sound_wave.png')
        sound_wave_path = os.path.normpath(os.path.abspath(sound_wave_path))
        if os.path.exists(sound_wave_path):
            pixmap = QPixmap(sound_wave_path)
            self.waveform_label.setPixmap(pixmap)
            self.waveform_label.show()


    
    
    def _prepare_modify_args(self):
        # 检查final_time数值
        if self.final_time is None:
            QMessageBox.warning(self, "参数错误", "请先分析时间偏移量")
            return None
        
        if abs(self.final_time) < 0.01:
            QMessageBox.information(self, "无需修改", "目标文件已经对齐，无需修改")
            return None
        
        # 检查目标文件路径
        if not self.selected_file_path_2:
            QMessageBox.warning(self, "参数错误", "请先选择目标文件")
            return None
        
        # 隐藏路径
        self.modify_target_label.hide()
        
        # 输出日志
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始修改目标文件...\n")
        
        # 返回参数：输入文件路径和偏移量
        return [self.selected_file_path_2, str(self.final_time)]
    

    def _on_modify_finished(self, exit_code):
        if exit_code == 0:
            self.modify_target_label.setText(self.selected_file_path_2)
            self.modify_target_label.show()
            self.output_widget.append_text("\n✓ 目标文件修改完成")
            self.output_widget.append_text("=" * 20)
        else:
            self.output_widget.append_text("\n✗ 目标文件修改失败")
            self.output_widget.append_text("=" * 20)
    
    
    # ----------------------------------------------------------------------
    # 按钮配置
    
    def _configure_buttons(self):
        self.analyze_button.configure(
            script_path=os.path.join(root, "tools", "detect_align_all_in_one.py"),
            args_generator=self._prepare_analyze_args,
            output_widget=self.output_widget,
            on_finished=self._on_analyze_finished
        )
        
        self.modify_target_button.configure(
            script_path=os.path.join(root, "tools", "trim.py"),
            args_generator=self._prepare_modify_args,
            output_widget=self.output_widget,
            on_finished=self._on_modify_finished
        )
