from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLineEdit, QMessageBox)
from PyQt6.QtGui import QDoubleValidator, QCursor
from PyQt6.QtCore import Qt
import os
import sys
import time
import json
import cv2

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config

from process_widgets import ProcessControlButton, OutputTextWidget
import ui_helpers



class AutoConvertPage(QWidget):
    
    def __init__(self, parent=None): # 父 widget

        super().__init__(parent)

        self.colors = ui_helpers.COLORS
        
        # 第一行 模型管理
        self.backend_combo = None
        self.current_selected_backend = None # backend_combo.currentText()备份
        # 第二行 模型管理
        self.env_status_label = None
        self.model_status_label = None
        self.batch_size_label = None
        self.batch_size_combo = None
        self.workspace_label = None
        self.workspace_combo = None
        
        # 第三行 Standardizer 配置
        self.video_path_label = None
        self.selected_video_path = None
        # 第四行 Standardizer 配置
        self.video_type_combo = None
        self.video_start_input = None
        self.video_end_input = None
        self.skip_detect_circle_checkbox = None

        # 第五行 NoteDetector 配置
        self.video_name_input = None
        # 第六行 NoteDetector 配置
        self.batch_detect_obb_combo = None
        self.batch_classify_combo = None
        self.skip_detect_checkbox = None
        self.skip_classify_checkbox = None
        self.skip_export_tracked_video_checkbox = None
        
        # 第七行 NoteAnalyzer 配置
        self.bpm_input = None
        self.chart_lv_combo = None
        self.base_denominator_combo = None

        # 第八行 模块管理
        self.enable_standardizer_checkbox = None
        self.enable_note_detector_checkbox = None
        self.enable_note_analyzer_checkbox = None

        # 进程控制按钮
        self.check_availability_button = None # 第一行
        self.convert_model_button = None      # 第二行
        self.auto_convert_button = None       # 第八行
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
        
        # 标题分隔线：模型管理
        layout.addWidget(ui_helpers.create_divider("模型管理", 0, 0))
        # 第一行：模型推理后端选择
        first_row = self.setup_1st_row()
        layout.addWidget(first_row)
        # 第二行：模型推理后端状态显示
        second_row = self.setup_2nd_row()
        layout.addWidget(second_row)
        
        # 标题分隔线：Standardize Video
        layout.addWidget(ui_helpers.create_divider("视频标准化"))
        # 第三行：选择谱面视频
        third_row = self.setup_3rd_row()
        layout.addWidget(third_row)
        # 第四行：Standardizer 配置
        fourth_row = self.setup_4th_row()
        layout.addWidget(fourth_row)
        
        # 标题分隔线：Note Detection
        layout.addWidget(ui_helpers.create_divider("音符识别"))
        # 第五行: 输入歌曲名称
        fifth_row = self.setup_5th_row()
        layout.addWidget(fifth_row)
        # 第六行: NoteDetector 配置
        sixth_row = self.setup_6th_row()
        layout.addWidget(sixth_row)

        # 标题分隔线：Note Analyze
        layout.addWidget(ui_helpers.create_divider("音符分析"))
        # 第七行: NoteAnalyzer 配置
        seventh_row = self.setup_7th_row()
        layout.addWidget(seventh_row)

        # 标题分隔线：开始转谱
        layout.addWidget(ui_helpers.create_divider("开始转谱"))
        # 第八行：模块管理 + 开始按钮
        eighth_row = self.setup_8th_row()
        layout.addWidget(eighth_row)

        layout.addSpacing(5)
        layout.addStretch()  # 添加弹性空间
        return widget
    
    

    def setup_1st_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # Label_ComboBox_Helper 模型推理后端
        backend_label = ui_helpers.create_label("模型推理后端:")
        row_layout.addWidget(backend_label)
        self.backend_combo = ui_helpers.create_combo_box(90, ["TensorRT", "DirectML"])
        row_layout.addWidget(self.backend_combo)
        help_label = ui_helpers.create_help_icon(
            "TensorRT: 适用于 NVIDIA GPU (推荐)\nDirectML: 适用于 AMD/Intel/Other GPU")
        row_layout.addWidget(help_label)

        # check_availability button
        self.check_availability_button = ProcessControlButton("检查可用性")
        self.check_availability_button.setFixedSize(80, 25)
        row_layout.addWidget(self.check_availability_button)

        row_layout.addStretch()  # 添加弹性空间
        return row

    

    def setup_2nd_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # Label: 运行环境状态
        self.env_status_label = ui_helpers.create_label("运行环境待检测⚪")
        row_layout.addWidget(self.env_status_label)

        # Label: 模型状态
        self.model_status_label = ui_helpers.create_label("模型文件待检测⚪")
        row_layout.addWidget(self.model_status_label)

        # 按钮: "转换模型"（默认隐藏）
        self.convert_model_button = ProcessControlButton("转换模型")
        self.convert_model_button.setFixedSize(80, 25)
        self.convert_model_button.hide()
        row_layout.addWidget(self.convert_model_button)
        
        # Label_ComboBox Batch_size（默认隐藏）
        self.batch_size_label = ui_helpers.create_label("batch:")
        self.batch_size_label.hide()
        row_layout.addWidget(self.batch_size_label)
        self.batch_size_combo = ui_helpers.create_combo_box(
            35, ["1", "2", "3", "4", "5", "6", "7", "8"])
        self.batch_size_combo.hide()
        row_layout.addWidget(self.batch_size_combo)

        # Label_ComboBox: Workspace（默认隐藏）
        self.workspace_label = ui_helpers.create_label("workspace:")
        self.workspace_label.hide()
        row_layout.addWidget(self.workspace_label)
        self.workspace_combo = ui_helpers.create_combo_box(
            65, ["auto", "1", "2", "3", "4", "5", "6", "7", "8"])
        self.workspace_combo.hide()
        row_layout.addWidget(self.workspace_combo)

        row_layout.addStretch()  # 添加弹性空间
        return row


    
    def setup_3rd_row(self):

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
        select_video_button.clicked.connect(self._on_select_video)
        row_layout.addWidget(select_video_button)

        # LineEdit: 显示选择的视频路径
        self.video_path_label = QLineEdit("")
        self.video_path_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-size: 13px;")
        self.video_path_label.setReadOnly(True)  # 只读
        self.video_path_label.setFixedHeight(25) # 非固定宽度
        self.video_path_label.setCursor(QCursor(Qt.CursorShape.IBeamCursor)) # 设置为 I-beam 光标
        self.video_path_label.setFrame(False)    # 移除默认边框
        row_layout.addWidget(self.video_path_label)

        # row_layout.addStretch()  # 添加弹性空间
        return row



    def _on_select_video(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("video (*.mkv *.mp4 *.webm *.avi)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.selected_video_path = os.path.normpath(os.path.abspath(selected_files[0]))
                self.video_path_label.setText(self.selected_video_path)
    

    
    def setup_4th_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # Label_ComboBox_Helper 视频形式
        video_type_label = ui_helpers.create_label("视频形式:")
        row_layout.addWidget(video_type_label)
        self.video_type_combo = ui_helpers.create_combo_box(120, ["source video", "camera footage"])
        row_layout.addWidget(self.video_type_combo)
        video_type_help = ui_helpers.create_help_icon("source video: 游戏原生画面\ncamera footage: 相机拍屏幕")
        row_layout.addWidget(video_type_help)

        # Label_LineEdit_Helper 歌曲范围
        video_range_label = ui_helpers.create_label("歌曲范围(秒):")
        row_layout.addWidget(video_range_label)

        start_validator = QDoubleValidator(-1.0, 999.0, 3, self) # -1_999的浮点数
        self.video_start_input = ui_helpers.create_line_edit(80, validator=start_validator, placeholder="0~999/-1")
        row_layout.addWidget(self.video_start_input)

        arrow_label = ui_helpers.create_label("->")
        row_layout.addWidget(arrow_label)

        end_validator = QDoubleValidator(-1.0, 999.0, 3, self) # -1_999的浮点数
        self.video_end_input = ui_helpers.create_line_edit(80, validator=end_validator, placeholder="0~999/-1")
        row_layout.addWidget(self.video_end_input)

        video_range_help = ui_helpers.create_help_icon(
            "歌曲真正起始和结束的时间(秒)\n"
            "-1 表示视频开头第 0 秒或结尾最后 1 秒\n"
            "正确的歌曲起始应该是游戏走转场刚刚进入黑屏，并且乐曲启动拍还没响的时间"
            "\n正确的歌曲结束应该是歌曲最后一个音符消失后的时间")
        row_layout.addWidget(video_range_help)

        # Label_CheckBox_Helper skip_detect_circle
        skip_detect_circle_label = ui_helpers.create_label("skip_detect_circle:")
        row_layout.addWidget(skip_detect_circle_label)
        self.skip_detect_circle_checkbox = ui_helpers.create_check_box()
        self.skip_detect_circle_checkbox.setChecked(True)  # 默认启用
        row_layout.addWidget(self.skip_detect_circle_checkbox)
        skip_detect_circle_help = ui_helpers.create_help_icon(
            "程序会尝试自动检测圆形游戏屏幕的位置\n" \
            "如果在当前谱面确认视频中，游戏画面已经是全屏并且在屏幕中心，可以跳过检测")
        row_layout.addWidget(skip_detect_circle_help)

        row_layout.addStretch()  # 添加弹性空间
        return row
    


    def setup_5th_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # 输入框: 视频名称
        self.video_name_input = ui_helpers.create_line_edit(placeholder="歌曲名称 (必填)")
        row_layout.addWidget(self.video_name_input)

        # row_layout.addStretch()  # 添加弹性空间
        return row
    


    def setup_6th_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # Label_ComboBox batch_detect_obb(1-8)
        batch_detect_label = ui_helpers.create_label("batch_detect_obb:")
        row_layout.addWidget(batch_detect_label)
        self.batch_detect_obb_combo = ui_helpers.create_combo_box(
            45, ["1", "2", "3", "4", "5", "6", "7", "8"], default_index=1)
        row_layout.addWidget(self.batch_detect_obb_combo)
        # Label_ComboBox batch_classify(1,2,4,8,16,32)
        batch_classify_label = ui_helpers.create_label("batch_classify:")
        row_layout.addWidget(batch_classify_label)
        self.batch_classify_combo = ui_helpers.create_combo_box(
            45, ["1", "2", "4", "8", "16", "32"], default_index=4)
        row_layout.addWidget(self.batch_classify_combo)
        # Helper 解释这两个 batch 的作用
        batch_help = ui_helpers.create_help_icon(
            "batch_detect_obb: 用于目标检测模型运行时的批处理大小\n" \
            "batch_classify: 用于图像分类模型运行时的批处理大小\n" \
            "如果推理后端是 TensorRT, batch_classify 不能超过转换模型时选择的 batch 数值")
        row_layout.addWidget(batch_help)
        
        # Label_CheckBox_Helper skip_detect
        skip_detect_label = ui_helpers.create_label("skip_detect:")
        row_layout.addWidget(skip_detect_label)
        self.skip_detect_checkbox = ui_helpers.create_check_box()
        row_layout.addWidget(self.skip_detect_checkbox)
        skip_detect_help = ui_helpers.create_help_icon(
            "跳过逐帧检测视频中的音符，直接读取已经存在的检测结果 (detect_result.txt)")
        row_layout.addWidget(skip_detect_help)

        # Label_CheckBox_Helper skip_classify
        skip_classify_label = ui_helpers.create_label("skip_classify:")
        row_layout.addWidget(skip_classify_label)
        self.skip_classify_checkbox = ui_helpers.create_check_box()
        row_layout.addWidget(self.skip_classify_checkbox)
        skip_classify_help = ui_helpers.create_help_icon(
            "跳过分类检测 ex-note, break-note, ex-break-note")
        row_layout.addWidget(skip_classify_help)

        # Label_CheckBox_Helper skip_export_tracked_video
        skip_export_tracked_video_label = ui_helpers.create_label("skip_export_tracked_video:")
        row_layout.addWidget(skip_export_tracked_video_label)
        self.skip_export_tracked_video_checkbox = ui_helpers.create_check_box()
        row_layout.addWidget(self.skip_export_tracked_video_checkbox)
        skip_export_tracked_video_help = ui_helpers.create_help_icon(
            "跳过导出追踪视频")
        row_layout.addWidget(skip_export_tracked_video_help)

        row_layout.addStretch()  # 添加弹性空间
        return row
    


    def setup_7th_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # Label_LineEdit_Helper 歌曲BPM
        bpm_label = ui_helpers.create_label("歌曲BPM:")
        row_layout.addWidget(bpm_label)
        bpm_validator = QDoubleValidator(10.0, 999.0, 3, self) # 10_999的浮点数
        self.bpm_input = ui_helpers.create_line_edit(70, validator=bpm_validator, placeholder="10~999")
        row_layout.addWidget(self.bpm_input)
        bpm_help = ui_helpers.create_help_icon(
            "仅支持静态 BPM (全程不变速)")
        row_layout.addWidget(bpm_help)

        # Label_ComboBox_Helper 谱面难度
        chart_lv_label = ui_helpers.create_label("谱面难度:")
        row_layout.addWidget(chart_lv_label)
        self.chart_lv_combo = ui_helpers.create_combo_box(
            45, ["1", "2", "3", "4", "5", "6", "7"], default_index=4)
        row_layout.addWidget(self.chart_lv_combo)
        chart_lv_help = ui_helpers.create_help_icon(
            "1-easy\n2-basic\n3-normal\n4-expert\n5-master\n6-re:master\n7-utage")
        row_layout.addWidget(chart_lv_help)

        # Label_ComboBox_Helper base_denominator
        base_denominator_label = ui_helpers.create_label("解析分辨率:")
        row_layout.addWidget(base_denominator_label)
        self.base_denominator_combo = ui_helpers.create_combo_box(
            45, ["4", "8", "16", "32", "64"], default_index=2)
        row_layout.addWidget(self.base_denominator_combo)
        base_denominator_help = ui_helpers.create_help_icon(
            "程序解析谱面的分辨率\n" \
            "默认为 16，代表单位时间为 1/16 小节，在 sinmai 语法中写作 {16},\n" \
            "程序会将音符对齐到单位时间\n" \
            "单位时间计算: 240000 / bpm / 分辨率 (ms)\n" \
            "建议单位时间 ≥30ms，如果 BPM 较高，需要适当降低分辨率以保证准确性")
        row_layout.addWidget(base_denominator_help)

        row_layout.addStretch()  # 添加弹性空间
        return row



    def setup_8th_row(self):

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # 大按钮: "Start Auto Convert!"（使用新组件）
        self.auto_convert_button = ProcessControlButton("Start!")
        self.auto_convert_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                font-size: 16px;
                font-weight: bold;
            }}QPushButton:hover {{
                background-color: {self.colors['accent_hover']};
            }}""")
        self.auto_convert_button.setFixedSize(80, 35)
        row_layout.addWidget(self.auto_convert_button)
        row_layout.addSpacing(5)

        # Label_CheckBox_Helper enable_standardizer
        enable_standardizer_label = ui_helpers.create_label("启用视频标准化模块:")
        row_layout.addWidget(enable_standardizer_label)
        self.enable_standardizer_checkbox = ui_helpers.create_check_box()
        self.enable_standardizer_checkbox.setChecked(True)  # 默认启用
        row_layout.addWidget(self.enable_standardizer_checkbox)
        enable_standardizer_help = ui_helpers.create_help_icon(
            "是否启用视频标准化模块")
        row_layout.addWidget(enable_standardizer_help)

        # Label_CheckBox_Helper enable_note_detector
        enable_note_detector_label = ui_helpers.create_label("启用音符识别模块:")
        row_layout.addWidget(enable_note_detector_label)
        self.enable_note_detector_checkbox = ui_helpers.create_check_box()
        self.enable_note_detector_checkbox.setChecked(True)  # 默认启用
        row_layout.addWidget(self.enable_note_detector_checkbox)
        enable_note_detector_help = ui_helpers.create_help_icon(
            "是否启用音符识别模块")
        row_layout.addWidget(enable_note_detector_help)

        # Label_CheckBox_Helper enable_note_analyzer
        enable_note_analyzer_label = ui_helpers.create_label("启用音符分析模块:")
        row_layout.addWidget(enable_note_analyzer_label)
        self.enable_note_analyzer_checkbox = ui_helpers.create_check_box()
        self.enable_note_analyzer_checkbox.setChecked(True)  # 默认启用
        row_layout.addWidget(self.enable_note_analyzer_checkbox)
        enable_note_analyzer_help = ui_helpers.create_help_icon(
            "是否启用音符分析模块")
        row_layout.addWidget(enable_note_analyzer_help)

        row_layout.addStretch()  # 添加弹性空间
        return row

    
    
    # debug
    # ----------------------------------------------------------------------
    # check_availability
    
    def _prepare_check_availability_args(self):
        # 重置状态
        self.env_status_label.setText("运行环境待检测⚪")
        self.model_status_label.setText("模型文件待检测⚪")
        self.convert_model_button.hide()
        self.batch_size_label.hide()
        self.batch_size_combo.hide()
        self.workspace_label.hide()
        self.workspace_combo.hide()
        
        # 开始环境检查
        self.current_selected_backend = self.backend_combo.currentText()
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始检查 {self.current_selected_backend} 运行环境...\n")
        
        return [self.current_selected_backend]
    
    

    def _on_check_availability_finished(self, exit_code):

        if exit_code == 0:
            self.env_status_label.setText("运行环境正常🟢")
            self.output_widget.append_text("\n✓ 运行环境检查通过")
            # 继续检查模型
            self.check_models()
        else:
            self.env_status_label.setText("运行环境异常🔴")
            self.output_widget.append_text("\n✗ 运行环境检查失败")
            self.output_widget.append_text("=" * 20)



    def check_models(self):
        self.output_widget.append_text(f"\n开始检查 {self.current_selected_backend} 模型文件...\n")

        # 先尝试查找转换后的模型文件
        if self.current_selected_backend == "TensorRT":
            model_paths = [tools.path_config.detect_engine,
                           tools.path_config.obb_pt,
                           tools.path_config.cls_break_pt,
                           tools.path_config.cls_ex_pt]
        else: # DirectML
            model_paths = [tools.path_config.detect_onnx,
                           tools.path_config.obb_onnx,
                           tools.path_config.cls_break_onnx,
                           tools.path_config.cls_ex_onnx]
            
        all_models_exist = True
        for model_path in model_paths:
            if os.path.exists(model_path) and os.path.isfile(model_path):
                self.output_widget.append_text(f"✓ 找到模型文件: {os.path.basename(model_path)}")
            else:
                self.output_widget.append_text(f"✗ 缺少模型文件: {os.path.basename(model_path)}")
                all_models_exist = False
        
        if all_models_exist:
            self.model_status_label.setText("模型文件正常🟢")
            self.output_widget.append_text("\n✓ 模型文件检查通过")
            self.output_widget.append_text("=" * 20)
            return
        
        # 如果没有找到转换后的模型，则检查原始模型文件
        self.output_widget.append_text("\n未找到转换后的模型文件，开始检查原始模型文件...\n")
        raw_model_paths = [tools.path_config.detect_pt,
                           tools.path_config.obb_pt,
                           tools.path_config.cls_break_pt,
                           tools.path_config.cls_ex_pt]
        
        all_models_exist = True
        for model_path in raw_model_paths:
            if os.path.exists(model_path) and os.path.isfile(model_path):
                self.output_widget.append_text(f"✓ 找到模型文件: {os.path.basename(model_path)}")
            else:
                self.output_widget.append_text(f"✗ 缺少模型文件: {os.path.basename(model_path)}")
                all_models_exist = False

        if all_models_exist:
            self.model_status_label.setText("模型文件待转换🟡")
            self.output_widget.append_text("\n✗ 模型文件检查未通过，需要转换格式")
            self.output_widget.append_text("=" * 20)
            # 显示转换按钮，如果是 TensorRT 还要显示 batch size 和 workspace 输入
            self.convert_model_button.show()
            if self.current_selected_backend == "TensorRT":
                self.batch_size_label.show()
                self.batch_size_combo.show()
                self.workspace_label.show()
                self.workspace_combo.show()
            return
        
        # 如果连原始模型都缺失
        self.model_status_label.setText("模型文件异常🔴")
        self.output_widget.append_text("\n✗ 模型文件检查未通过，文件缺失")
        self.output_widget.append_text("=" * 20)



    # debug
    # ----------------------------------------------------------------------
    # convert_model

    def _prepare_convert_model_args(self):
        # 准备参数
        args = [self.current_selected_backend]
        # 如果是 TensorRT，额外添加 batch size 和 workspace 参数
        if self.current_selected_backend == "TensorRT":
            batch_size = self.batch_size_combo.currentText()    
            workspace = self.workspace_combo.currentText()
            args.append(str(batch_size))
            args.append(workspace)
        # 打印开始
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始转换为 {self.current_selected_backend} 模型...\n")
        
        return args
    
    
    def _on_convert_model_finished(self, exit_code):

        if exit_code == 0:
            self.output_widget.append_text("\n✓ 模型转换完成")
            self.output_widget.append_text("=" * 20)
            # 隐藏转换按钮和输入框
            self.convert_model_button.hide()
            self.batch_size_label.hide()
            self.batch_size_combo.hide()
            self.workspace_label.hide()
            self.workspace_combo.hide()
            # 更新模型状态
            self.model_status_label.setText("模型文件正常🟢")
        else:
            self.output_widget.append_text("\n✗ 模型转换失败")
            self.output_widget.append_text("=" * 20)



    # debug
    # ----------------------------------------------------------------------
    # auto_convert
    
    def _prepare_auto_convert_args(self):

        # 根据启用的模块准备参数
        enable_standardizer = self.enable_standardizer_checkbox.isChecked()
        enable_note_detector = self.enable_note_detector_checkbox.isChecked()
        enable_note_analyzer = self.enable_note_analyzer_checkbox.isChecked()
        if not (enable_standardizer or enable_note_detector or enable_note_analyzer):
            QMessageBox.warning(self, "参数错误", "请至少启用一个模块")
            return None
        
        # 这个参数无论如何都需要输入
        video_name = self.video_name_input.text().strip()
        if not video_name:
            QMessageBox.warning(self, "参数错误", "请输入歌曲名称")
            return None
        
        # 准备 standardizer 参数
        if enable_standardizer:

            if not self.selected_video_path:
                QMessageBox.warning(self, "参数错误", "请先选择谱面确认视频文件")
                return None
            
            video_start = self.video_start_input.text().strip()
            if not video_start:
                QMessageBox.warning(self, "参数错误", "请输入歌曲起始时间")
                return None
            
            video_end = self.video_end_input.text().strip()
            if not video_end:
                QMessageBox.warning(self, "参数错误", "请输入歌曲结束时间")
                return None
            
            # 检查参数范围
            video_start = float(video_start)
            video_end = float(video_end)
            if video_start != -1:
                video_start = round(video_start, 3)
                if video_start < 0 or video_start > 999:
                    QMessageBox.warning(self, "参数错误", "歌曲起始时间应在 0~999 秒范围内，或为 -1")
                    return None
            if video_end != -1:
                video_end = round(video_end, 3)
                if video_end < 0 or video_end > 999:
                    QMessageBox.warning(self, "参数错误", "歌曲结束时间应在 0~999 秒范围内，或为 -1")
                    return None
                
            # 使用 OpenCV 获取视频的实际 FPS，将 start/end 转为帧数
            try:
                cap = cv2.VideoCapture(self.selected_video_path)
                if not cap.isOpened():
                    QMessageBox.warning(self, "\n视频错误", f"无法打开视频文件: {self.selected_video_path}")
                    return None
                video_fps = cap.get(cv2.CAP_PROP_FPS)
                cap.release()
                if video_fps <= 0:
                    QMessageBox.warning(self, "\n视频错误", f"无法获取视频 FPS 信息: {self.selected_video_path}")
                    return None
                self.output_widget.append_text(f"\n检测到谱面确认视频 FPS: {video_fps:.2f}")
            except Exception as e:
                QMessageBox.warning(self, "\n视频错误", f"尝试读取视频 FPS 失败: (self.selected_video_path)\n" \
                                                       f"错误信息: {str(e)}")
                return None

            video_path = os.path.normpath(os.path.abspath(self.selected_video_path))
            video_mode = self.video_type_combo.currentText()
            target_res = 1080
            skip_detect_circle = self.skip_detect_circle_checkbox.isChecked()
            start_frame = round(video_start * video_fps) if video_start >= 0 else -1
            end_frame = round(video_end * video_fps) if video_end >= 0 else -1


        # 准备 note_detector 参数
        if enable_note_detector:
            
            # 如果没有启用标准化视频模块，需要检查是否已经存在标准化后的视频文件
            if enable_standardizer:
                standardized_video_path = None
            else:
                if not self.selected_video_path:
                    QMessageBox.warning(self, "参数错误", "请先选择谱面确认视频文件")
                    return None
                video_filename_no_ext = os.path.basename(self.selected_video_path)[:-4] # 总是mp4
                standardized_video_path = os.path.normpath(os.path.abspath(
                    os.path.join(tools.path_config.temp_dir, f"{video_filename_no_ext}_standardized.mp4")))
                if not os.path.exists(standardized_video_path) or not os.path.isfile(standardized_video_path):
                    QMessageBox.warning(self, "参数错误", f"未找到标准化后的视频文件: {standardized_video_path}\n" \
                                                         "请先启用并运行视频标准化模块")
                    return None
            
            # 根据后端选择模型路径和推理设备
            backend = self.backend_combo.currentText()
            if backend == "TensorRT":
                model_paths = {
                    "detect": os.path.normpath(os.path.abspath(tools.path_config.detect_engine)),
                    "obb": os.path.normpath(os.path.abspath(tools.path_config.obb_pt)),
                    "cls_break": os.path.normpath(os.path.abspath(tools.path_config.cls_break_pt)),
                    "cls_ex": os.path.normpath(os.path.abspath(tools.path_config.cls_ex_pt))
                }
                inference_device = "0"
            else:  # DirectML
                model_paths = {
                    "detect": os.path.normpath(os.path.abspath(tools.path_config.detect_onnx)),
                    "obb": os.path.normpath(os.path.abspath(tools.path_config.obb_onnx)),
                    "cls_break": os.path.normpath(os.path.abspath(tools.path_config.cls_break_onnx)),
                    "cls_ex": os.path.normpath(os.path.abspath(tools.path_config.cls_ex_onnx))
                }
                inference_device = "NONE"

            batch_detect_obb = int(self.batch_detect_obb_combo.currentText())
            batch_classify = int(self.batch_classify_combo.currentText())
            skip_detect = self.skip_detect_checkbox.isChecked()
            skip_classify = self.skip_classify_checkbox.isChecked()
            skip_export_tracked_video = self.skip_export_tracked_video_checkbox.isChecked()


        # 准备 note_analyzer 参数
        if enable_note_analyzer:

            # 如果没有启用音符识别模块，需要构建 tracked_output_dir
            if enable_note_detector:
                tracked_output_dir = None
            else:
                tracked_output_dir = os.path.normpath(os.path.abspath(
                    os.path.join(tools.path_config.all_songs_output_dir, video_name)))
                if not os.path.exists(tracked_output_dir):
                    QMessageBox.warning(self, "参数错误", f"未找到音符追踪结果文件夹: {tracked_output_dir}\n" \
                                                         "请先启用并运行音符识别模块")
                    return None

            bpm = self.bpm_input.text().strip()
            if not bpm:
                QMessageBox.warning(self, "参数错误", "请输入歌曲 BPM")
                return None

            bpm = round(float(bpm), 3)    
            if bpm < 10 or bpm > 999:
                QMessageBox.warning(self, "参数错误", "歌曲 BPM 应在 10~999 范围内")
                return None
            
            chart_lv = int(self.chart_lv_combo.currentText())
            base_denominator = int(self.base_denominator_combo.currentText())


        # 构建参数字典
        params = {
            "Standardizer": {"enabled": False},
            "NoteDetector": {"enabled": False},
            "NoteAnalyzer": {"enabled": False}
        }

        if enable_standardizer:
            params["Standardizer"] = {
                "enabled": True,
                "video_path": video_path,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "video_mode": video_mode,
                "target_res": target_res,
                "skip_detect_circle": skip_detect_circle,
            }
        
        if enable_note_detector:
            params["NoteDetector"] = {
                "enabled": True,
                "std_video_path": standardized_video_path,
                "video_name": video_name,
                "batch_detect_obb": batch_detect_obb,
                "batch_cls": batch_classify,
                "inference_device": inference_device,
                "model_paths": model_paths,
                "skip_detect": skip_detect,
                "skip_cls": skip_classify,
                "skip_export_tracked_video": skip_export_tracked_video
            }

        if enable_note_analyzer:
            params["NoteAnalyzer"] = {
                "enabled": True,
                "tracked_output_dir": tracked_output_dir,
                "bpm": bpm,
                "chart_lv": chart_lv,
                "base_denominator": base_denominator
            }

        # 输出日志
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"开始自动转谱: {video_name}\n")
        
        # 创建临时 JSON 文件保存参数
        if not os.path.exists(tools.path_config.temp_dir):
            os.makedirs(tools.path_config.temp_dir)
        temp_json_path = os.path.normpath(tools.path_config.temp_auto_convert_args_json)
        if os.path.exists(temp_json_path):
            os.remove(temp_json_path)
        with open(temp_json_path, 'w', encoding='utf-8') as temp_json:
            json.dump(params, temp_json, ensure_ascii=False, indent=2)
        
        # 返回参数列表
        return [temp_json_path]
    
    

    def _on_auto_convert_finished(self, exit_code):

        if exit_code == 0:
            self.output_widget.append_text("\n✓ 自动转换完成")
            self.output_widget.append_text("=" * 20)
        else:
            self.output_widget.append_text("\n✗ 自动转换失败")
            self.output_widget.append_text("=" * 20)



    # debug
    # ----------------------------------------------------------------------
    # 按钮配置

    def _configure_buttons(self):

        self.check_availability_button.configure(
            script_path=os.path.join(root, "tools", "check_device.py"),
            args_generator=self._prepare_check_availability_args,
            output_widget=self.output_widget,
            on_finished=self._on_check_availability_finished
        )
        self.convert_model_button.configure(
            script_path=os.path.join(root, "tools", "export_models.py"),
            args_generator=self._prepare_convert_model_args,
            output_widget=self.output_widget,
            on_finished=self._on_convert_model_finished
        )
        self.auto_convert_button.configure(
            script_path=os.path.join(root, "convert_core", "All_in_one.py"),
            args_generator=self._prepare_auto_convert_args,
            output_widget=self.output_widget,
            on_finished=self._on_auto_convert_finished
        )
