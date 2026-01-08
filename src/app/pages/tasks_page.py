from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.services import TaskInfo, TaskScheduler, TaskStatus

from .base_output_page import BaseOutputPage
from ..ui_style import UI_Style


class TasksPage(BaseOutputPage):
    def __init__(self, parent: Optional[QWidget] = None):
        self._auto_scroll: Optional[QScrollArea] = None
        self._media_scroll: Optional[QScrollArea] = None
        self._auto_list_layout: Optional[QVBoxLayout] = None
        self._media_list_layout: Optional[QVBoxLayout] = None
        self._last_by_id: Dict[str, Tuple[Any, ...]] = {}

        super().__init__(parent)

        scheduler = TaskScheduler.get_instance()
        scheduler.signals.task_list_changed.connect(self._on_task_list_changed)

        # Best-effort initial render.
        if hasattr(scheduler, "_emit_snapshot"):
            QTimer.singleShot(0, scheduler._emit_snapshot)  # type: ignore[attr-defined]


    def setup_content(self) -> None:
        columns = QWidget()
        columns.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        columns_layout = QHBoxLayout(columns)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(UI_Style.widget_spacing)

        auto_panel, self._auto_scroll, self._auto_list_layout = self._create_queue_panel("Auto Convert")
        media_panel, self._media_scroll, self._media_list_layout = self._create_queue_panel("Media")

        columns_layout.addWidget(auto_panel, 1)
        columns_layout.addWidget(media_panel, 1)

        self.content_layout.addWidget(columns, 1)


    # -------------------
    # UI builders
    # -------------------

    def _create_queue_panel(self, title: str) -> tuple[QWidget, QScrollArea, QVBoxLayout]:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(8)

        header = QLabel(title)
        header.setStyleSheet(
            f"color: {UI_Style.COLORS['text_primary']}; font-size: {UI_Style.default_text_size + 1}px;"
        )
        panel_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; }}"
            f"QScrollBar:vertical {{ background-color: {UI_Style.COLORS['bg']}; width: 12px; border: none; }}"
            f"QScrollBar::handle:vertical {{ background-color: {UI_Style.COLORS['text_secondary']}; border-radius: 6px; min-height: 20px; }}"
            f"QScrollBar::handle:vertical:hover {{ background-color: {UI_Style.COLORS['accent']}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}"
        )

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(8)
        inner_layout.addStretch()

        scroll.setWidget(inner)
        panel_layout.addWidget(scroll, 1)

        return panel, scroll, inner_layout


    def _create_task_card(self, task: TaskInfo) -> QWidget:
        bg = self._status_bg(task.status)

        card = QFrame()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(
            "QFrame {"
            f"background-color: {bg};"
            f"color: {UI_Style.COLORS['text_primary']};"
            "border-radius: 6px;"
            "padding: 8px;"
            "}"
        )

        row = QHBoxLayout(card)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        uuid_label = QLabel(str(task.task_id))
        uuid_label.setStyleSheet(f"color: {UI_Style.COLORS['text_primary']}; font-size: 12px;")

        name_label = QLabel(task.task_name or "")
        name_label.setStyleSheet(f"color: {UI_Style.COLORS['text_primary']}; font-size: 12px;")

        accepted_label = QLabel(self._format_accepted(task.accepted_at))
        accepted_label.setStyleSheet(f"color: {UI_Style.COLORS['text_secondary']}; font-size: 11px;")

        left_layout.addWidget(uuid_label)
        left_layout.addWidget(name_label)
        left_layout.addWidget(accepted_label)

        cancel_btn = QToolButton()
        cancel_btn.setText("✕")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)  # type: ignore[name-defined]
        cancel_btn.setStyleSheet(
            "QToolButton {"
            "background: transparent;"
            f"color: {UI_Style.COLORS['text_primary']};"
            "border: none;"
            "padding: 2px 6px;"
            "}"
            "QToolButton:hover {"
            f"color: {UI_Style.COLORS['stop_hover']};"
            "}"
        )
        font = cancel_btn.font()
        font.setPointSize(16)
        cancel_btn.setFont(font)
        cancel_btn.clicked.connect(lambda _=False, tid=task.task_id: TaskScheduler.cancel(tid))

        row.addWidget(left, 1)
        row.addWidget(cancel_btn, 0)

        return card


    # -------------------
    # Data -> UI
    # -------------------

    def _on_task_list_changed(self, snapshot: object) -> None:
        if not isinstance(snapshot, dict):
            return

        auto_tasks = snapshot.get("auto_convert") or []
        media_tasks = snapshot.get("media") or []

        if not isinstance(auto_tasks, list):
            auto_tasks = []
        if not isinstance(media_tasks, list):
            media_tasks = []

        self._log_task_list_diff(auto_tasks, media_tasks)
        self._render_columns(auto_tasks, media_tasks)


    def _render_columns(self, auto_tasks: list[TaskInfo], media_tasks: list[TaskInfo]) -> None:
        if self._auto_scroll is None or self._media_scroll is None:
            return
        if self._auto_list_layout is None or self._media_list_layout is None:
            return

        auto_scroll_value = self._auto_scroll.verticalScrollBar().value()
        media_scroll_value = self._media_scroll.verticalScrollBar().value()

        self._rebuild_list(self._auto_list_layout, auto_tasks)
        self._rebuild_list(self._media_list_layout, media_tasks)

        self._auto_scroll.verticalScrollBar().setValue(auto_scroll_value)
        self._media_scroll.verticalScrollBar().setValue(media_scroll_value)


    def _rebuild_list(self, layout: QVBoxLayout, tasks: list[TaskInfo]) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for task in self._sort_tasks_for_display(tasks):
            if task.status == TaskStatus.CANCELLED:
                continue
            layout.addWidget(self._create_task_card(task))


    def _sort_tasks_for_display(self, tasks: Iterable[TaskInfo]) -> list[TaskInfo]:
        visible = [t for t in tasks if t.status != TaskStatus.CANCELLED]

        running = [t for t in visible if t.status == TaskStatus.RUNNING]
        pending = [t for t in visible if t.status == TaskStatus.PENDING]
        ended = [t for t in visible if t.status == TaskStatus.ENDED]

        def key(t: TaskInfo) -> datetime:
            return t.accepted_at or datetime.min

        running.sort(key=key, reverse=True)
        pending.sort(key=key, reverse=True)
        ended.sort(key=key, reverse=True)

        return running + pending + ended


    # -------------------
    # Diff logging
    # -------------------

    def _task_fingerprint(self, task: TaskInfo) -> Tuple[Any, ...]:
        accepted = task.accepted_at.isoformat(sep=" ", timespec="seconds") if task.accepted_at else None
        return (
            task.task_id,
            getattr(task.task_type, "value", task.task_type),
            getattr(task.status, "value", task.status),
            task.task_name or "",
            accepted,
            task.error_msg or "",
        )


    def _log_task_list_diff(self, auto_tasks: list[TaskInfo], media_tasks: list[TaskInfo]) -> None:
        new_by_id: Dict[str, Tuple[Any, ...]] = {}
        for task in list(auto_tasks) + list(media_tasks):
            try:
                new_by_id[str(task.task_id)] = self._task_fingerprint(task)
            except Exception:
                continue

        old_ids = set(self._last_by_id.keys())
        new_ids = set(new_by_id.keys())

        added = sorted(new_ids - old_ids)
        removed = sorted(old_ids - new_ids)

        for tid in added:
            fp = new_by_id[tid]
            self.output_widget.append_text(f"[+] {tid} type={fp[1]} status={fp[2]} name=\"{fp[3]}\" accepted_at={fp[4]}")

        for tid in removed:
            fp = self._last_by_id.get(tid)
            last_status = fp[2] if fp else "?"
            self.output_widget.append_text(f"[-] {tid} last_status={last_status}")

        for tid in sorted(new_ids & old_ids):
            old_fp = self._last_by_id.get(tid)
            new_fp = new_by_id.get(tid)
            if old_fp is None or new_fp is None or old_fp == new_fp:
                continue

            changes = []
            if old_fp[2] != new_fp[2]:
                changes.append(f"status {old_fp[2]} -> {new_fp[2]}")
            if old_fp[3] != new_fp[3]:
                changes.append(f"name \"{old_fp[3]}\" -> \"{new_fp[3]}\"")
            if old_fp[4] != new_fp[4]:
                changes.append(f"accepted_at {old_fp[4]} -> {new_fp[4]}")
            if old_fp[1] != new_fp[1]:
                changes.append(f"type {old_fp[1]} -> {new_fp[1]}")
            if old_fp[5] != new_fp[5] and new_fp[5]:
                changes.append(f"error {new_fp[5]}")

            if changes:
                self.output_widget.append_text(f"[*] {tid} " + "; ".join(changes))

        self._last_by_id = new_by_id


    # -------------------
    # Formatting / colors
    # -------------------

    def _format_accepted(self, accepted_at: Optional[datetime]) -> str:
        if accepted_at is None:
            return ""
        return accepted_at.isoformat(sep=" ", timespec="seconds")


    def _status_bg(self, status: TaskStatus) -> str:
        if status == TaskStatus.PENDING:
            return UI_Style.COLORS["task_pending"]
        if status == TaskStatus.RUNNING:
            return UI_Style.COLORS["task_running"]
        return UI_Style.COLORS["task_ended"]
