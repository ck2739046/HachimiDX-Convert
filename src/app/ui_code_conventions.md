# 前端 UI 与代码规范总结 (基于 src/app)

本文档基于 `run_ffmpeg.py` 和 `tasks_page.py` 的分析，总结了当前应用前端页面的 UI 设计规范和代码编写风格，以便在后续开发中保持一致性。

## 1. 基础架构与继承
- **基类选择**：所有的输出页面或具有标准框架的页面应继承自 `BaseOutputPage`（或其他基础页面类）。
- **生命周期方法**：UI 的初始化和构建应主要集中在重写的 `setup_content(self)` 方法中。对于一些需要在类实例化时即绑定的属性或信号，可以放置在 `__init__` 中，但视图布局操作应保存在 `setup_content` 内。
- **根容器**：页面的主布局应挂载到 `self.content_area` 上。

## 2. 布局与间距规范 (Layouts & Spacing)
- **主布局**：通常使用 `QVBoxLayout` 或 `QHBoxLayout`。
- **边距设置**：主布局使用 `setContentsMargins` 设置边距（常见的有 `(10, 10, 10, 10)` 或 `(0, 10, 0, 10)` 等）。
- **组件间距**：推荐统一使用 `UI_Style.widget_spacing` 保证间距的全局一致性。例如 `self.content_layout.addSpacing(UI_Style.widget_spacing)` 或 `layout.setSpacing(UI_Style.widget_spacing)`。
- **行布局辅助**：推荐使用基类提供的 `self.create_row(*widgets, add_stretch=True/False)` 来快速组织水平表单行。
- **弹性空间**：合理使用 `addStretch()` 控制元素的对齐，防止组件在窗口最大化时被异常拉伸。

## 3. 控件创建规范 (Widget Creation)
- **工厂方法优先**：不要直接实例化基础裸控件（如 `QLabel`、`QLineEdit`），应优先使用 `src.app.widgets` 中提供的工厂方法：
  - `create_label()`
  - `create_divider()`
  - `create_help_icon()`
  - `create_file_selection_row()`
  - `create_combo_box()`, `create_check_box()`, `create_line_edit()`
  - `create_stated_button()`, `create_path_display()`
- **原生控件后备**：只有当需要构建复杂的自定义容器（如 `QScrollArea`、卡片 `QFrame`）或复杂的复合布局时，才直接使用 PyQt6 原生类，并自行封装组装逻辑。

## 4. 样式与主题控制 (Style & Theming)
- **颜色管理**：UI 颜色严禁硬编码，所有的色彩属性（背景、文字、强调色、悬停色等）必须通过 `UI_Style.COLORS` 字典获取（如 `UI_Style.COLORS['bg']`, `UI_Style.COLORS['text_primary']`）。
- **样式表 (QSS) 注入**：为原生控件（如 `QFrame`, `QScrollBar`）设置 `setStyleSheet` 时，应与 Python 的 f-string 结合动态填入 `UI_Style.COLORS` 的值。

## 5. 国际化 (i18n)
- **避免硬编码字符串**：所有面向用户的显示文本（Label、Button Text、Placeholder 等）都必须通过 `i18n.t("...")` 获取。
- **命名空间划分**：i18n 键值应按模块或页面进行树形命名，如 `"app.media_subpages.run_ffmpeg.ui_submit_button"`。

## 6. 事件与信号处理 (Signals & Slots)
- **槽函数命名规范**：UI 组件对应的事件处理函数通常命名为 `on_<widget_name>_clicked` 或 `_on_<event>_changed`。
- **与后端/服务解耦**：当发生服务级的更新（流、队列变化）时，UI 层应只负责监听，并根据后端传回的 snapshot (如 `dict`) 重绘页面。相关操作可连接至全局暴露出的信号：如 `process_manager_api.get_signals().x` 或 `task_scheduler_api.get_signals().x`。
- **防止阻塞主线程**：耗时任务不直接在点击事件中执行，而应将其组装并打包派发给 Scheduler / API 等后台服务处理。

## 7. 代码组织与变量命名 (Code Organization)
- **方法级别拆分**：如果页面的控件多且复杂，需将其划分为多个 `init_..._widgets()` 方法再统一添加到布局。
- **变量预声明**：页面用到的公共或跨方法访问的控件引用，通常需要先置为 `None`，然后再实例化创建。
- **私有方法约束**：仅在内部供逻辑流使用的方法（如 `_create_task_card`、`_rebuild_list`）应该使用前导下划线标明私有。
- **代码区块划分**：在过长的文件中，使用明显的注释分隔线（如 `# ------------------- UI builders -------------------`）划分不同职责的代码块。