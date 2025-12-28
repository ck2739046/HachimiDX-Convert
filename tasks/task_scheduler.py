"""TaskScheduler: dual-queue scheduling (auto_convert + media).

Key constraints (per latest requirements):
- Use QProcess only (no QThread, no subprocess module).
- TaskSignals exposes only:
    - task_accepted(TaskInfo)
    - task_list_changed(snapshot)
- Any change (accepted/started/ended/cancelled/removed) emits task_list_changed,
    and each emission contains a FULL snapshot for UI to render.
- TaskStatus does not distinguish finished/failed: use ENDED.
- User clicking "x" on a RUNNING task marks it CANCELLED.
- Kill the whole process tree on cancel (psutil), similar to legacy process_widgets.
- Scheduler does NOT parse stdout/stderr; UI should connect QProcess output directly
    to OutputLogWidget.handle_raw_output.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Deque, Dict, Optional

import psutil
from PyQt6.QtCore import QObject, QProcess

from core.ffmpeg_utils.ffmpeg_launcher import start_ffmpeg_for_media_task
from tasks.task_configs import BaseTaskConfig
from tasks.task_signals import TaskSignals
from tasks.task_types import TaskInfo, TaskStatus, TaskType
from tasks.qprocess_utils import kill_qprocess_tree


class TaskScheduler(QObject):
    """Global scheduler with two independent queues."""

    _instance: Optional["TaskScheduler"] = None

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self.signals = TaskSignals()

        # task registry
        self._tasks: Dict[str, TaskInfo] = {}

        # media queue
        self._media_task_pending: Deque[str] = deque()
        self._media_task_running: Optional[str] = None
        self._media_task_done: Deque[str] = deque()

        # auto_convert queue
        self._auto_convert_task_pending: Deque[str] = deque()
        self._auto_convert_task_running: Optional[str] = None
        self._auto_convert_task_done: Deque[str] = deque()

        # processes: one per queue to allow parallelism across queues
        self._media_process = QProcess(self)
        self._media_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        self._auto_convert_process = QProcess(self)
        self._auto_convert_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        # Connect lifecycle
        self._media_process.started.connect(lambda: self._on_process_started(TaskType.MEDIA))
        self._media_process.finished.connect(
            lambda code, status: self._on_process_finished(TaskType.MEDIA, int(code), status)
        )
        self._media_process.errorOccurred.connect(lambda err: self._on_process_error(TaskType.MEDIA, err))

        self._auto_convert_process.started.connect(lambda: self._on_process_started(TaskType.AUTO_CONVERT))
        self._auto_convert_process.finished.connect(
            lambda code, status: self._on_process_finished(TaskType.AUTO_CONVERT, int(code), status)
        )
        self._auto_convert_process.errorOccurred.connect(
            lambda err: self._on_process_error(TaskType.AUTO_CONVERT, err)
        )

    # ===== Process exposure (for OutputLogWidget binding) =====

    def get_media_process(self) -> QProcess:
        return self._media_process

    def get_auto_convert_process(self) -> QProcess:
        return self._auto_convert_process

    # ===== Snapshot =====

    def _emit_task_list_changed(self) -> None:
        self.signals.task_list_changed.emit(
            {
                "auto_convert": self._build_column_snapshot(TaskType.AUTO_CONVERT),
                "media": self._build_column_snapshot(TaskType.MEDIA),
            }
        )

    def _build_column_snapshot(self, task_type: TaskType) -> list[TaskInfo]:
        if task_type == TaskType.MEDIA:
            running = self._media_task_running
            pending = list(self._media_task_pending)
            done = list(self._media_task_done)
        else:
            running = self._auto_convert_task_running
            pending = list(self._auto_convert_task_pending)
            done = list(self._auto_convert_task_done)

        result: list[TaskInfo] = []
        if running and running in self._tasks:
            result.append(self._tasks[running])
        for tid in pending:
            if tid in self._tasks:
                result.append(self._tasks[tid])
        for tid in done:
            if tid in self._tasks:
                result.append(self._tasks[tid])
        return result

    @classmethod
    def instance(cls) -> "TaskScheduler":
        if cls._instance is None:
            cls._instance = TaskScheduler()
        return cls._instance

    @classmethod
    def shutdown_instance(cls) -> None:
        """Shutdown scheduler if it was created."""
        if cls._instance is not None:
            cls._instance.shutdown()

    def shutdown(self) -> None:
        """Best-effort shutdown: cancel running processes (kill tree)."""
        try:
            if self._media_task_running:
                self.cancel_or_remove(self._media_task_running)
        except Exception:
            pass
        try:
            if self._auto_convert_task_running:
                self.cancel_or_remove(self._auto_convert_task_running)
        except Exception:
            pass

    def submit_media_task(self, config: BaseTaskConfig, task_name: Optional[str] = None) -> str:
        """Accept a media task into queue and attempt dispatch."""
        task_id = getattr(config, "task_id")

        task = TaskInfo(
            task_id=task_id,
            task_type=TaskType.MEDIA,
            task_name=(task_name.strip() if isinstance(task_name, str) and task_name.strip() else None),
            accepted_at=datetime.now(),
            status=TaskStatus.PENDING,
            config=config,
        )

        self._tasks[task_id] = task
        self._media_task_pending.append(task_id)

        self.signals.task_accepted.emit(task)
        self._emit_task_list_changed()

        self._try_dispatch(TaskType.MEDIA)
        return task_id

    def submit_auto_convert_task(self, config: BaseTaskConfig, task_name: Optional[str] = None) -> str:
        task_id = getattr(config, "task_id")

        task = TaskInfo(
            task_id=task_id,
            task_type=TaskType.AUTO_CONVERT,
            task_name=(task_name.strip() if isinstance(task_name, str) and task_name.strip() else None),
            accepted_at=datetime.now(),
            status=TaskStatus.PENDING,
            config=config,
        )

        self._tasks[task_id] = task
        self._auto_convert_task_pending.append(task_id)

        self.signals.task_accepted.emit(task)
        self._emit_task_list_changed()

        self._try_dispatch(TaskType.AUTO_CONVERT)
        return task_id

    # ===== Cancel / remove =====

    def cancel_or_remove(self, task_id: str) -> bool:
        """"x" behavior: RUNNING => cancel (kill process tree), else remove."""

        if task_id == self._media_task_running:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.CANCELLED
            self._emit_task_list_changed()
            kill_qprocess_tree(self._media_process)
            return True

        if task_id == self._auto_convert_task_running:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.CANCELLED
            self._emit_task_list_changed()
            kill_qprocess_tree(self._auto_convert_process)
            return True

        if task_id in self._media_task_pending:
            self._media_task_pending = deque([tid for tid in self._media_task_pending if tid != task_id])
            self._tasks.pop(task_id, None)
            self._emit_task_list_changed()
            return True

        if task_id in self._auto_convert_task_pending:
            self._auto_convert_task_pending = deque(
                [tid for tid in self._auto_convert_task_pending if tid != task_id]
            )
            self._tasks.pop(task_id, None)
            self._emit_task_list_changed()
            return True

        if task_id in self._tasks:
            self._media_task_done = deque([tid for tid in self._media_task_done if tid != task_id])
            self._auto_convert_task_done = deque(
                [tid for tid in self._auto_convert_task_done if tid != task_id]
            )
            self._tasks.pop(task_id, None)
            self._emit_task_list_changed()
            return True

        return False

    # ===== Dispatch =====

    def _try_dispatch(self, task_type: TaskType) -> None:
        if task_type == TaskType.MEDIA:
            if self._media_task_running is not None or not self._media_task_pending:
                return
            next_id = self._media_task_pending.popleft()
            if next_id not in self._tasks:
                self._try_dispatch(TaskType.MEDIA)
                return
            self._start_task(TaskType.MEDIA, next_id)
            return

        if task_type == TaskType.AUTO_CONVERT:
            if self._auto_convert_task_running is not None or not self._auto_convert_task_pending:
                return
            next_id = self._auto_convert_task_pending.popleft()
            if next_id not in self._tasks:
                self._try_dispatch(TaskType.AUTO_CONVERT)
                return
            self._start_task(TaskType.AUTO_CONVERT, next_id)
            return

    def _start_task(self, task_type: TaskType, task_id: str) -> None:
        task = self._tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.error_msg = None

        if task_type == TaskType.MEDIA:
            self._media_task_running = task_id
            self._emit_task_list_changed()
            self._start_media_process(task)
            return

        # AUTO_CONVERT placeholder (external process not implemented yet)
        self._auto_convert_task_running = task_id
        self._emit_task_list_changed()
        task.status = TaskStatus.ENDED
        task.error_msg = "auto_convert not implemented"
        self._auto_convert_task_done.append(task_id)
        self._auto_convert_task_running = None
        self._emit_task_list_changed()
        self._try_dispatch(TaskType.AUTO_CONVERT)

    def _start_media_process(self, task: TaskInfo) -> None:
        ok, msg = start_ffmpeg_for_media_task(self._media_process, task.config)
        if not ok:
            task.status = TaskStatus.ENDED
            task.error_msg = msg
            self._media_task_done.append(task.task_id)
            self._media_task_running = None
            self._emit_task_list_changed()
            self._try_dispatch(TaskType.MEDIA)

    # ===== Process lifecycle =====

    def _on_process_started(self, task_type: TaskType) -> None:
        self._emit_task_list_changed()

    def _on_process_error(self, task_type: TaskType, err: QProcess.ProcessError) -> None:
        if task_type == TaskType.MEDIA:
            task_id = self._media_task_running
            if not task_id:
                self._emit_task_list_changed()
                return
            task = self._tasks.get(task_id)
            if task and task.status != TaskStatus.CANCELLED:
                task.status = TaskStatus.ENDED
                task.error_msg = f"process_error={err.name}"
            self._media_task_done.append(task_id)
            self._media_task_running = None
            self._emit_task_list_changed()
            self._try_dispatch(TaskType.MEDIA)
            return

        if task_type == TaskType.AUTO_CONVERT:
            task_id = self._auto_convert_task_running
            if not task_id:
                self._emit_task_list_changed()
                return
            task = self._tasks.get(task_id)
            if task and task.status != TaskStatus.CANCELLED:
                task.status = TaskStatus.ENDED
                task.error_msg = f"process_error={err.name}"
            self._auto_convert_task_done.append(task_id)
            self._auto_convert_task_running = None
            self._emit_task_list_changed()
            self._try_dispatch(TaskType.AUTO_CONVERT)

    def _on_process_finished(
        self, task_type: TaskType, exit_code: int, exit_status: QProcess.ExitStatus
    ) -> None:
        if task_type == TaskType.MEDIA:
            task_id = self._media_task_running
            if not task_id:
                self._emit_task_list_changed()
                return
            task = self._tasks.get(task_id)
            if task and task.status != TaskStatus.CANCELLED:
                task.status = TaskStatus.ENDED
                if exit_status == QProcess.ExitStatus.CrashExit:
                    task.error_msg = "crashed"
                elif exit_code != 0:
                    task.error_msg = f"exit_code={exit_code}"
                else:
                    task.error_msg = None
            self._media_task_done.append(task_id)
            self._media_task_running = None
            self._emit_task_list_changed()
            self._try_dispatch(TaskType.MEDIA)
            return

        if task_type == TaskType.AUTO_CONVERT:
            task_id = self._auto_convert_task_running
            if not task_id:
                self._emit_task_list_changed()
                return
            task = self._tasks.get(task_id)
            if task and task.status != TaskStatus.CANCELLED:
                task.status = TaskStatus.ENDED
                if exit_status == QProcess.ExitStatus.CrashExit:
                    task.error_msg = "crashed"
                elif exit_code != 0:
                    task.error_msg = f"exit_code={exit_code}"
                else:
                    task.error_msg = None
            self._auto_convert_task_done.append(task_id)
            self._auto_convert_task_running = None
            self._emit_task_list_changed()
            self._try_dispatch(TaskType.AUTO_CONVERT)

    # ===== Process tree kill (psutil) =====
