from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtGui import QTextCursor


class OutputTextWidget(QWidget):
    """
    可复用的终端输出文本组件
    支持：
    - 普通文本追加
    - 进度行替换（处理 \r 回车符）
    - 智能滚动（仅当用户在底部时才自动滚动）
    - 最大行数限制
    """
    
    def __init__(self, colors, max_lines=400, parent=None):
        """
        初始化输出文本组件
        
        :param colors: 配色方案字典，需要包含以下键：
            - 'grey': 背景色
            - 'text_primary': 主文本颜色
            - 'bg': 滚动条背景色
            - 'text_secondary': 滚动条颜色
            - 'accent': 滚动条悬停颜色
        :param max_lines: 最大保留行数，默认 400
        :param parent: 父 widget
        """
        super().__init__(parent)
        
        self.colors = colors
        self.max_output_lines = max_lines
        self.last_line_is_progress = False  # 标记最后一行是否是进度行（可被替换）
        
        # 创建 UI
        self._setup_ui()
    
    
    def _setup_ui(self):
        """设置 UI 布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建文本输出控件
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)  # 只读模式
        self.text_edit.setStyleSheet(f"""
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
        
        layout.addWidget(self.text_edit)
    
    
    def _is_at_bottom(self):
        """检查滚动条是否在底部"""
        scrollbar = self.text_edit.verticalScrollBar()
        # 判断是否在底部（允许几个像素的误差）
        return scrollbar.value() >= scrollbar.maximum() - 5
    
    
    def append_output(self, text, replace_last=False):
        """
        添加输出文本
        
        :param text: 要添加的文本
        :param replace_last: 是否替换最后一行（用于进度条更新，处理 \r）
        """
        # 在添加内容前检查是否在底部
        was_at_bottom = self._is_at_bottom()
        
        # 保存当前滚动条位置
        scrollbar = self.text_edit.verticalScrollBar()
        old_scroll_value = scrollbar.value()
        
        if replace_last:
            # 只在上一行是进度行时才替换
            if self.last_line_is_progress:
                # 替换最后一行：移动到文档末尾，选择当前行，删除并插入新文本
                cursor = self.text_edit.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                cursor.insertText(text)
                # 不要设置光标，避免触发自动滚动
                # self.text_edit.setTextCursor(cursor)
            else:
                # 如果上一行不是进度行，则追加新行
                self.text_edit.append(text)
            # 标记这一行是进度行
            self.last_line_is_progress = True
        else:
            # 追加新行
            self.text_edit.append(text)
            # 标记这一行不是进度行
            self.last_line_is_progress = False
        
        # 限制最大行数
        self._limit_output_lines()
        
        # 智能滚动：仅当用户之前在底部时才自动滚动
        if was_at_bottom:
            self.scroll_to_bottom()
        else:
            # 如果用户不在底部，恢复原来的滚动位置
            scrollbar.setValue(old_scroll_value)
    
    
    def _limit_output_lines(self):
        """限制输出文本的最大行数"""
        document = self.text_edit.document()
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
    
    
    def scroll_to_bottom(self):
        """滚动到文本底部"""
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
    
    
    def clear(self):
        """清空输出文本"""
        self.text_edit.clear()
        self.last_line_is_progress = False
    
    
    def set_max_lines(self, max_lines):
        """设置最大行数"""
        self.max_output_lines = max_lines
    
    
    def get_text(self):
        """获取所有文本内容"""
        return self.text_edit.toPlainText()
    
    
    def set_text(self, text):
        """设置文本内容（替换所有内容）"""
        self.text_edit.setPlainText(text)
        self.last_line_is_progress = False
