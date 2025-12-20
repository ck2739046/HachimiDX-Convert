from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt
import os
import sys
import time
import re
import ast

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config
import tools.config_manager

from process_widgets import ProcessControlButton, OutputTextWidget
import ui_helpers


class SettingsPage(QWidget):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.colors = ui_helpers.COLORS
        
        # 第一行 模型管理
        self.backend_combo = None
        self.current_selected_backend = None  # backend_combo.currentText()备份
        # 第二行 模型管理
        self.env_status_label = None
        self.model_status_label = None
        self.batch_size_label = None
        self.batch_size_combo = None
        self.batch_size_help = None
        self.workspace_label = None
        self.workspace_combo = None
        self.workspace_help = None
        
        # FFmpeg 硬件加速配置
        self.vp9_combo = None
        self.h264_combo = None
        
        # 进程控制按钮
        self.check_availability_button = None  # 第一行
        self.convert_model_button = None       # 第二行
        self.ffmpeg_hw_button = None           # 第三行
        
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
    
    
    def create_config_area(self):
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {self.colors['bg']};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题分隔线：模型管理
        layout.addWidget(ui_helpers.create_divider("模型管理", down_margin=0))
                                                    # 分割线文字下方是文字，比按钮矮一些
                                                    # 需要删除down_margin以保证视觉上间距相等
        # 第一行：模型推理后端选择
        first_row = self.setup_1st_row()
        layout.addWidget(first_row)
        # 第二行：模型推理后端状态显示
        second_row = self.setup_2nd_row()
        layout.addWidget(second_row)

        # 标题分隔线：FFmpeg 硬件加速
        layout.addWidget(ui_helpers.create_divider("FFmpeg 硬件加速", width=114))
        # 第三行: FFmpeg 硬件加速配置行
        ffmpeg_row = self.setup_ffmpeg_hw_row()
        layout.addWidget(ffmpeg_row)
        
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
            45, ["1", "2", "3", "4", "5", "6", "7", "8"])
        self.batch_size_combo.hide()
        row_layout.addWidget(self.batch_size_combo)
        self.batch_size_help = ui_helpers.create_help_icon(
            "TensorRT 模型转换时的批处理大小\n" \
            "较大的 batch 可以提高推理效率，但会占用更多显存\n" \
            "转换后，batch_detect_obb 不能超过此数值")
        self.batch_size_help.hide()
        row_layout.addWidget(self.batch_size_help)

        # Label_ComboBox: Workspace（默认隐藏）
        self.workspace_label = ui_helpers.create_label("workspace:")
        self.workspace_label.hide()
        row_layout.addWidget(self.workspace_label)
        self.workspace_combo = ui_helpers.create_combo_box(
            65, ["auto", "1", "2", "3", "4", "5", "6", "7", "8"])
        self.workspace_combo.hide()
        row_layout.addWidget(self.workspace_combo)
        self.workspace_help = ui_helpers.create_help_icon(
            "TensorRT 引擎构建时的工作空间大小 (GB)\n" \
            "较大的 workspace 可以让 TensorRT 尝试更多优化策略\n" \
            "auto: 自动选择合适的 workspace 大小")
        self.workspace_help.hide()
        row_layout.addWidget(self.workspace_help)

        row_layout.addStretch()  # 添加弹性空间
        return row


    def setup_ffmpeg_hw_row(self):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # 检测按钮
        self.ffmpeg_hw_button = ProcessControlButton("检测硬件加速")
        self.ffmpeg_hw_button.setFixedSize(100, 25)
        row_layout.addWidget(self.ffmpeg_hw_button)

        # VP9 解码配置
        row_layout.addWidget(ui_helpers.create_label("VP9:"))
        self.vp9_combo = ui_helpers.create_combo_box(120, items=["cpu"])
        # 读取配置
        vp9_config, _ = tools.config_manager.get_config("ffmpeg_hw_acceleration_vp9")
        if vp9_config and vp9_config != "cpu":
            self.vp9_combo.addItem(vp9_config)
            self.vp9_combo.setCurrentText(vp9_config)
        else:
            self.vp9_combo.setCurrentText("cpu")
        self.vp9_combo.currentTextChanged.connect(self._on_ffmpeg_config_changed)
        row_layout.addWidget(self.vp9_combo)

        # H.264 编码配置
        row_layout.addWidget(ui_helpers.create_label("H.264:"))
        self.h264_combo = ui_helpers.create_combo_box(120, items=["cpu"])
        # 读取配置
        h264_config, _ = tools.config_manager.get_config("ffmpeg_hw_acceleration_h264")
        if h264_config and h264_config != "cpu":
            self.h264_combo.addItem(h264_config)
            self.h264_combo.setCurrentText(h264_config)
        else:
            self.h264_combo.setCurrentText("cpu")
        self.h264_combo.currentTextChanged.connect(self._on_ffmpeg_config_changed)
        row_layout.addWidget(self.h264_combo)

        row_layout.addStretch()
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
        self.batch_size_help.hide()
        self.workspace_label.hide()
        self.workspace_combo.hide()
        self.workspace_help.hide()
        
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
        else:  # DirectML
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
            # 保存配置
            error_msg = tools.config_manager.set_config("model_backend_selection", self.current_selected_backend)
            if error_msg:
                self.output_widget.append_text(f"\n✗ model_backend_selection 配置保存失败: {error_msg}")
            else:
                self.output_widget.append_text(f"\n✓ 配置已保存：model_backend_selection = {self.current_selected_backend}")
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
                self.batch_size_help.show()
                self.workspace_label.show()
                self.workspace_combo.show()
                self.workspace_help.show()
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
            self.batch_size_help.hide()
            self.workspace_label.hide()
            self.workspace_combo.hide()
            self.workspace_help.hide()
            # 更新模型状态
            self.model_status_label.setText("模型文件正常🟢")
            # 保存配置
            error_msg = tools.config_manager.set_config("model_backend_selection", self.current_selected_backend)
            if error_msg:
                self.output_widget.append_text(f"\n✗ model_backend_selection 配置保存失败: {error_msg}")
            else:
                self.output_widget.append_text(f"\n✓ 配置已保存：model_backend_selection = {self.current_selected_backend}")
            
            # 如果是 TensorRT，还要保存 batch_size 配置
            if self.current_selected_backend == "TensorRT":
                batch_size = self.batch_size_combo.currentText()
                error_msg = tools.config_manager.set_config("tensorRT_batch_size", batch_size)
                if error_msg:
                    self.output_widget.append_text(f"\n✗ tensorRT_batch_size 配置保存失败: {error_msg}")
                else:
                    self.output_widget.append_text(f"\n✓ 配置已保存：tensorRT_batch_size = {batch_size}")
        else:
            self.output_widget.append_text("\n✗ 模型转换失败")
            self.output_widget.append_text("=" * 20)
    
    







    # debug
    # ----------------------------------------------------------------------
    # FFmpeg 硬件加速检测逻辑
    
    def _prepare_check_ffmpeg_hw_args(self):
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始检测 FFmpeg 硬件加速支持...\n")
        return []
    

    def _on_check_ffmpeg_hw_finished(self, exit_code):
        if exit_code == 0:
            # 获取最近10行文本解析支持的硬件加速方案 ID
            recent_output = self.output_widget.get_recent_lines(10)
            match = re.search(r"支持的硬件加速方案ID: (\[.*?\])", recent_output)
            if match:
                try:
                    supported_ids = ast.literal_eval(match.group(1))
                    new_items = ['cpu'] + supported_ids
                    
                    # 更新 VP9 下拉框
                    current_vp9 = self.vp9_combo.currentText()
                    self.vp9_combo.blockSignals(True)
                    self.vp9_combo.clear()
                    self.vp9_combo.addItems(new_items)
                    if current_vp9 in new_items:
                        self.vp9_combo.setCurrentText(current_vp9)
                    else:
                        self.vp9_combo.setCurrentText('cpu')
                    self.vp9_combo.blockSignals(False)
                    
                    # 更新 H.264 下拉框
                    current_h264 = self.h264_combo.currentText()
                    self.h264_combo.blockSignals(True)
                    self.h264_combo.clear()
                    self.h264_combo.addItems(new_items)
                    if current_h264 in new_items:
                        self.h264_combo.setCurrentText(current_h264)
                    else:
                        self.h264_combo.setCurrentText('cpu')
                    self.h264_combo.blockSignals(False)
                    
                    self.output_widget.append_text("\n✓ 检测完成，已更新选项")
                    self.output_widget.append_text("=" * 20)
                    
                    # 触发一次保存，确保当前选中的值被记录（如果之前是无效值被重置为cpu的情况）
                    self._on_ffmpeg_config_changed(None)
                    
                except Exception as e:
                    self.output_widget.append_text(f"\n✗ 解析结果失败: {e}")
                    self.output_widget.append_text("=" * 20)
            else:
                self.output_widget.append_text("\n✗ 未能从输出中找到支持列表")
                self.output_widget.append_text("=" * 20)
        else:
            self.output_widget.append_text("\n✗ 检测失败")
            self.output_widget.append_text("=" * 20)


    def _on_ffmpeg_config_changed(self, text):
        # 保存 VP9 配置
        vp9_val = self.vp9_combo.currentText()
        tools.config_manager.set_config("ffmpeg_hw_acceleration_vp9", vp9_val)
        # 保存 H.264 配置
        h264_val = self.h264_combo.currentText()
        tools.config_manager.set_config("ffmpeg_hw_acceleration_h264", h264_val)







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
        self.ffmpeg_hw_button.configure(
            script_path=os.path.join(root, "tools", "check_ffmpeg_hw_acceleration.py"),
            args_generator=self._prepare_check_ffmpeg_hw_args,
            output_widget=self.output_widget,
            on_finished=self._on_check_ffmpeg_hw_finished
        )
