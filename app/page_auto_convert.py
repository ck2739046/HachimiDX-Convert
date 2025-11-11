from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
                             QLabel, QComboBox, QToolTip)
from PyQt6.QtCore import pyqtSlot, Qt, QProcess
from PyQt6.QtGui import QTextCursor, QCursor
import os
import sys
import time

root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config



class AutoConvertPage(QWidget):
    
    def __init__(self, 
                 colors,                # 配色方案字典
                 folder_combobox_class, # FolderComboBox 类引用（用于创建不可编辑的选择框）
                 parent=None):          # 父 widget

        super().__init__(parent)
        
        # 保存传入的依赖
        self.colors = colors
        self.FolderComboBox = folder_combobox_class
        
        # 配置区控件
        self.backend_combo = None
        self.current_selected_backend = None
        self.env_status_label = None
        self.model_status_label = None
        self.convert_model_button = None
        self.check_availability_process = None
        
        # 输出区相关变量
        self.output_text_edit = None
        self.max_output_lines = 400  # 最大保留行数
        
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
    
    
    def create_config_area(self):
        widget = QWidget()
        widget.setFixedHeight(500)  # 固定高度
        widget.setStyleSheet(f"background-color: {self.colors['bg']};")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Label: '模型推理后端：'
        backend_label = QLabel("模型推理后端:")
        backend_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        layout.addWidget(backend_label)
        
        # ComboBox: 后端选择（不可编辑）
        self.backend_combo = QComboBox()
        self.backend_combo.setEditable(False)
        self.backend_combo.setStyleSheet(f"background-color: {self.colors['grey']}; padding-left: 8px;")
        self.backend_combo.setFixedSize(100, 25)
        self.backend_combo.addItems(["TensorRT", "DirectML"])
        layout.addWidget(self.backend_combo)
        
        # 帮助图标（圆圈中带问号）
        help_label = QLabel("❓")
        help_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        help_label.setFixedSize(20, 20)
        help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_label.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        help_label.enterEvent = lambda event: QToolTip.showText(
            QCursor.pos(),
            "TensorRT: 适用于 NVIDIA GPU\nDirectML: 适用于 AMD/Intel/Other GPU",
            help_label,
            help_label.rect()
        )
        help_label.leaveEvent = lambda event: QToolTip.hideText()
        layout.addWidget(help_label)
        
        # 按钮: "检查可用性"
        check_button = QPushButton("检查可用性")
        check_button.setStyleSheet(f"background-color: {self.colors['accent']};")
        check_button.setFixedSize(90, 25)
        check_button.clicked.connect(self.on_check_availability_clicked)
        layout.addWidget(check_button)
        
        # Label: 运行环境状态
        self.env_status_label = QLabel("运行环境待检测⚪")
        self.env_status_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        layout.addWidget(self.env_status_label)
        
        # Label: 模型状态
        self.model_status_label = QLabel("模型文件待检测⚪")
        self.model_status_label.setStyleSheet(f"color: {self.colors['text_primary']}; font-size: 13px;")
        layout.addWidget(self.model_status_label)
        
        # 按钮: "转换模型"（默认隐藏）
        self.convert_model_button = QPushButton("转换模型")
        self.convert_model_button.setStyleSheet(f"background-color: {self.colors['accent']};")
        self.convert_model_button.setFixedSize(90, 25)
        self.convert_model_button.clicked.connect(self.on_convert_model_clicked)
        self.convert_model_button.hide()  # 默认隐藏
        layout.addWidget(self.convert_model_button)
        
        layout.addStretch()  # 添加弹性空间，使控件靠左对齐
        
        return widget
    

    # ----------------------------------------------------------------------
    # 事件处理方法
    
    @pyqtSlot()
    def on_check_availability_clicked(self):
        # 重置状态
        self.env_status_label.setText("运行环境待检测⚪")
        self.model_status_label.setText("模型文件待检测⚪")
        self.convert_model_button.hide()
        # 开始环境检查
        self.current_selected_backend = self.backend_combo.currentText()
        self.append_output(f'\n{"=" * 20}')
        self.append_output(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        self.append_output(f"\n开始检查 {self.current_selected_backend} 运行环境...\n")
        # 使用 QProcess 运行子进程
        if self.check_availability_process is not None:
            self.check_availability_process.kill()
            self.check_availability_process.deleteLater()

        self.check_availability_process = QProcess(self)
        self.check_availability_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels) # 合并stdout和stderr
        # 连接信号
        self.check_availability_process.readyReadStandardOutput.connect(self.on_check_availability_process_output)
        self.check_availability_process.finished.connect(self.on_check_availability_process_finished)
        # 启动子进程
        python_exe = sys.executable
        check_device_script = os.path.join(root, "tools", "check_device.py")
        self.check_availability_process.start(python_exe, [check_device_script, self.current_selected_backend])

    
    @pyqtSlot()
    def on_check_availability_process_output(self):
        if self.check_availability_process:
            # 使用 GBK 编码读取 Windows 控制台输出
            output = self.check_availability_process.readAllStandardOutput()
            try:
                # 先尝试 GBK 编码
                text = bytes(output).decode('gbk', errors='replace')
            except:
                # 失败则使用 UTF-8
                text = bytes(output).decode('utf-8', errors='replace')
            # 按行输出
            for line in text.splitlines():
                if line.strip():
                    self.append_output(line)
    

    @pyqtSlot(int)
    def on_check_availability_process_finished(self, exit_code):
        success = (exit_code == 0)
        if success:
            self.env_status_label.setText("运行环境正常🟢")
            self.append_output("\n✓ 运行环境检查通过")
            # 继续检查模型
            self.check_models()
        else:
            self.env_status_label.setText("运行环境异常🔴")
            self.append_output("\n✗ 运行环境检查失败")
            self.append_output("=" * 20)


    def check_models(self):
        self.append_output(f"\n开始检查 {self.current_selected_backend} 模型文件...\n")

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
                self.append_output(f"✓ 找到模型文件: {os.path.basename(model_path)}")
            else:
                self.append_output(f"✗ 缺少模型文件: {os.path.basename(model_path)}")
                all_models_exist = False
        
        if all_models_exist:
            self.model_status_label.setText("模型文件正常🟢")
            self.append_output("\n✓ 模型文件检查通过")
            self.append_output("=" * 20)
            return
        
        # 如果没有找到转换后的模型，则检查原始模型文件
        self.append_output("\n未找到转换后的模型文件，开始检查原始模型文件...\n")
        raw_model_paths = [tools.path_config.detect_pt,
                           tools.path_config.obb_pt,
                           tools.path_config.cls_break_pt,
                           tools.path_config.cls_ex_pt]
        
        all_models_exist = True
        for model_path in raw_model_paths:
            if os.path.exists(model_path) and os.path.isfile(model_path):
                self.append_output(f"✓ 找到模型文件: {os.path.basename(model_path)}")
            else:
                self.append_output(f"✗ 缺少模型文件: {os.path.basename(model_path)}")
                all_models_exist = False

        if all_models_exist:
            self.model_status_label.setText("模型文件待转换🟡")
            self.append_output("\n✗ 模型文件检查未通过，需要转换格式")
            self.append_output("=" * 20)
            self.convert_model_button.show() # 显示转换按钮
            return
        
        # 如果连原始模型都缺失
        self.model_status_label.setText("模型文件异常🔴")
        self.append_output("\n✗ 模型文件检查未通过，文件缺失")
        self.append_output("=" * 20)


    @pyqtSlot()
    def on_convert_model_clicked(self):
        self.append_output("\n开始转换模型...")
        # TODO: 实现模型转换逻辑

    
    
    # debug
    # ----------------------------------------------------------------------
    # 输出区域

    def create_output_area(self):
        widget = QWidget()
        widget.setStyleSheet(f"background-color: {self.colors['grey']};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建文本输出控件
        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)  # 只读模式
        self.output_text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.colors['grey']};
                color: {self.colors['text_primary']};
                border: none;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }}
            QScrollBar:vertical {{
                background-color: {self.colors['bg']};
                width: 12px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {self.colors['text_secondary']};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {self.colors['accent']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        
        layout.addWidget(self.output_text_edit)
        
        return widget
    
    
    def append_output(self, text):
        self.output_text_edit.append(text)
        # 限制最大行数
        document = self.output_text_edit.document()
        if document.blockCount() > self.max_output_lines:
            # 删除开头的行，保留最新的 max_output_lines 行
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            # 计算需要删除的行数
            lines_to_remove = document.blockCount() - self.max_output_lines
            for _ in range(lines_to_remove):
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # 删除换行符
        
        # 自动滚动到底部
        self.output_text_edit.moveCursor(QTextCursor.MoveOperation.End)
    
    
    def clear_output(self):
        self.output_text_edit.clear()
