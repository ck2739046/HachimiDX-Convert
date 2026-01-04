import os
from PyQt6.QtWidgets import QComboBox, QToolTip
from PyQt6.QtCore import Qt, QPoint, QEvent
from ..ui_style import UI_Style
from src.services import PathManage

class ToolTipComboBox(QComboBox):
    """QComboBox with immediate hover tooltip for dropdown items."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_popup_shown = False
        self._connected_view = None
        self._event_filter_installed = False
        self.setMouseTracking(True)


    def showPopup(self):
        super().showPopup()
        # 清理旧连接
        self._disconnect_view()
        # 安装事件过滤器（避免重复安装）
        view = self.view()
        if not view or not view.viewport():
            return
        if not self._event_filter_installed:
            view.viewport().installEventFilter(self)
            self._event_filter_installed = True
        # 连接新的 view
        try:
            view.entered.connect(self._on_view_entered)
            self._connected_view = view
        except (RuntimeError, TypeError):
            pass
        
        self._is_popup_shown = True


    def hidePopup(self):
        self._is_popup_shown = False
        
        # 移除事件过滤器
        try:
            view = self.view()
            if view and view.viewport():
                view.viewport().removeEventFilter(self)
                self._event_filter_installed = False
        except (RuntimeError, AttributeError):
            pass
        
        # 断开信号连接
        self._disconnect_view()
        QToolTip.hideText()
        super().hidePopup()


    def _disconnect_view(self):
        """断开 view 的信号连接"""
        if self._connected_view:
            try:
                self._connected_view.entered.disconnect(self._on_view_entered)
            except (RuntimeError, TypeError):
                pass
            self._connected_view = None


    def _on_view_entered(self, index):
        # 检查弹窗状态和索引有效性
        if not self._is_popup_shown or not index.isValid():
            QToolTip.hideText()
            return
        
        # 检查 view 和 viewport 是否存在
        view = self.view()
        if not view or not view.viewport():
            return
        
        viewport = view.viewport()
        
        # 获取项目数据
        text = index.data()
        if not text:  # 忽略空文本
            QToolTip.hideText()
            return
        
        # 计算 tooltip 显示位置（选项右侧）
        viewport_right = viewport.mapToGlobal(QPoint(viewport.width(), 0))
        item_rect = view.visualRect(index)
        item_center_y = item_rect.center().y()
        item_center_global = viewport.mapToGlobal(QPoint(0, item_center_y))
        tooltip_pos = QPoint(viewport_right.x()+2, item_center_global.y()-20)

        # 显示 tooltip（粗体文字)
        QToolTip.showText(tooltip_pos, text, viewport)
        font = QToolTip.font()
        font.setBold(True)
        QToolTip.setFont(font)


    def eventFilter(self, obj, event):
        if not self._is_popup_shown:
            return super().eventFilter(obj, event)
        # 检查 view 是否存在
        view = self.view()
        if view and view.viewport() and obj == view.viewport() and event.type() == QEvent.Type.Leave:
            QToolTip.hideText()
        
        return super().eventFilter(obj, event)


    def __del__(self):
        """销毁时确保清理资源"""
        try:
            self._disconnect_view()
            view = self.view()
            if view and view.viewport() and self._event_filter_installed:
                view.viewport().removeEventFilter(self)
        except (RuntimeError, AttributeError):
            pass




class FolderComboBox(ToolTipComboBox):
    """支持自动刷新子目录列表并恢复上次选择的下拉框"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main_output_dir = PathManage.get_main_output_dir()

    def mousePressEvent(self, event):
        current_text = self.currentText() # Save current text before clear
        self.clear()
        self.addItem("---")  # 添加占位符
        if self.main_output_dir and os.path.exists(self.main_output_dir):
            subdirs = [d for d in os.listdir(self.main_output_dir) 
                      if os.path.isdir(os.path.join(self.main_output_dir, d))]
            self.addItems(subdirs)

        # Restore previous selection if it exists
        if current_text and current_text != "---":
            index = self.findText(current_text)
            if index >= 0:
                self.setCurrentIndex(index)
            else:
                self.setCurrentText(current_text)
                
        super().mousePressEvent(event)





def create_combo_box(length, items=None, default_index=0, show_tooltip=False):
    """
    创建带悬停提示的下拉选择框
    
    Args:
        length: int，宽度（像素）
        items: list，选项列表，可选，默认None
        default_index: int，默认选中的索引，可选，默认0
        show_tooltip: bool，是否显示悬停提示，可选，默认False
    
    Returns:
        ToolTipComboBox: 配置好的下拉选择框
    """
    colors = UI_Style.COLORS
    if show_tooltip:
        combo = ToolTipComboBox()
    else:
        combo = QComboBox()

    combo.setEditable(False)
    combo.setStyleSheet(f"background-color: {colors['grey']}; padding-left: 8px;")
    combo.setFixedSize(length, UI_Style.element_height)
    
    if items:
        combo.addItems(items)
        if 0 <= default_index < len(items):
            combo.setCurrentIndex(default_index)
    
    return combo
