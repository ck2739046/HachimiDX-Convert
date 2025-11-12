from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
                             QLabel, QComboBox, QToolTip, QFileDialog, QLineEdit, QCheckBox, QMessageBox)
from PyQt6.QtCore import pyqtSlot, Qt, QProcess, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCursor, QCursor, QIntValidator, QDoubleValidator
import os
import sys
import time
import re
import json
import tempfile
import cv2

root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config

# 导入新的进程控制组件
from process_widgets import ProcessControlButton, OutputTextWidget


# debug
class AutoConvertPage(QWidget):
    
    def __init__(self, 
                 colors,                # 配色方案字典
                 folder_combobox_class, # FolderComboBox 类引用（用于创建不可编辑的选择框）
                 parent=None):          # 父 widget

        super().__init__(parent)
        
        # 保存传入的依赖
        self.colors = colors
        self.FolderComboBox = folder_combobox_class
        
        # 第一行/第二行控件
        self.backend_combo = None
        self.current_selected_backend = None
        self.batch_detect_obb_combo = None
        self.batch_classify_combo = None
        self.env_status_label = None
        self.model_status_label = None
        self.convert_model_button = None
        self.batch_size_label = None
        self.batch_size_input = None
        
        # 第三行/第四行/第五行控件
        self.video_path_label = None
        self.selected_video_path = None
        self.video_name_input = None
        self.video_type_combo = None
        self.bpm_input = None
        self.video_start_input = None
        self.video_end_input = None
        self.target_res_input = None
        self.chart_lv_combo = None
        self.base_denominator_combo = None
        self.skip_detect_circle_checkbox = None
        self.skip_detect_checkbox = None
        self.skip_classify_checkbox = None

        # 进程控制按钮（新组件）
        self.check_button = None
        self.convert_button = None
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
        output_widget = self.create_output_area()
        page_layout.addWidget(output_widget)
        
        # 配置所有进程控制按钮
        self._configure_buttons()
    
    
    # debug
    def create_config_area(self):
        widget = QWidget()
        widget.setFixedHeight(400)  # 固定高度
        widget.setStyleSheet(f"background-color: {self.colors['bg']};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # 第一行：，模型推理后端选择
        first_row = self.setup_1st_row()
        layout.addWidget(first_row)
        
        # 第二行：模型推理后端状态显示
        second_row = self.setup_2nd_row()
        layout.addWidget(second_row)
        
        # 分隔线
        divider_container = QWidget()
        divider_layout = QVBoxLayout(divider_container)
        divider_layout.setContentsMargins(0, 10, 0, 10)  # 上下各10像素间距
        divider_layout.setSpacing(0)
        divider_line = QWidget()
        divider_line.setFixedHeight(2)  # 细线高度
        divider_line.setStyleSheet(f"background-color: {self.colors['grey']};")
        divider_layout.addWidget(divider_line)
        layout.addWidget(divider_container)

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
        divider_container2 = QWidget()
        divider_layout2 = QVBoxLayout(divider_container2)
        divider_layout2.setContentsMargins(0, 10, 0, 10)  # 上下各10像素间距
        divider_layout2.setSpacing(0)
        divider_line2 = QWidget()
        divider_line2.setFixedHeight(2)  # 细线高度
        divider_line2.setStyleSheet(f"background-color: {self.colors['grey']};")
        divider_layout2.addWidget(divider_line2)
        layout.addWidget(divider_container2)
        
        # 第六行：开始自动转换按钮
        sixth_row = self.setup_6th_row()
        layout.addWidget(sixth_row)

        layout.addStretch()  # 添加弹性空间，使整体靠上对齐
        
        return widget
    
    
    def setup_1st_row(self):
        """第一行：模型推理后端选择"""
        first_row = QWidget()
        first_row_layout = QHBoxLayout(first_row)
        first_row_layout.setContentsMargins(0, 0, 0, 0)
        first_row_layout.setSpacing(5)
        
        # Label: '模型推理后端：'
        backend_label = QLabel("模型推理后端:")
        backend_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        first_row_layout.addWidget(backend_label)
        
        # ComboBox: 后端选择（不可编辑）
        self.backend_combo = QComboBox()
        self.backend_combo.setEditable(False)
        self.backend_combo.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.backend_combo.setFixedSize(80, 25)
        self.backend_combo.addItems(["TensorRT", "DirectML"])
        first_row_layout.addWidget(self.backend_combo)
        
        # 帮助图标（圆圈中带问号）
        help_label = QLabel("❓")
        help_label.setStyleSheet(f"font-size: 13px;")
        help_label.setFixedSize(10, 20)
        help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_label.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        help_label.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "TensorRT: 适用于 NVIDIA GPU\nDirectML: 适用于 AMD/Intel/Other GPU",
            help_label,
            help_label.rect()
        )
        help_label.leaveEvent = lambda event: QToolTip.hideText()
        first_row_layout.addWidget(help_label)
        
        # 按钮: "检查可用性"（使用新组件）
        self.check_button = ProcessControlButton("检查可用性", self.colors)
        self.check_button.setFixedSize(80, 25)
        first_row_layout.addWidget(self.check_button)

                # Label: "batch_detect_obb:"
        batch_detect_label = QLabel("batch_detect_obb:")
        batch_detect_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        first_row_layout.addWidget(batch_detect_label)
        
        # ComboBox: batch_detect_obb（1-8）
        self.batch_detect_obb_combo = QComboBox()
        self.batch_detect_obb_combo.setEditable(False)
        self.batch_detect_obb_combo.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.batch_detect_obb_combo.setFixedSize(45, 25)
        self.batch_detect_obb_combo.addItems(["1", "2", "3", "4", "5", "6", "7", "8"])
        self.batch_detect_obb_combo.setCurrentIndex(1)  # 默认选择2
        first_row_layout.addWidget(self.batch_detect_obb_combo)
        
        # Label: "batch_classify:"
        batch_classify_label = QLabel("batch_classify:")
        batch_classify_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        first_row_layout.addWidget(batch_classify_label)
        
        # ComboBox: batch_classify（1,2,4,8,16,32）
        self.batch_classify_combo = QComboBox()
        self.batch_classify_combo.setEditable(False)
        self.batch_classify_combo.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.batch_classify_combo.setFixedSize(45, 25)
        self.batch_classify_combo.addItems(["1", "2", "4", "8", "16", "32"])
        self.batch_classify_combo.setCurrentIndex(4)  # 默认选择16
        first_row_layout.addWidget(self.batch_classify_combo)
        
        # 配置按钮（稍后在 setup_ui 完成后配置）
        
        first_row_layout.addStretch()  # 添加弹性空间
        
        return first_row
    
    
    def setup_2nd_row(self):
        """第二行：模型推理后端状态显示与模型转换"""
        second_row = QWidget()
        second_row_layout = QHBoxLayout(second_row)
        second_row_layout.setContentsMargins(0, 0, 0, 0)
        second_row_layout.setSpacing(5)
        
        # Label: 运行环境状态
        self.env_status_label = QLabel("运行环境待检测⚪")
        self.env_status_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        second_row_layout.addWidget(self.env_status_label)
        
        # Label: 模型状态
        self.model_status_label = QLabel("模型文件待检测⚪")
        self.model_status_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        second_row_layout.addWidget(self.model_status_label)
        
        # Label: Batch（默认隐藏）
        self.batch_size_label = QLabel("batch:")
        self.batch_size_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        self.batch_size_label.hide()
        second_row_layout.addWidget(self.batch_size_label)
        
        # 输入框: Batch Size（默认隐藏）
        self.batch_size_input = QComboBox()
        self.batch_size_input.setEditable(False)
        self.batch_size_input.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.batch_size_input.addItems(["1", "2", "3", "4", "5", "6", "7", "8"])
        self.batch_size_input.setFixedSize(35, 25)
        self.batch_size_input.hide()
        second_row_layout.addWidget(self.batch_size_input)
        
        # Label: Workspace（默认隐藏）
        self.workspace_label = QLabel("workspace:")
        self.workspace_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        self.workspace_label.hide()
        second_row_layout.addWidget(self.workspace_label)
        
        # 输入框: Workspace（默认隐藏）
        self.workspace_input = QComboBox()
        self.workspace_input.setEditable(False)
        self.workspace_input.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.workspace_input.addItems(["auto", "1", "2", "3", "4", "5", "6", "7", "8"])
        self.workspace_input.setFixedSize(65, 25)
        self.workspace_input.hide()
        second_row_layout.addWidget(self.workspace_input)
        
        # 按钮: "转换模型"（默认隐藏，使用新组件）
        self.convert_button = ProcessControlButton("转换模型", self.colors)
        self.convert_button.setFixedSize(80, 25)
        self.convert_button.hide()  # 默认隐藏
        second_row_layout.addWidget(self.convert_button)
        
        # 配置按钮（稍后在 setup_ui 完成后配置）
        
        second_row_layout.addStretch()  # 添加弹性空间，使控件靠左对齐
        
        return second_row
    
    
    def setup_3rd_row(self):
        """第三行：选择谱面视频"""
        third_row = QWidget()
        third_row_layout = QHBoxLayout(third_row)
        third_row_layout.setContentsMargins(0, 0, 0, 0)
        third_row_layout.setSpacing(5)
        
        # 按钮: "选择谱面视频"
        select_video_button = QPushButton("选择谱面视频")
        select_video_button.setStyleSheet(f"background-color: {self.colors['accent']};")
        select_video_button.setFixedSize(100, 25)
        select_video_button.clicked.connect(self._on_select_video)
        third_row_layout.addWidget(select_video_button)
        
        # 输入框: 视频名称
        self.video_name_input = QLineEdit()
        self.video_name_input.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.video_name_input.setFixedSize(300, 25)
        self.video_name_input.setPlaceholderText("歌曲名称")
        third_row_layout.addWidget(self.video_name_input)

        # Label: 显示选择的视频路径 (允许用户复制)
        self.video_path_label = QLineEdit("")
        self.video_path_label.setStyleSheet(f"background-color: {self.colors['grey']}; font-size: 13px;")
        self.video_path_label.setReadOnly(True)
        self.video_path_label.setFixedHeight(25)
        third_row_layout.addWidget(self.video_path_label)

        # third_row_layout.addStretch()  # 添加弹性空间
        
        return third_row
    
    
    def setup_4th_row(self):
        """第四行：视频参数设置"""
        fourth_row = QWidget()
        fourth_row_layout = QHBoxLayout(fourth_row)
        fourth_row_layout.setContentsMargins(0, 0, 0, 0)
        fourth_row_layout.setSpacing(5)
        
        # Label: "视频形式:"
        video_type_label = QLabel("视频形式:")
        video_type_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fourth_row_layout.addWidget(video_type_label)
        
        # ComboBox: 视频形式选择
        self.video_type_combo = QComboBox()
        self.video_type_combo.setEditable(False)
        self.video_type_combo.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.video_type_combo.setFixedSize(120, 25)
        self.video_type_combo.addItems(["source", "camera footage"])
        fourth_row_layout.addWidget(self.video_type_combo)

        # 帮助图标：视频形式
        video_type_help = QLabel("❓")
        video_type_help.setStyleSheet(f"font-size: 13px;")
        video_type_help.setFixedSize(10, 20)
        video_type_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        video_type_help.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        video_type_help.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "source: 游戏原生画面\ncamera footage: 相机拍屏幕",
            video_type_help,
            video_type_help.rect()
        )
        video_type_help.leaveEvent = lambda event: QToolTip.hideText()
        fourth_row_layout.addWidget(video_type_help)
        
        # Label: "歌曲bpm:"
        bpm_label = QLabel("歌曲bpm:")
        bpm_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fourth_row_layout.addWidget(bpm_label)
        
        # 输入框: BPM（>=10的整数）
        self.bpm_input = QLineEdit()
        self.bpm_input.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.bpm_input.setFixedSize(70, 25)
        self.bpm_input.setPlaceholderText("≥10")
        bpm_validator = QDoubleValidator(10, 999, 3, self)
        self.bpm_input.setValidator(bpm_validator)
        fourth_row_layout.addWidget(self.bpm_input)
        
        # Label: "歌曲范围:"
        video_range_label = QLabel("歌曲范围:")
        video_range_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fourth_row_layout.addWidget(video_range_label)
        
        # 输入框: 起始秒数（>=-1的整数）
        self.video_start_input = QLineEdit()
        self.video_start_input.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.video_start_input.setFixedSize(50, 25)
        self.video_start_input.setPlaceholderText("≥-1")
        start_validator = QIntValidator(-1, 999, self)
        self.video_start_input.setValidator(start_validator)
        fourth_row_layout.addWidget(self.video_start_input)
        
        # Label: "->"
        arrow_label = QLabel("->")
        arrow_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fourth_row_layout.addWidget(arrow_label)
        
        # 输入框: 结束秒数（>=-1的整数）
        self.video_end_input = QLineEdit()
        self.video_end_input.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.video_end_input.setFixedSize(50, 25)
        self.video_end_input.setPlaceholderText("≥-1")
        end_validator = QIntValidator(-1, 999, self)
        self.video_end_input.setValidator(end_validator)
        fourth_row_layout.addWidget(self.video_end_input)

        # 帮助图标：歌曲范围
        video_range_help = QLabel("❓")
        video_range_help.setStyleSheet(f"font-size: 13px;")
        video_range_help.setFixedSize(10, 20)
        video_range_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        video_range_help.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        video_range_help.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "歌曲真正起始和结束的时间(秒)\n" \
            "-1 表示视频开头第 0 秒或结尾最后 1 秒\n" \
            "正确的歌曲起始应该是游戏走转场刚刚进入黑屏，并且乐曲启动拍还没响的时间" \
            "\n正确的歌曲结束应该是歌曲最后一个音符消失后的时间",
            video_range_help,
            video_range_help.rect()
        )
        video_range_help.leaveEvent = lambda event: QToolTip.hideText()
        fourth_row_layout.addWidget(video_range_help)

        # Label: "目标分辨率:"
        target_res_label = QLabel("目标分辨率:")
        target_res_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fourth_row_layout.addWidget(target_res_label)
        
        # 输入框: 目标分辨率（720-2160的整数，默认1080）
        self.target_res_input = QLineEdit()
        self.target_res_input.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.target_res_input.setFixedSize(60, 25)
        self.target_res_input.setText("1080")
        target_res_validator = QIntValidator(720, 2160, self)
        self.target_res_input.setValidator(target_res_validator)
        fourth_row_layout.addWidget(self.target_res_input)
        
        # 帮助图标：目标分辨率
        target_res_help = QLabel("❓")
        target_res_help.setStyleSheet(f"font-size: 13px;")
        target_res_help.setFixedSize(10, 20)
        target_res_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        target_res_help.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        target_res_help.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "程序生成的标准化视频的分辨率，默认1080x1080",
            target_res_help,
            target_res_help.rect()
        )
        target_res_help.leaveEvent = lambda event: QToolTip.hideText()
        fourth_row_layout.addWidget(target_res_help)

        fourth_row_layout.addStretch()  # 添加弹性空间
        
        return fourth_row
    
    
    def setup_5th_row(self):
        """第五行：高级参数设置"""
        fifth_row = QWidget()
        fifth_row_layout = QHBoxLayout(fifth_row)
        fifth_row_layout.setContentsMargins(0, 0, 0, 0)
        fifth_row_layout.setSpacing(5)

        # Label: "谱面难度:"
        chart_lv_label = QLabel("谱面难度:")
        chart_lv_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fifth_row_layout.addWidget(chart_lv_label)
        
        # ComboBox: 谱面难度（1-7）
        self.chart_lv_combo = QComboBox()
        self.chart_lv_combo.setEditable(False)
        self.chart_lv_combo.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.chart_lv_combo.setFixedSize(35, 25)
        self.chart_lv_combo.addItems(["1", "2", "3", "4", "5", "6", "7"])
        self.chart_lv_combo.setCurrentIndex(3)  # 默认选择4（expert）
        fifth_row_layout.addWidget(self.chart_lv_combo)
        
        # 帮助图标：谱面难度
        chart_lv_help = QLabel("❓")
        chart_lv_help.setStyleSheet(f"font-size: 13px;")
        chart_lv_help.setFixedSize(10, 20)
        chart_lv_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_lv_help.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        chart_lv_help.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "1-easy, 2-basic, 3-normal, 4-expert, 5-master, 6-re:master, 7-utage",
            chart_lv_help,
            chart_lv_help.rect()
        )
        chart_lv_help.leaveEvent = lambda event: QToolTip.hideText()
        fifth_row_layout.addWidget(chart_lv_help)
        
        # Label: "解析分辨率:"
        base_denominator_label = QLabel("解析分辨率:")
        base_denominator_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fifth_row_layout.addWidget(base_denominator_label)
        
        # ComboBox: 解析分辨率（4,8,16,32,64，默认16）
        self.base_denominator_combo = QComboBox()
        self.base_denominator_combo.setEditable(False)
        self.base_denominator_combo.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.base_denominator_combo.setFixedSize(45, 25)
        self.base_denominator_combo.addItems(["4", "8", "16", "32", "64"])
        self.base_denominator_combo.setCurrentIndex(2)  # 默认选择16
        fifth_row_layout.addWidget(self.base_denominator_combo)
        
        # 帮助图标：解析分辨率
        base_denominator_help = QLabel("❓")
        base_denominator_help.setStyleSheet(f"font-size: 13px;")
        base_denominator_help.setFixedSize(10, 20)
        base_denominator_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_denominator_help.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        base_denominator_help.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "程序解析谱面的分辨率，默认为16，意味着程序会将音符对齐到1/16的时间",
            base_denominator_help,
            base_denominator_help.rect()
        )
        base_denominator_help.leaveEvent = lambda event: QToolTip.hideText()
        fifth_row_layout.addWidget(base_denominator_help)

        # Label: "skip_detect_circle"
        skip_detect_label = QLabel("skip_detect_circle:")
        skip_detect_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fifth_row_layout.addWidget(skip_detect_label)
        
        # CheckBox: 跳过检测圆形
        self.skip_detect_circle_checkbox = QCheckBox()
        self.skip_detect_circle_checkbox.setFixedSize(20, 20)
        self.skip_detect_circle_checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                background-color: {self.colors['grey']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors['accent']};
            }}
        """)
        fifth_row_layout.addWidget(self.skip_detect_circle_checkbox)
        
        # 帮助图标：skip_detect_circle
        skip_detect_help = QLabel("❓")
        skip_detect_help.setStyleSheet(f"font-size: 13px;")
        skip_detect_help.setFixedSize(10, 20)
        skip_detect_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skip_detect_help.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        skip_detect_help.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "程序会尝试自动检测圆形游戏屏幕的位置\n如果在当前谱面确认视频中，游戏画面已经是全屏并且在屏幕中心，可以跳过检测",
            skip_detect_help,
            skip_detect_help.rect()
        )
        skip_detect_help.leaveEvent = lambda event: QToolTip.hideText()
        fifth_row_layout.addWidget(skip_detect_help)
        
        # Label: "skip_detect"
        skip_detect_label2 = QLabel("skip_detect:")
        skip_detect_label2.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fifth_row_layout.addWidget(skip_detect_label2)
        
        # CheckBox: 跳过逐帧检测
        self.skip_detect_checkbox = QCheckBox()
        self.skip_detect_checkbox.setFixedSize(20, 20)
        self.skip_detect_checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                background-color: {self.colors['grey']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors['accent']};
            }}
        """)
        fifth_row_layout.addWidget(self.skip_detect_checkbox)
        
        # 帮助图标：skip_detect
        skip_detect_help2 = QLabel("❓")
        skip_detect_help2.setStyleSheet(f"font-size: 13px;")
        skip_detect_help2.setFixedSize(10, 20)
        skip_detect_help2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skip_detect_help2.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        skip_detect_help2.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "跳过逐帧检测视频中的音符，直接读取已经存在的检测结果 (detect_result.txt)",
            skip_detect_help2,
            skip_detect_help2.rect()
        )
        skip_detect_help2.leaveEvent = lambda event: QToolTip.hideText()
        fifth_row_layout.addWidget(skip_detect_help2)
        
        # Label: "skip_classify"
        skip_classify_label = QLabel("skip_classify:")
        skip_classify_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        fifth_row_layout.addWidget(skip_classify_label)
        
        # CheckBox: 跳过分类检测
        self.skip_classify_checkbox = QCheckBox()
        self.skip_classify_checkbox.setFixedSize(20, 20)
        self.skip_classify_checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                background-color: {self.colors['grey']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors['accent']};
            }}
        """)
        fifth_row_layout.addWidget(self.skip_classify_checkbox)
        
        # 帮助图标：skip_classify
        skip_classify_help = QLabel("❓")
        skip_classify_help.setStyleSheet(f"font-size: 13px;")
        skip_classify_help.setFixedSize(10, 20)
        skip_classify_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skip_classify_help.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        skip_classify_help.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "跳过分类检测 ex-note, break-note, ex-break-note",
            skip_classify_help,
            skip_classify_help.rect()
        )
        skip_classify_help.leaveEvent = lambda event: QToolTip.hideText()
        fifth_row_layout.addWidget(skip_classify_help)
        
        fifth_row_layout.addStretch()  # 添加弹性空间
        
        return fifth_row
    
    
    def setup_6th_row(self):
        """第六行：开始自动转换按钮"""
        sixth_row = QWidget()
        sixth_row_layout = QHBoxLayout(sixth_row)
        sixth_row_layout.setContentsMargins(0, 0, 0, 0)
        sixth_row_layout.setSpacing(5)
        
        # 大按钮: "Start Auto Convert!"（使用新组件）
        self.auto_convert_button = ProcessControlButton("Start Auto Convert!", self.colors)
        self.auto_convert_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                font-size: 16px;
                font-weight: bold;
                padding: 10px 20px;
            }}
        """)
        self.auto_convert_button.setFixedSize(200, 50)
        sixth_row_layout.addWidget(self.auto_convert_button)
        
        # 配置按钮（稍后在 setup_ui 完成后配置）
        
        sixth_row_layout.addStretch()  # 添加弹性空间
        
        return sixth_row
    

    def _configure_buttons(self):
        """配置所有进程控制按钮"""
        # 配置"检查可用性"按钮
        self.check_button.configure(
            script_path=os.path.join(root, "tools", "check_device.py"),
            args_generator=self._prepare_check_availability_args,
            output_widget=self.output_widget,
            on_finished=self._on_check_availability_finished
        )
        
        # 配置"转换模型"按钮
        self.convert_button.configure(
            script_path=os.path.join(root, "tools", "export_models.py"),
            args_generator=self._prepare_convert_model_args,
            output_widget=self.output_widget,
            on_finished=self._on_convert_model_finished
        )
        
        # 配置"Start Auto Convert!"按钮
        self.auto_convert_button.configure(
            script_path=os.path.join(root, "convert_core", "All_in_one.py"),
            args_generator=self._prepare_auto_convert_args,
            output_widget=self.output_widget,
            on_finished=self._on_auto_convert_finished
        )
    
    
    # debug
    # ----------------------------------------------------------------------
    # 第三行/第四行 事件处理
    
    def _on_select_video(self):
        """选择谱面视频文件"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("视频文件 (*.mkv *.mp4 *.webm *.avi)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.selected_video_path = selected_files[0]
                self.video_path_label.setText(self.selected_video_path)
    
    
    # debug
    # ----------------------------------------------------------------------
    # 参数准备方法
    
    def _prepare_auto_convert_args(self):
        """准备自动转换的参数"""
        # 验证必填参数
        if not self.selected_video_path:
            QMessageBox.warning(self, "参数错误", "请先选择谱面视频文件")
            return []
        
        video_name = self.video_name_input.text().strip()
        if not video_name:
            QMessageBox.warning(self, "参数错误", "请输入歌曲名称")
            return []
        
        bpm = self.bpm_input.text().strip()
        if not bpm:
            QMessageBox.warning(self, "参数错误", "请输入歌曲 BPM")
            return []
        
        video_start = self.video_start_input.text().strip()
        if not video_start:
            QMessageBox.warning(self, "参数错误", "请输入歌曲起始时间")
            return []
        
        video_end = self.video_end_input.text().strip()
        if not video_end:
            QMessageBox.warning(self, "参数错误", "请输入歌曲结束时间")
            return []
        
        # 使用 OpenCV 获取视频的实际 FPS
        try:
            cap = cv2.VideoCapture(self.selected_video_path)
            if not cap.isOpened():
                QMessageBox.warning(self, "视频错误", "无法打开视频文件")
                return []
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            if video_fps <= 0:
                QMessageBox.warning(self, "视频错误", "无法获取视频 FPS 信息")
                return []
            self.output_widget.append_text(f"检测到视频 FPS: {video_fps}")
        except Exception as e:
            QMessageBox.warning(self, "视频错误", f"读取视频 FPS 失败: {str(e)}")
            return []
        
        # 根据后端选择模型路径和推理设备
        backend = self.backend_combo.currentText()
        if backend == "TensorRT":
            model_paths = {
                "detect": tools.path_config.detect_engine,
                "obb": tools.path_config.obb_pt,
                "cls_break": tools.path_config.cls_break_pt,
                "cls_ex": tools.path_config.cls_ex_pt
            }
            inference_device = "0"
        else:  # DirectML
            model_paths = {
                "detect": tools.path_config.detect_onnx,
                "obb": tools.path_config.obb_onnx,
                "cls_break": tools.path_config.cls_break_onnx,
                "cls_ex": tools.path_config.cls_ex_onnx
            }
            inference_device = "NONE"
        
        # 收集所有参数
        params = {
            # standardizer 参数
            "video_path": self.selected_video_path,
            "video_mode": self.video_type_combo.currentText(),
            "start_frame": int(float(video_start) * video_fps) if float(video_start) >= 0 else -1,  # 使用实际 FPS 转换为帧数
            "end_frame": int(float(video_end) * video_fps) if float(video_end) >= 0 else -1,        # 使用实际 FPS 转换为帧数
            "target_res": int(self.target_res_input.text()),
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
            "bpm": float(bpm),
            "chart_lv": int(self.chart_lv_combo.currentText()),
            "base_denominator": int(self.base_denominator_combo.currentText())
        }
        
        # 输出日志
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始自动转换: {video_name}\n")
        self.output_widget.append_text(f"视频路径: {self.selected_video_path}")
        self.output_widget.append_text(f"BPM: {bpm}")
        self.output_widget.append_text(f"歌曲范围: {video_start}s -> {video_end}s")
        self.output_widget.append_text(f"谱面难度: {self.chart_lv_combo.currentText()}")
        self.output_widget.append_text("")
        
        # 创建临时 JSON 文件保存参数
        temp_json = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(params, temp_json, ensure_ascii=False, indent=2)
        temp_json_path = temp_json.name
        temp_json.close()
        
        # 返回参数列表
        return [temp_json_path]
    
    
    def _on_auto_convert_finished(self, exit_code):
        """自动转换完成回调"""
        if exit_code == 0:
            self.output_widget.append_text("\n✓ 自动转换完成")
            self.output_widget.append_text("=" * 20)
        else:
            self.output_widget.append_text("\n✗ 自动转换失败")
            self.output_widget.append_text("=" * 20)
    
    
    # debug
    # ----------------------------------------------------------------------
    # 第一行/第二行 检查可用性
    
    def _prepare_check_availability_args(self):
        """准备检查可用性的参数"""
        # 重置状态
        self.env_status_label.setText("运行环境待检测⚪")
        self.model_status_label.setText("模型文件待检测⚪")
        self.convert_button.hide()
        self.batch_size_label.hide()
        self.batch_size_input.hide()
        self.workspace_label.hide()
        self.workspace_input.hide()
        
        # 开始环境检查
        self.current_selected_backend = self.backend_combo.currentText()
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始检查 {self.current_selected_backend} 运行环境...\n")
        
        return [self.current_selected_backend]
    
    
    def _on_check_availability_finished(self, exit_code):
        """检查可用性完成回调"""
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
            self.convert_button.show()
            if self.current_selected_backend == "TensorRT":
                self.batch_size_label.show()
                self.batch_size_input.show()
                self.workspace_label.show()
                self.workspace_input.show()
            return
        
        # 如果连原始模型都缺失
        self.model_status_label.setText("模型文件异常🔴")
        self.output_widget.append_text("\n✗ 模型文件检查未通过，文件缺失")
        self.output_widget.append_text("=" * 20)


    def _prepare_convert_model_args(self):
        """准备转换模型的参数"""
        self.output_widget.append_text(f'\n{"=" * 20}')
        self.output_widget.append_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.output_widget.append_text(f"\n开始转换为 {self.current_selected_backend} 模型...\n")
        
        # 准备参数
        args = [self.current_selected_backend]
        # 如果是 TensorRT，额外添加 batch size 和 workspace 参数
        if self.current_selected_backend == "TensorRT":
            batch_size = self.batch_size_input.currentText()    
            workspace = self.workspace_input.currentText()
            args.append(str(batch_size))
            args.append(workspace)
        
        return args
    
    
    def _on_convert_model_finished(self, exit_code):
        """转换模型完成回调"""
        if exit_code == 0:
            self.output_widget.append_text("\n✓ 模型转换完成")
            self.output_widget.append_text("=" * 20)
            # 隐藏转换按钮和输入框
            self.convert_button.hide()
            self.batch_size_label.hide()
            self.batch_size_input.hide()
            self.workspace_label.hide()
            self.workspace_input.hide()
            # 更新模型状态
            self.model_status_label.setText("模型文件正常🟢")
        else:
            self.output_widget.append_text("\n✗ 模型转换失败")
            self.output_widget.append_text("=" * 20)







    # debug
    # ----------------------------------------------------------------------
    # 第三行 事件处理




    
    
    # debug
    # ----------------------------------------------------------------------
    # 输出区域

    def create_output_area(self):
        """创建输出区域，使用独立的 OutputTextWidget 组件"""
        # 创建输出文本组件
        self.output_widget = OutputTextWidget(
            colors=self.colors,
            max_lines=400
        )
        
        return self.output_widget
