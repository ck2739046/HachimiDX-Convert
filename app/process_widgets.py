"""
进程控制组件模块
包含：
- ProcessControlButton: 一体化进程控制按钮
- OutputTextWidget: 文本输出组件
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton
from PyQt6.QtCore import QProcess, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCursor
import sys
import re
import ui_helpers


class OutputTextWidget(QWidget):
    """
    文本输出组件
    职责：接收原始 QByteArray → 解析编码 → 处理 \r\n → 显示
    
    支持：
    - 普通文本追加
    - 进度行替换（处理 \r 回车符）
    - 智能滚动（仅当用户在底部时才自动滚动）
    - 最大行数限制
    """
    
    def __init__(self, max_lines=400, parent=None):
        """
        初始化输出文本组件
        
        :param max_lines: 最大保留行数，默认 400
        :param parent: 父 widget
        """
        super().__init__(parent)
        
        self.colors = ui_helpers.COLORS
        self.max_output_lines = max_lines
        self.last_line_is_progress = False  # 标记最后一行是否是进度行（可被替换）
        
        # ANSI 转义序列的正则表达式
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        # 文本缓冲区（用于处理 \r）
        self.text_buffer = ""
        
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
    
    
    def _decode_output(self, byte_array):
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
    
    
    def _strip_ansi(self, text):
        """移除 ANSI 转义序列"""
        return self.ansi_escape.sub('', text)
    
    
    def _process_text_buffer(self, text):
        """处理文本缓冲区中的 \r 和 \n"""
        # 将新文本添加到缓冲区
        self.text_buffer += text
        
        # 处理缓冲区中的文本
        while True:
            # 检查是否有换行符
            if '\n' in self.text_buffer:
                # 有换行符，处理到换行符为止的内容
                line, self.text_buffer = self.text_buffer.split('\n', 1)
                
                # 处理 \r（回车符）
                if '\r' in line:
                    # 有多个 \r 分隔的部分，只保留最后一段
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
                    # 没有 \r，直接追加
                    if line.strip():
                        clean_line = self._strip_ansi(line)
                        self._append_output(clean_line, replace_last=False)
                        
            elif '\r' in self.text_buffer:
                # 有回车符但没有换行符，说明是进度更新
                parts = self.text_buffer.split('\r')
                # 只发送倒数第二个部分（如果有的话）
                # 因为最后一个部分可能不完整，需要保留在缓冲区
                if len(parts) >= 2:
                    # 取倒数第二个部分（这是最新的完整进度）
                    progress_text = parts[-2]
                    if progress_text.strip():
                        clean_line = self._strip_ansi(progress_text)
                        self._append_output(clean_line, replace_last=True)
                # 保留最后一部分在缓冲区
                self.text_buffer = parts[-1]
                break
            else:
                # 没有换行符也没有回车符，等待更多数据
                break
    
    
    def flush_buffer(self):
        """刷新缓冲区，输出剩余内容"""
        if self.text_buffer.strip():
            clean_line = self._strip_ansi(self.text_buffer)
            self._append_output(clean_line, replace_last=False)
            self.text_buffer = ""
    
    
    def _is_at_bottom(self):
        """检查滚动条是否在底部"""
        scrollbar = self.text_edit.verticalScrollBar()
        # 判断是否在底部（允许几个像素的误差）
        return scrollbar.value() >= scrollbar.maximum() - 5
    
    
    def _append_output(self, text, replace_last=False):
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
    
    
    def append_text(self, text):
        """
        手动添加文本（用于非进程输出的日志）
        安全假设：手动添加的文本不包含 \r
        
        :param text: 要添加的文本
        """
        self._append_output(text, replace_last=False)
    
    
    def scroll_to_bottom(self):
        """滚动到文本底部"""
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
    
    
    def clear(self):
        """清空输出文本"""
        self.text_edit.clear()
        self.last_line_is_progress = False
        self.text_buffer = ""
    
    
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
        self.text_buffer = ""


class ProcessControlButton(QPushButton):
    """
    一体化进程控制按钮
    集成：按钮状态管理 + QProcess 进程运行
    
    功能：
    - 点击启动进程，按钮变为"停止"（红色）
    - 再次点击强制停止进程
    - 自动连接输出到 OutputTextWidget
    - 进程结束时自动恢复按钮状态
    - 带冷却期防止误操作
    """
    
    # 对外信号
    process_finished = pyqtSignal(int)  # exit_code
    
    def __init__(self, text, parent=None):
        """
        初始化进程控制按钮
        
        :param text: 按钮文本
        :param parent: 父 widget
        """
        super().__init__(text, parent)
        
        # 配置参数
        self._original_text = text
        self._original_font_size = None
        self._original_font_weight = None
        self._colors = ui_helpers.COLORS
        self._script_path = None
        self._args_generator = None
        self._output_widget = None
        self._on_finished_callback = None
        
        # 状态
        self._is_running = False
        self._is_transitioning = False
        self._is_user_stopping = False
        
        # 内部 QProcess（直接使用 QProcess）
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        
        # 冷却计时器
        self._cooldown_timer = QTimer(self)
        self._cooldown_timer.setSingleShot(True)
        self._cooldown_timer.timeout.connect(self._on_cooldown_complete)
        
        # 连接信号
        self.clicked.connect(self._on_clicked)
        self._process.finished.connect(self._on_process_finished)
        
        # 样式
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._colors['accent']};
            }}
            QPushButton:hover {{
                background-color: {self._colors['accent_hover']};
            }}""")
    
    
    def configure(self, script_path, args_generator=None, 
                  output_widget=None, on_finished=None):
        """
        一次性配置按钮行为
        
        :param script_path: 要运行的脚本路径（必需）
        :param args_generator: 参数生成函数，返回列表（可选）
                               例如: lambda: ["arg1", "arg2"]
        :param output_widget: OutputTextWidget 实例（可选）
                             如果提供，将自动连接进程输出
        :param on_finished: 完成回调函数（可选）
                           签名: callback(exit_code: int)
        """
        self._script_path = script_path
        self._args_generator = args_generator or (lambda: [])
        self._on_finished_callback = on_finished
        
        # 连接输出 widget（如果提供）
        if output_widget:
            self._output_widget = output_widget
            # 直接连接 QProcess 的输出信号到 widget
            self._process.readyReadStandardOutput.connect(
                output_widget.handle_raw_output
            )
    
    
    def _on_clicked(self):
        """按钮点击处理"""
        if self._is_transitioning:
            return
        
        if not self._is_running:
            self._start_process()
        else:
            self._stop_process()
    
    
    def _start_process(self):
        """启动进程（带冷却）"""
        self._is_transitioning = True
        self._is_user_stopping = False
        self.setEnabled(False)

        # 获取原始字体大小和粗细
        font = self.font()
        self._original_font_size = font.pixelSize()
        self._original_font_weight = font.weight()
        
        # 冷却后启动
        self._cooldown_timer.timeout.disconnect()
        self._cooldown_timer.timeout.connect(self._do_start_process)
        self._cooldown_timer.start(500)  # 0.5秒冷却
    
    
    def _do_start_process(self):
        """真正启动进程"""
        # 调用 args_generator，如果返回 None 则取消启动
        args = self._args_generator()
        if args is None:
            # 输出提示信息到 widget（如果绑定了的话）
            if self._output_widget:
                self._output_widget.append_text("参数准备失败，程序未启动")
            # 立即恢复按钮状态
            self._is_transitioning = False
            self.setEnabled(True)
            return
        
        self._is_running = True
        self._is_transitioning = False
        self.setEnabled(True)
        self.setText("Cancel")
        
        # 获取停止状态颜色（如果没有则使用默认红色）
        stop_color = self._colors.get('stop', '#DC3545')
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {stop_color};
                font-size: {self._original_font_size}px;
                font-weight: {self._original_font_weight};
            }}""")
        
        # 准备参数并运行
        python_exe = sys.executable
        self._process.start(python_exe, [self._script_path] + args)
    
    
    def _stop_process(self):
        """停止进程（带冷却）"""
        self._is_transitioning = True
        self._is_user_stopping = True
        self.setEnabled(False)
        
        # 输出手动退出信息到 widget（如果绑定了的话）
        if self._output_widget:
            self._output_widget.append_text("程序已终止")
        
        # 终止进程
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(500)
        
        # 冷却后恢复
        self._cooldown_timer.timeout.disconnect()
        self._cooldown_timer.timeout.connect(self._on_cooldown_complete)
        self._cooldown_timer.start(500)  # 0.5秒冷却
    
    
    def _on_process_finished(self, exit_code, exit_status):
        """进程结束处理"""
        # 处理缓冲区剩余输出
        if self._output_widget:
            self._output_widget.flush_buffer()
        
        # 如果是用户主动停止，等待冷却
        if self._is_user_stopping:
            return
        
        # 立即恢复按钮
        self._reset_button()
        
        # 调用回调
        if self._on_finished_callback:
            self._on_finished_callback(exit_code)
        
        # 发出信号
        self.process_finished.emit(exit_code)
    
    
    def _on_cooldown_complete(self):
        """冷却完成"""
        self._reset_button()
    
    
    def _reset_button(self):
        """重置按钮状态"""
        if self._cooldown_timer.isActive():
            self._cooldown_timer.stop()
        
        self._is_running = False
        self._is_transitioning = False
        self._is_user_stopping = False
        self.setEnabled(True)
        self.setText(self._original_text)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._colors['accent']};
                font-size: {self._original_font_size}px;
                font-weight: {self._original_font_weight};
            }}
            QPushButton:hover {{
                background-color: {self._colors['accent_hover']};
            }}""")
