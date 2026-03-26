from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

from ..ui_style import UI_Style


class StatedButton(QPushButton):
    """A primary button.

    States:
      - Enabled: blue
      - Disabled: grey

    Behavior:
      - Auto-disables itself after a successful click (mouse release inside).
        Re-enabling is controlled by the caller (UI).
    """

    def __init__(self, text: str, isbig: bool = False, width: int = None, height: int = None, parent=None):
        super().__init__(text, parent)

        if width is not None:
            self.setFixedWidth(width)
        if height is not None:
            self.setFixedHeight(height)

        self._apply_style(isbig)
        self._update_cursor()


    def _apply_style(self, isbig: bool) -> None:
        colors = UI_Style.COLORS

        if not isbig:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {colors['accent']};
                }}
                QPushButton:hover {{
                    background-color: {colors['accent_hover']};
                }}
                QPushButton:disabled {{
                    background-color: {colors['grey']};
                }}
                """
            )

        if isbig:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {colors['accent']};
                    font-size: 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {colors['accent_hover']};
                }}
                QPushButton:disabled {{
                    background-color: {colors['grey']};
                }}
                """
            )
            

    def _update_cursor(self) -> None:
        if self.isEnabled():
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def setEnabled(self, enabled: bool) -> None:  # type: ignore[override]
        super().setEnabled(enabled)
        self._update_cursor()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        was_enabled = self.isEnabled()
        super().mouseReleaseEvent(event)

        if not was_enabled:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self.rect().contains(event.position().toPoint()):
            return





def create_stated_button(text: str, isbig: bool = False, width: int = None) -> StatedButton:
    """
    创建大按钮，带启用/禁用状态切换

    Args:
        text (str): 按钮文本
        isbig (bool, optional): 是否为大按钮. 默认值为 False
        width (int, optional): 按钮宽度. 默认值 None
        
        大按钮默认高度: 35
        小按钮默认高度: element_height

        大按钮默认宽度: 100
        小按钮默认宽度: 无
    
    Returns:
        StatedButton: 按钮实例

    设置按钮状态:
        setEnabled(True): 启用状态，显示为蓝色
        setEnabled(False): 禁用状态，显示为灰色
    """
    
    if isbig:
        height = 35
    else:
        height = UI_Style.element_height

    if not width and isbig:
        width = 100

    return StatedButton(text, isbig=isbig, width=width, height=height)




def create_button(text: str, width: int = None) -> QPushButton:
    """
    创建普通按钮

    Args:
        text (str): 按钮文本
        width (int, 可选): 按钮宽度. 默认 None，根据文本自适应宽度

    Returns:
        QPushButton: 按钮实例
    """
    
    button = QPushButton(text)
    button.setFixedHeight(UI_Style.element_height)
    if width is not None:
        button.setFixedWidth(width)
    colors = UI_Style.COLORS
    button.setStyleSheet(f'''
        QPushButton {{
            background-color: {colors['accent']};
        }}
        QPushButton:hover {{
            background-color: {colors['accent_hover']};
        }}
    ''')
    return button
