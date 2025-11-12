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
        
        # 第一行/第二行 模型区域
        self.backend_combo = None
        self.current_selected_backend = None # backend_combo.currentText()备份
        self.batch_detect_obb_combo = None # 自动转谱运行的时候用的
        self.batch_classify_combo = None   # 自动转谱运行的时候用的

        self.env_status_label = None
        self.model_status_label = None
        self.batch_size_label = None
        self.batch_size_combo = None
        self.workspace_label = None
        self.workspace_combo = None
        
        # 第三行/第四行/第五行 自动转谱参数区域
        self.video_path_label = None
        self.selected_video_path = None
        self.video_name_input = None

        self.video_type_combo = None
        self.bpm_input = None
        self.video_start_input = None
        self.video_end_input = None

        self.chart_lv_combo = None
        self.base_denominator_combo = None
        self.skip_detect_circle_checkbox = None
        self.skip_detect_checkbox = None
        self.skip_classify_checkbox = None

        # 进程控制按钮
        self.check_availability_button = None
        self.convert_model_button = None
        self.auto_convert_button = None
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
        widget.setFixedHeight(300)  # 固定高度
        widget.setStyleSheet(f"background-color: {self.colors['bg']};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # 第一行：模型推理后端选择
        first_row = self.setup_1st_row()
        layout.addWidget(first_row)
        
        # 第二行：模型推理后端状态显示
        second_row = self.setup_2nd_row()
        layout.addWidget(second_row)
        
        # 分隔线1
        layout.addWidget(ui_helpers.create_divider())

        # 第三行：选择谱面视频
        third_row = self.setup_3rd_row()
        layout.addWidget(third_row)
        
        # 第四行：视频参数设置
        fourth_row = self.setup_4th_row()
        layout.addWidget(fourth_row)
        
        # 第五行：高级参数设置
        fifth_row = self.setup_5th_row()
        layout.addWidget(fifth_row)

        # 分隔线2
        layout.addWidget(ui_helpers.create_divider())
        
        # 第六行：开始转谱
        sixth_row = self.setup_6th_row()
        layout.addWidget(sixth_row)

        layout.addStretch()  # 添加弹性空间，使整体靠上对齐
        
        return widget
    
    

    def setup_1st_row(self):

        first_row = QWidget()
        first_row_layout = QHBoxLayout(first_row)
        first_row_layout.setContentsMargins(0, 0, 0, 0)
        first_row_layout.setSpacing(5)
        
        # Label_ComboBox_Helper 模型推理后端
        backend_label = ui_helpers.create_label("模型推理后端:")
        first_row_layout.addWidget(backend_label)
        self.backend_combo = ui_helpers.create_combo_box(80, ["TensorRT", "DirectML"])
        first_row_layout.addWidget(self.backend_combo)
        help_label = ui_helpers.create_help_icon(
            "TensorRT: 适用于 NVIDIA GPU\nDirectML: 适用于 AMD/Intel/Other GPU")
        first_row_layout.addWidget(help_label)
        
        # check_availability button
        self.check_availability_button = ProcessControlButton("检查可用性")
        self.check_availability_button.setFixedSize(80, 25)
        first_row_layout.addWidget(self.check_availability_button)

        # Label_ComboBox batch_detect_obb(1-8)
        batch_detect_label = ui_helpers.create_label("batch_detect_obb:")
        first_row_layout.addWidget(batch_detect_label)
        self.batch_detect_obb_combo = ui_helpers.create_combo_box(
            45, ["1", "2", "3", "4", "5", "6", "7", "8"], default_index=1)
        first_row_layout.addWidget(self.batch_detect_obb_combo)
        
        # Label_ComboBox batch_classify(1,2,4,8,16,32)
        batch_classify_label = ui_helpers.create_label("batch_classify:")
        first_row_layout.addWidget(batch_classify_label)
        self.batch_classify_combo = ui_helpers.create_combo_box(
            45, ["1", "2", "4", "8", "16", "32"], default_index=4)
        first_row_layout.addWidget(self.batch_classify_combo)

        # Helper 解释这两个 batch 的作用
        batch_help = ui_helpers.create_help_icon("batch_detect_obb: 用于目标检测模型运行时的批处理大小\nbatch_classify: 用于图像分类模型运行时的批处理大小")
        first_row_layout.addWidget(batch_help)
        
        first_row_layout.addStretch()  # 添加弹性空间
        return first_row
    

    
    def setup_2nd_row(self):

        second_row = QWidget()
        second_row_layout = QHBoxLayout(second_row)
        second_row_layout.setContentsMargins(0, 0, 0, 0)
        second_row_layout.setSpacing(5)
        
        # Label: 运行环境状态
        self.env_status_label = ui_helpers.create_label("运行环境待检测⚪")
        second_row_layout.addWidget(self.env_status_label)
        
        # Label: 模型状态
        self.model_status_label = ui_helpers.create_label("模型文件待检测⚪")
        second_row_layout.addWidget(self.model_status_label)

        # 按钮: "转换模型"（默认隐藏）
        self.convert_model_button = ProcessControlButton("转换模型")
        self.convert_model_button.setFixedSize(80, 25)
        self.convert_model_button.hide()
        second_row_layout.addWidget(self.convert_model_button)
        
        # Label_ComboBox Batch_size（默认隐藏）
        self.batch_size_label = ui_helpers.create_label("batch:")
        self.batch_size_label.hide()
        second_row_layout.addWidget(self.batch_size_label)
        self.batch_size_combo = ui_helpers.create_combo_box(
            35, ["1", "2", "3", "4", "5", "6", "7", "8"])
        self.batch_size_combo.hide()
        second_row_layout.addWidget(self.batch_size_combo)
        
        # Label_ComboBox: Workspace（默认隐藏）
        self.workspace_label = ui_helpers.create_label("workspace:")
        self.workspace_label.hide()
        second_row_layout.addWidget(self.workspace_label)
        self.workspace_combo = ui_helpers.create_combo_box(
            65, ["auto", "1", "2", "3", "4", "5", "6", "7", "8"])
        self.workspace_combo.hide()
        second_row_layout.addWidget(self.workspace_combo)
        
        second_row_layout.addStretch()  # 添加弹性空间，使控件靠左对齐
        return second_row
    

    
    def setup_3rd_row(self):

        third_row = QWidget()
        third_row_layout = QHBoxLayout(third_row)
        third_row_layout.setContentsMargins(0, 0, 0, 0)
        third_row_layout.setSpacing(5)
        
        # 按钮: "选择谱面视频"
        select_video_button = QPushButton("选择谱面视频")
        select_video_button.setStyleSheet(f'''
            QPushButton {{
                background-color: {self.colors['accent']};
            }}QPushButton:hover {{
                background-color: {self.colors['accent_hover']};
            }}''')
        select_video_button.setFixedSize(100, 25)
        select_video_button.clicked.connect(self._on_select_video)
        third_row_layout.addWidget(select_video_button)
        
        # 输入框: 视频名称
        self.video_name_input = ui_helpers.create_line_edit(300, placeholder="歌曲名称")
        third_row_layout.addWidget(self.video_name_input)

        # Label: 显示选择的视频路径 (只读，但是允许用户复制)
        self.video_path_label = QLineEdit("")
        self.video_path_label.setStyleSheet(f"background-color: {self.colors['grey']}; font-size: 13px;")
        self.video_path_label.setReadOnly(True)
        self.video_path_label.setFixedHeight(25)
        self.video_path_label.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        third_row_layout.addWidget(self.video_path_label)

        # third_row_layout.addStretch()  # 添加弹性空间
        return third_row
    


    def _on_select_video(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("video (*.mkv *.mp4 *.webm *.avi)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.selected_video_path = selected_files[0]
                self.video_path_label.setText(self.selected_video_path)
    

    
    def setup_4th_row(self):

        fourth_row = QWidget()
        fourth_row_layout = QHBoxLayout(fourth_row)
        fourth_row_layout.setContentsMargins(0, 0, 0, 0)
        fourth_row_layout.setSpacing(5)
        
        # Label_ComboBox_Helper 视频形式
        video_type_label = ui_helpers.create_label("视频形式:")
        fourth_row_layout.addWidget(video_type_label)
        self.video_type_combo = ui_helpers.create_combo_box(120, ["source video", "camera footage"])
        fourth_row_layout.addWidget(self.video_type_combo)
        video_type_help = ui_helpers.create_help_icon("source video: 游戏原生画面\ncamera footage: 相机拍屏幕")
        fourth_row_layout.addWidget(video_type_help)
        
        # Label_LineEdit_Helper 歌曲范围
        video_range_label = ui_helpers.create_label("歌曲范围:")
        fourth_row_layout.addWidget(video_range_label)

        start_validator = QDoubleValidator(-1.0, 999.0, 1, self) # -1_999的浮点数
        self.video_start_input = ui_helpers.create_line_edit(70, validator=start_validator, placeholder="0~999/-1")
        fourth_row_layout.addWidget(self.video_start_input)

        arrow_label = ui_helpers.create_label("->")
        fourth_row_layout.addWidget(arrow_label)

        end_validator = QDoubleValidator(-1.0, 999.0, 1, self) # -1_999的浮点数
        self.video_end_input = ui_helpers.create_line_edit(70, validator=end_validator, placeholder="0~999/-1")
        fourth_row_layout.addWidget(self.video_end_input)

        video_range_help = ui_helpers.create_help_icon(
            "歌曲真正起始和结束的时间(秒)\n"
            "-1 表示视频开头第 0 秒或结尾最后 1 秒\n"
            "正确的歌曲起始应该是游戏走转场刚刚进入黑屏，并且乐曲启动拍还没响的时间"
            "\n正确的歌曲结束应该是歌曲最后一个音符消失后的时间")
        fourth_row_layout.addWidget(video_range_help)

        # Label_LineEdit 歌曲bpm
        bpm_label = ui_helpers.create_label("歌曲bpm:")
        fourth_row_layout.addWidget(bpm_label)
        bpm_validator = QDoubleValidator(10.0, 999.0, 3, self) # 10_999的浮点数
        self.bpm_input = ui_helpers.create_line_edit(70, validator=bpm_validator, placeholder="10~999")
        fourth_row_layout.addWidget(self.bpm_input)

        fourth_row_layout.addStretch()  # 添加弹性空间
        return fourth_row
    
    

    def setup_5th_row(self):

        fifth_row = QWidget()
        fifth_row_layout = QHBoxLayout(fifth_row)
        fifth_row_layout.setContentsMargins(0, 0, 0, 0)
        fifth_row_layout.setSpacing(5)

        # Label_ComboBox_Helper 谱面难度
        chart_lv_label = ui_helpers.create_label("谱面难度:")
        fifth_row_layout.addWidget(chart_lv_label)
        self.chart_lv_combo = ui_helpers.create_combo_box(
            45, ["1", "2", "3", "4", "5", "6", "7"], default_index=4)
        fifth_row_layout.addWidget(self.chart_lv_combo)
        chart_lv_help = ui_helpers.create_help_icon(
            "1-easy\n2-basic\n3-normal\n4-expert\n5-master\n6-re:master\n7-utage")
        fifth_row_layout.addWidget(chart_lv_help)
        
        # Label_ComboBox_Helper base_denominator
        base_denominator_label = ui_helpers.create_label("解析分辨率:")
        fifth_row_layout.addWidget(base_denominator_label)
        self.base_denominator_combo = ui_helpers.create_combo_box(
            45, ["4", "8", "16", "32", "64"], default_index=2)
        fifth_row_layout.addWidget(self.base_denominator_combo)
        base_denominator_help = ui_helpers.create_help_icon(
            "程序解析谱面的分辨率，默认为16，意味着程序会将音符对齐到1/16的时间")
        fifth_row_layout.addWidget(base_denominator_help)

        # Label_CheckBox_Helper skip_detect_circle
        skip_detect_label = ui_helpers.create_label("skip_detect_circle:")
        fifth_row_layout.addWidget(skip_detect_label)
        self.skip_detect_circle_checkbox = ui_helpers.create_check_box()
        fifth_row_layout.addWidget(self.skip_detect_circle_checkbox)
        skip_detect_help = ui_helpers.create_help_icon(
            "程序会尝试自动检测圆形游戏屏幕的位置\n如果在当前谱面确认视频中，游戏画面已经是全屏并且在屏幕中心，可以跳过检测")
        fifth_row_layout.addWidget(skip_detect_help)
        
        # Label_CheckBox_Helper skip_detect
        skip_detect_label2 = ui_helpers.create_label("skip_detect:")
        fifth_row_layout.addWidget(skip_detect_label2)
        self.skip_detect_checkbox = ui_helpers.create_check_box()
        fifth_row_layout.addWidget(self.skip_detect_checkbox)
        skip_detect_help2 = ui_helpers.create_help_icon(
            "跳过逐帧检测视频中的音符，直接读取已经存在的检测结果 (detect_result.txt)"
        )
        fifth_row_layout.addWidget(skip_detect_help2)
        
        # Label_CheckBox_Helper skip_classify
        skip_classify_label = ui_helpers.create_label("skip_classify:")
        fifth_row_layout.addWidget(skip_classify_label)
        self.skip_classify_checkbox = ui_helpers.create_check_box()
        fifth_row_layout.addWidget(self.skip_classify_checkbox)
        skip_classify_help = ui_helpers.create_help_icon(
            "跳过分类检测 ex-note, break-note, ex-break-note")
        fifth_row_layout.addWidget(skip_classify_help)
        
        fifth_row_layout.addStretch()  # 添加弹性空间
        return fifth_row
    
    

    def setup_6th_row(self):

        sixth_row = QWidget()
        sixth_row_layout = QHBoxLayout(sixth_row)
        sixth_row_layout.setContentsMargins(0, 0, 0, 0)
        sixth_row_layout.setSpacing(5)
        
        # 大按钮: "Start Auto Convert!"（使用新组件）
        self.auto_convert_button = ProcessControlButton("Start Auto Convert!")
        self.auto_convert_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                font-size: 16px;
                font-weight: bold;
                padding: 10px 20px;
            }}QPushButton:hover {{
                background-color: {self.colors['accent_hover']};
            }}""")
        self.auto_convert_button.setFixedSize(200, 50)
        sixth_row_layout.addWidget(self.auto_convert_button)
        
        sixth_row_layout.addStretch()  # 添加弹性空间
        return sixth_row

    
    
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
        # 验证必填参数
        if not self.selected_video_path:
            QMessageBox.warning(self, "参数错误", "请先选择谱面视频文件")
            return None
        
        video_name = self.video_name_input.text().strip()
        if not video_name:
            QMessageBox.warning(self, "参数错误", "请输入歌曲名称")
            return None
        
        bpm = self.bpm_input.text().strip()
        if not bpm:
            QMessageBox.warning(self, "参数错误", "请输入歌曲 BPM")
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
        bpm = round(float(bpm), 3)
        if video_start != -1:
            video_start = round(video_start, 1)
            if video_start < 0 or video_start > 999:
                QMessageBox.warning(self, "参数错误", "歌曲起始时间应在 0~999 秒范围内，或为 -1")
                return None
        if video_end != -1:
            video_end = round(video_end, 1)
            if video_end < 0 or video_end > 999:
                QMessageBox.warning(self, "参数错误", "歌曲结束时间应在 0~999 秒范围内，或为 -1")
                return None
        if bpm < 10 or bpm > 999:
            QMessageBox.warning(self, "参数错误", "歌曲 BPM 应在 10~999 范围内")
            return None
        
        # 使用 OpenCV 获取视频的实际 FPS
        try:
            cap = cv2.VideoCapture(self.selected_video_path)
            if not cap.isOpened():
                QMessageBox.warning(self, "视频错误", "无法打开视频文件")
                return None
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            if video_fps <= 0:
                QMessageBox.warning(self, "视频错误", "无法获取视频 FPS 信息")
                return None
            self.output_widget.append_text(f"检测到谱面确认视频 FPS: {video_fps:.2f}")
        except Exception as e:
            QMessageBox.warning(self, "视频错误", f"读取视频 FPS 失败: {str(e)}")
            return None
        
        # 根据后端选择模型路径和推理设备
        backend = self.backend_combo.currentText()
        if backend == "TensorRT":
            model_paths = {
                "detect": os.path.normpath(tools.path_config.detect_engine),
                "obb": os.path.normpath(tools.path_config.obb_pt),
                "cls_break": os.path.normpath(tools.path_config.cls_break_pt),
                "cls_ex": os.path.normpath(tools.path_config.cls_ex_pt)
            }
            inference_device = "0"
        else:  # DirectML
            model_paths = {
                "detect": os.path.normpath(tools.path_config.detect_onnx),
                "obb": os.path.normpath(tools.path_config.obb_onnx),
                "cls_break": os.path.normpath(tools.path_config.cls_break_onnx),
                "cls_ex": os.path.normpath(tools.path_config.cls_ex_onnx)
            }
            inference_device = "NONE"
        
        # 收集所有参数
        params = {
            # standardizer 参数
            "video_path": self.selected_video_path,
            "video_mode": self.video_type_combo.currentText(),
            "start_frame": round(video_start * video_fps) if video_start >= 0 else -1,  # 使用实际 FPS 转换为帧数
            "end_frame": round(video_end * video_fps) if video_end >= 0 else -1,        # 使用实际 FPS 转换为帧数
            "target_res": 1080,
            "skip_detect_circle": self.skip_detect_circle_checkbox.isChecked(),
            
            # note-detector 参数
            "video_name": video_name,
            "batch_detect": int(self.batch_detect_obb_combo.currentText()),
            "batch_cls": int(self.batch_classify_combo.currentText()),
            "inference_device": inference_device,
            "detect_model": model_paths["detect"],
            "obb_model": model_paths["obb"],
            "cls_ex_model": model_paths["cls_ex"],
            "cls_break_model": model_paths["cls_break"],
            "skip_detect": self.skip_detect_checkbox.isChecked(),
            "skip_classify": self.skip_classify_checkbox.isChecked(),
            
            # note_analyzer 参数
            "bpm": bpm,
            "chart_lv": int(self.chart_lv_combo.currentText()),
            "base_denominator": int(self.base_denominator_combo.currentText())
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
