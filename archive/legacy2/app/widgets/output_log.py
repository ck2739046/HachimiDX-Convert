import re

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from app import ui_style


class OutputLogWidget(QWidget):
    """通用日志输出组件。

    Supports two usage patterns:
    1) Manual: call append_text(text)
    2) QProcess streaming (raw): connect QProcess.readyReadStandardOutput
       to handle_raw_output (recommended with MergedChannels).

    Notes:
    - Handles carriage-return (\r) progress updates by replacing the last line.
    - Strips ANSI escape sequences.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 保存的最大行数
        self.max_output_lines = 400
        # 标记最后一行是否可被替换 (用于处理 \r)
        self._is_last_line_replaceable = False
        # ANSI 转义序列的正则表达式
        self._ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        # 文本缓冲区（用于处理 \r）
        self.text_buffer = ""

        self._setup_ui()



    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)  # 只读模式
        self.text_edit.setFixedHeight(ui_style.output_log_widget_height)
        self.text_edit.setStyleSheet(
            f"""
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
            """
        )

        layout.addWidget(self.text_edit)



    def _limit_output_lines(self) -> None:
        document = self.text_edit.document()
        if document.blockCount() <= self.max_output_lines:
            return
        # 删除旧的行，仅保留最近的 400 行
        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        # 计算需要删除的行数
        lines_to_remove = document.blockCount() - self.max_output_lines
        for _ in range(lines_to_remove):
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除换行符



    def _append_output(self, text: str, replace_last: bool = False) -> None:
        """
        添加输出文本
        
        :param text: 要添加的文本
        :param replace_last: 是否替换最后一行（用于进度条更新，处理 \\r）
        """
        
        # 保存当前滚动条位置
        scrollbar = self.text_edit.verticalScrollBar()
        old_scroll_value = scrollbar.value()

        # 在添加内容前检查是否在底部
        if scrollbar.value() >= scrollbar.maximum() - 5:
            was_at_bottom = True
        else:
            was_at_bottom = False
        
        if replace_last:
            # 只在上一行是进度行时才替换
            if self._is_last_line_replaceable:
                # 替换最后一行：移动到文档末尾，选择当前行，删除并插入新文本
                cursor = self.text_edit.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                cursor.insertText(text)
                # 不要设置光标，避免触发自动滚动
            else:
                # 如果上一行不是进度行，则追加新行
                self.text_edit.append(text)
            # 标记这一行是进度行
            self._is_last_line_replaceable = True
        else:
            # 追加新行
            self.text_edit.append(text)
            # 标记这一行不是进度行
            self._is_last_line_replaceable = False
        
        # 限制最大行数
        self._limit_output_lines()
        
        # 智能滚动：仅当用户之前在底部时才自动滚动
        if was_at_bottom:
            self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
        else:
            # 如果用户不在底部，恢复原来的滚动位置
            scrollbar.setValue(old_scroll_value)



    def append_text(self, text):
        """
        手动添加文本（用于非进程输出的日志）
        安全假设：手动添加的文本不包含 \r
        
        :param text: 要添加的文本
        """
        self._append_output(text, replace_last=False)




    # ===== QProcess raw output handling =====

    def handle_raw_output(self):
        """
        处理来自 QProcess 的原始输出（槽函数）
        直接连接到 QProcess.readyReadStandardOutput 信号
        """
        # 获取发送者（QProcess）
        process = self.sender()
        if not process:
            return
        
        # 读取原始字节
        output = process.readAllStandardOutput()
        
        # 解码
        text = self._decode_output(output)
        
        # 处理 \r 和 \n
        self._process_text_buffer(text)



    def flush_buffer(self) -> None:
        """刷新缓冲区，输出剩余内容"""
        if self._text_buffer.strip():
            clean_line = self._strip_ansi(self._text_buffer)
            self._append_output(clean_line, replace_last=False)
            self._text_buffer = ""



    def _strip_ansi(self, text: str) -> str:
        """移除 ANSI 转义序列"""
        return self._ansi_escape.sub('', text)



    def _decode_output(self, byte_array) -> str:
        """解码字节流"""
        # 先尝试 UTF-8 编码（Python 脚本默认输出）
        try:
            return bytes(byte_array).decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            # 失败则尝试 GBK（Windows 控制台默认）
            try:
                return bytes(byte_array).decode('gbk', errors='strict')
            except:
                # 最后使用 UTF-8 with replace（兜底）
                return bytes(byte_array).decode('utf-8', errors='replace')



    def _process_text_buffer(self, text: str) -> None:
        """处理文本缓冲区中的 \\r 和 \\n"""
        # 将新文本添加到缓冲区
        self._text_buffer += text
        
        # 处理缓冲区中的文本
        while True:
            # 检查是否有换行符
            if '\n' in self._text_buffer:
                # 有换行符，处理到换行符为止的内容
                line, self._text_buffer = self._text_buffer.split('\n', 1)
                
                # 处理 \\r（回车符）
                if '\r' in line:
                    # 有多个 \\r 分隔的部分，只保留最后一段
                    parts = line.split('\r')
                    final_text = parts[-1]
                    
                    # 如果有多个部分，说明之前有进度更新
                    if len(parts) > 1:
                        # 先用倒数第二个部分更新进度行（如果存在）
                        if len(parts) >= 2 and parts[-2].strip():
                            clean_line = self._strip_ansi(parts[-2])
                            self._append_output(clean_line, replace_last=True)
                    
                    # 然后追加最终文本作为新行（如果非空）
                    if final_text.strip():
                        clean_line = self._strip_ansi(final_text)
                        self._append_output(clean_line, replace_last=False)
                    else:
                        # 即使是空行，也要发送以固定进度行
                        self._append_output("", replace_last=False)
                else:
                    # 没有 \\r，直接追加
                    if line.strip():
                        clean_line = self._strip_ansi(line)
                        self._append_output(clean_line, replace_last=False)
                        
            elif '\r' in self._text_buffer:
                # 有回车符但没有换行符，说明是进度更新
                parts = self._text_buffer.split('\r')
                # 只发送倒数第二个部分（如果有的话）
                # 因为最后一个部分可能不完整，需要保留在缓冲区
                if len(parts) >= 2:
                    # 取倒数第二个部分（这是最新的完整进度）
                    progress_text = parts[-2]
                    if progress_text.strip():
                        clean_line = self._strip_ansi(progress_text)
                        self._append_output(clean_line, replace_last=True)
                # 保留最后一部分在缓冲区
                self._text_buffer = parts[-1]
                break
            else:
                # 没有换行符也没有回车符，等待更多数据
                break
