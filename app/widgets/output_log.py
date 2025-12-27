from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtGui import QTextCursor
from app import ui_style

class OutputLogWidget(QWidget):
    """
    通用日志输出组件
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.max_output_lines = 400
        self._setup_ui()


    def _setup_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建文本输出控件
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)  # 只读模式
        self.text_edit.setFixedHeight(ui_style.output_log_widget_height)
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {ui_style.COLORS['grey']};
                color: {ui_style.COLORS['text_primary']};
                border: none;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }}
            QScrollBar:vertical {{
                background-color: {ui_style.COLORS['bg']};
                width: 12px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {ui_style.COLORS['text_secondary']};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {ui_style.COLORS['accent']};
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
        # 判断是否在底部（允许5个像素的误差）
        return scrollbar.value() >= scrollbar.maximum() - 5
    

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


    def append_text(self, text, replace_last=False):
        """
        添加输出文本
        
        :param text: 要添加的文本
        :param replace_last: 是否替换最后一行
        """
        # 在添加内容前检查是否在底部
        was_at_bottom = self._is_at_bottom()
        
        # 保存当前滚动条位置
        scrollbar = self.text_edit.verticalScrollBar()
        old_scroll_value = scrollbar.value()
        
        if replace_last:
            # 替换最后一行：移动到文档末尾，选择当前行，删除并插入新文本
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.insertText(text)
        else:
            # 追加新行
            self.text_edit.append(text)
        
        # 限制最大行数
        self._limit_output_lines()
        
        # 智能滚动：仅当用户之前在底部时才自动滚动
        if was_at_bottom:
            self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
        else:
            # 如果用户不在底部，恢复原来的滚动位置
            scrollbar.setValue(old_scroll_value)
