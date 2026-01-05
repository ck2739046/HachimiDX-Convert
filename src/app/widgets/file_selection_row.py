from PyQt6.QtWidgets import QPushButton, QLineEdit, QFileDialog
import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from ..ui_style import UI_Style
from .help_icon import create_help_icon

def create_file_selection_row(button_text: str, help_text: str = None, on_button_clicked_handler=None):
    """
    创建文件选择行UI组件

    Args:
        button_text: str，按钮显示文本
        help_text: str，可选，默认None，不创建help_icon
        on_button_clicked_handler: function，可选，按钮点击事件处理函数 (这个函数需要接受"选择的文件路径"作为参数)

    Returns:
        tuple: (button_widget, line_edit_widget, help_label_widget | None)
    """
    colors = UI_Style.COLORS

    # 创建文件选择按钮
    button = QPushButton(button_text)
    button.setStyleSheet(f'''
        QPushButton {{
            background-color: {colors['accent']};
        }}
        QPushButton:hover {{
            background-color: {colors['accent_hover']};
        }}
    ''')
    button.setFixedSize(120, UI_Style.element_height)

    # 创建可选的帮助图标
    help_label = None
    if help_text:
        help_label = create_help_icon(help_text)

    # 创建路径显示LineEdit
    line_edit = QLineEdit("")
    line_edit.setStyleSheet(f"color: {colors['text_secondary']}; font-size: {UI_Style.default_text_size}px;")
    line_edit.setReadOnly(True)
    line_edit.setFixedHeight(UI_Style.element_height)
    line_edit.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
    line_edit.setFrame(False)

    # 默认的文件选择处理函数
    def _default_file_select_handler():
        """默认处理: 打开文件选择界面，更新 LineEdit 显示所选择的文件路径"""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("video/audio (*.mkv *.mp4 *.webm *.avi *.mp3 *.ogg *.wav)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                selected_file_path = os.path.normpath(os.path.abspath(selected_files[0]))
                line_edit.setText(selected_file_path)

                # 如果有自定义处理函数，则调用它
                # 闭包保存自定义处理函数的引用
                if on_button_clicked_handler:
                    on_button_clicked_handler(selected_file_path)

    # 连接按钮点击事件
    if on_button_clicked_handler:
        # 有自定义处理函数时，使用默认行为 + 自定义处理
        button.clicked.connect(_default_file_select_handler)
    else:
        # 没有自定义处理函数时，只使用默认行为
        button.clicked.connect(_default_file_select_handler)

    return button, line_edit, help_label
