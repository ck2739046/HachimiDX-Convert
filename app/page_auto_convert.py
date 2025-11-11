from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel)
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QTextCursor
import os


class AutoConvertPage(QWidget):
    
    def __init__(self, 
                 colors,        # 配色方案字典
                 parent=None):  # 父 widget

        super().__init__(parent)
        
        # 保存传入的依赖
        self.colors = colors
        
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
        widget.setStyleSheet(f"background-color: {self.colors['bg']};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 示例：添加一些按钮
        # 第一行按钮
        button_row1 = QHBoxLayout()
        button_row1.setSpacing(10)
        
        test_button1 = QPushButton("测试按钮 1")
        test_button1.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['surface']};
                color: {self.colors['text_primary']};
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['surface_hover']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['accent']};
            }}
        """)
        test_button1.clicked.connect(self.on_test_button1_clicked)
        button_row1.addWidget(test_button1)
        
        test_button2 = QPushButton("测试按钮 2")
        test_button2.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['surface']};
                color: {self.colors['text_primary']};
                border: none;
                padding: 10px 20px;
                font-size: 14px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['surface_hover']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['accent']};
            }}
        """)
        test_button2.clicked.connect(self.on_test_button2_clicked)
        button_row1.addWidget(test_button2)
        
        button_row1.addStretch()  # 添加弹性空间，使按钮靠左对齐
        
        layout.addLayout(button_row1)
        layout.addStretch()  # 添加弹性空间，使内容靠上对齐
        
        return widget
    

    # debug
    # ----------------------------------------------------------------------
    # 事件处理方法
    
    @pyqtSlot()
    def on_test_button1_clicked(self):
        """测试按钮 1 点击事件"""
        self.append_output("测试按钮 1 被点击了")
        self.append_output("这是第二行输出")
    
    
    @pyqtSlot()
    def on_test_button2_clicked(self):
        """测试按钮 2 点击事件"""
        self.append_output("=" * 50)
        self.append_output("测试按钮 2 被点击了")
        for i in range(10):
            self.append_output(f"输出测试行 {i + 1}")
        self.append_output("=" * 50)

    
    
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
