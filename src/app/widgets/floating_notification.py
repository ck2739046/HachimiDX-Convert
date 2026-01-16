from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from ..ui_style import UI_Style


class FloatingNotificationManager(QObject):
    """
    悬浮通知管理器（全局单例）
    负责创建、管理和定位所有悬浮通知。
    """
    
    # 单例实例引用
    _instance: Optional["FloatingNotificationManager"] = None
    
    # 配置常量
    FIXED_WIDTH: int = 300
    FIXED_HEIGHT: int = 35
    SPACING: int = 7
    MARGIN: int = 15
    AUTO_CLOSE_MS: int = 10000 # 10秒后自动关闭
    
    # 重新定位请求信号
    reposition_requested = pyqtSignal(QWidget)
    


    @classmethod
    def get_instance(cls) -> "FloatingNotificationManager":
        """获取全局单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    


    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._active_notifications: list[QWidget] = [] # 通知列表
    


    def create_notification(self, message: str, parent: QWidget) -> QWidget:

        # 创建组件
        notification = self._create_notification_widget(message, parent)
        # 添加到列表
        self._active_notifications.append(notification)
        # 显示通知
        notification.show()
        # 超时自动关闭
        notification._auto_close_timer.start(self.AUTO_CLOSE_MS)
        # 触发重新定位
        self._reposition_all_notifications(parent.window() or parent)
        
        return notification
    


    def _create_notification_widget(self, message: str, parent: any) -> QWidget:

        widget = QWidget(parent)
        
        # 公共属性
        widget._auto_close_timer = QTimer(widget)
        widget._anchor = parent
        
        # 窗口属性
        widget.setWindowFlags(Qt.WindowType.FramelessWindowHint
                              | Qt.WindowType.Tool
                              | Qt.WindowType.WindowStaysOnTopHint)
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True) # 半透明
        widget.setFixedSize(self.FIXED_WIDTH, self.FIXED_HEIGHT)

        # 布局
        outer_layout = QHBoxLayout(widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        hex_color = str(UI_Style.COLORS['task_running']).lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        a = int(255 * 0.8)  # 80% 不透明度
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.NoFrame)
        frame.setStyleSheet(f"background-color: rgba({r},{g},{b},{a}); \
                              border-radius: 10px;")

        content_layout = QHBoxLayout(frame)
        content_layout.setContentsMargins(8, 6, 8, 6)
        content_layout.setSpacing(0)
        
        message_label = QLabel(message)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                            | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        message_label.setCursor(Qt.CursorShape.IBeamCursor)
        message_label.setStyleSheet(f"color: {UI_Style.COLORS['text_primary']}; \
                                      font-size: {UI_Style.default_text_size}px; \
                                      font-weight: bold; \
                                      background: transparent; \
                                      padding-left: 2px;")
        
        close_button = QToolButton(frame)
        close_button.setText("✕")
        close_button.setFixedSize(20, 20)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                color: {UI_Style.COLORS['text_primary']};
                font-size: 15px;
                font-weight: bold;
            }}
            QToolButton:hover {{
                color: {UI_Style.COLORS['stop_hover']};
            }}""")
        
        content_layout.addWidget(message_label, 1)
        content_layout.addWidget(close_button, 0)
        outer_layout.addWidget(frame)

        # 手动关闭
        close_button.clicked.connect(lambda: self._close_notification(widget))
        # 超时自动关闭
        widget._auto_close_timer.timeout.connect(lambda: self._close_notification(widget))
        
        return widget
    

    
    def _close_notification(self, widget: QWidget) -> None:
        # 停止定时器
        widget._auto_close_timer.stop()
        # 关闭窗口
        widget.close()
        # 从活动列表移除
        if widget in self._active_notifications:
            self._active_notifications.remove(widget)
        # 触发重新定位
        self._reposition_all_notifications(widget._anchor)
    


    def _reposition_all_notifications(self, anchor: any) -> None:
        """重新定位所有通知"""
        try:
            if hasattr(anchor, 'frameGeometry'):
                anchor_geo = anchor.frameGeometry()
            else:
                anchor_geo = anchor.geometry()
        except Exception:
            return
        
        # 过滤出属于同一个锚点的通知
        same_anchor_notifications = [
            n for n in self._active_notifications 
            if n._anchor == anchor
        ]
        
        # 重新定位
        for idx, notification in enumerate(same_anchor_notifications):
            try:
                x = anchor_geo.right() - notification.width() - self.MARGIN
                y = (
                    anchor_geo.bottom()
                    - notification.height()
                    - self.MARGIN
                    - idx * (notification.height() + self.SPACING)
                )
                notification.move(x, y)
            except Exception:
                # 定位失败，尝试从活动列表中移除
                if notification in self._active_notifications:
                    self._active_notifications.remove(notification)
    




# static
def create_floating_notification(message: str, parent: QWidget) -> QWidget:
    """
    创建悬浮通知
    
    Args:
        message: 通知消息
        parent: 父窗口
        
    Returns:
        QWidget: 创建的通知窗口
    """
    manager = FloatingNotificationManager.get_instance()
    return manager.create_notification(message, parent)
