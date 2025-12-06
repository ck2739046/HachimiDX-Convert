"""
UI Helper Functions and Shared Resources
提供统一的UI组件创建函数和配色方案
"""

from PyQt6.QtWidgets import QLabel, QComboBox, QLineEdit, QCheckBox, QWidget, QHBoxLayout, QFrame, QStyle, QStyleOptionButton
from PyQt6.QtCore import Qt, QRectF, QEvent, QPoint
from PyQt6.QtGui import QCursor, QPainter, QColor, QPen, QPainterPath, QFont
from PyQt6.QtWidgets import QToolTip


# 配色方案
COLORS = {
    'bg': "#303030",
    'text_primary': "#E8E8E8",
    'text_secondary': "#8D99AE",

    'grey': "#454545",
    'grey_hover': "#505050",

    'surface': "#17203D",
    'surface_hover': "#212C47",
    
    'accent': "#3A86FF",
    'accent_hover': "#4794FF",

    'stop': "#DC3545",
    'stop_hover': "#E04A5A",
}

def create_help_icon(text):
    """
    创建帮助图标（ⓘ），鼠标悬停时显示提示文本
    
    Args:
        text: 提示文本内容
    
    Returns:
        QLabel: 配置好的帮助图标widget
    """

    def enter_event():
        # show text
        # 必须先显示文字再设置样式，避免样式被覆盖
        QToolTip.showText(QCursor.pos(), text, help_label, help_label.rect())
        # set palette
        palette = QToolTip.palette()
        palette.setColor(palette.ColorRole.Window, QColor(COLORS['grey']))
        palette.setColor(palette.ColorRole.WindowText, QColor(COLORS['text_secondary']))
        QToolTip.setPalette(palette)
        # set font
        font = QToolTip.font()
        font.setBold(True)
        QToolTip.setFont(font)

    help_label = QLabel("ⓘ")
    help_label.setStyleSheet("font-size: 13px;")
    help_label.setFixedSize(20, 20)
    help_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    help_label.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
    help_label.enterEvent = lambda event: enter_event()
    help_label.leaveEvent = lambda event: QToolTip.hideText()
    return help_label


def create_combo_box(length, items=None, default_index=0, show_tooltip=False):
    """
    创建带悬停提示的下拉选择框
    
    Args:
        length: 宽度（像素）
        items: 选项列表，默认为None
        default_index: 默认选中的索引，默认为0
        show_tooltip: 是否显示悬停提示，默认为False
    
    Returns:
        ToolTipComboBox: 配置好的下拉选择框
    """
    if show_tooltip:
        combo = ToolTipComboBox()
    else:
        combo = QComboBox()

    combo.setEditable(False)
    combo.setStyleSheet(f"background-color: {COLORS['grey']}; padding-left: 8px;")
    combo.setFixedSize(length, 25)
    
    if items:
        combo.addItems(items)
        if 0 <= default_index < len(items):
            combo.setCurrentIndex(default_index)
    
    return combo


def create_label(text):
    """
    创建文本标签
    
    Args:
        text: 标签文本内容
    
    Returns:
        QLabel: 配置好的文本标签
    """
    label = QLabel(text)
    label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px;")
    return label


def create_line_edit(length=None, validator=None, placeholder=None):
    """
    创建文本输入框
    
    Args:
        length: 宽度（像素），默认为None
        validator: 输入验证器（QValidator），默认为None
        placeholder: 占位符文本，默认为None
    
    Returns:
        QLineEdit: 配置好的文本输入框
    """
    line_edit = QLineEdit()
    line_edit.setStyleSheet(f"background-color: {COLORS['grey']}; padding-left: 8px;")
    if length:
        line_edit.setFixedSize(length, 25)
    else:
        line_edit.setFixedHeight(25)

    if validator:
        line_edit.setValidator(validator)
    
    if placeholder:
        line_edit.setPlaceholderText(placeholder)
    
    return line_edit


def create_check_box():
    """
    创建复选框
    
    Returns:
        QCheckBox: 配置好的复选框
    """
    checkbox = SimpleCheckBox(colors=COLORS, size=20, border_width=1)
    return checkbox


def create_divider(text, up_margin=5, down_margin=5, width=None):
    """
    创建分隔线

    Args:
        text: 分隔栏文本内容
        up_margin: 分隔栏上边距（像素），默认为5
        down_margin: 分隔栏下边距（像素），默认为5
        width: 分隔栏总宽度（像素），默认为None
    
    Returns:
        QWidget: 包含分隔线的容器widget
    """
    divider_container = QWidget()
    divider_layout = QHBoxLayout(divider_container)
    
    divider_layout.setContentsMargins(0, up_margin, 0, down_margin)
    divider_layout.setSpacing(0)

    if text:
        line_left = QFrame()
        line_left.setFrameShape(QFrame.Shape.HLine)
        line_left.setFixedSize(18, 20) # 固定宽度18像素
        line_left.setStyleSheet(f"color: {COLORS['grey']};")
        divider_layout.addWidget(line_left)

        label = QLabel(text)
        label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if not width:
            length = len(text)*13 + 8 # 一个中文汉字是13px，外加8px的边距
            label.setFixedSize(length, 20)
        else:
            label.setFixedSize(width, 20)

        divider_layout.addWidget(label)

        line_right = QFrame()
        line_right.setFrameShape(QFrame.Shape.HLine)
        line_right.setFixedHeight(20) # 无固定宽度
        line_right.setStyleSheet(f"color: {COLORS['grey']};")
        divider_layout.addWidget(line_right)

        #divider_layout.addStretch()  # 添加弹性空间

    return divider_container








# debug
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











# debug
class SimpleCheckBox(QCheckBox):


    def __init__(self, colors, size, border_width, parent=None):
        super().__init__(parent)
        
        # 默认颜色配置（转换为QColor对象）
        self.checked_color = QColor(colors['accent'])
        self.checked_hover_color = QColor(colors['accent_hover'])
        self.unchecked_color = QColor(colors['grey'])
        self.unchecked_hover_color = QColor(colors['grey_hover'])
        self.border_color = QColor(colors['text_secondary'])

        self.size = size
        self.border_width = border_width
        self.is_hover = False
        self.setFixedSize(size, size)
        
        # 设置样式表控制指示器尺寸
        self.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: {self.size}px;
                height: {self.size}px;
            }}
        """)


    def enterEvent(self, event):
        """鼠标进入"""
        self.is_hover = True
        self.update()
        super().enterEvent(event)


    def leaveEvent(self, event):
        """鼠标离开"""
        self.is_hover = False
        self.update()
        super().leaveEvent(event)


    def paintEvent(self, event):
        """自定义绘制"""
        # 先绘制文本
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 获取指示器区域
        opt = QStyleOptionButton()
        opt.initFrom(self)
        indicator_rect = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opt, self)

        # 缩小 indicator，给边框留出位置
        rect = QRectF(indicator_rect).adjusted(self.border_width, self.border_width, -self.border_width, -self.border_width)
        
        # 确定背景颜色
        if self.isChecked():
            bg_color = self.checked_hover_color if self.is_hover else self.checked_color
        else:
            bg_color = self.unchecked_hover_color if self.is_hover else self.unchecked_color
        
        # 绘制圆角矩形 + 1px边框
        painter.setPen(QPen(self.border_color, self.border_width))
        painter.setBrush(bg_color)
        painter.drawRoundedRect(rect, 4, 4)
        
        # 绘制对勾
        if self.isChecked():
            path = QPainterPath()
            w, h = rect.width(), rect.height()
            
            # 对勾路径
            path.moveTo(rect.left() + w * 0.25, rect.top() + h * 0.5)
            path.lineTo(rect.left() + w * 0.45, rect.top() + h * 0.7)
            path.lineTo(rect.left() + w * 0.75, rect.top() + h * 0.3)
            
            pen = QPen(QColor("white"), 1.5, Qt.PenStyle.SolidLine, 
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)
