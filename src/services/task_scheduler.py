from __future__ import annotations

import threading
import psutil
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Deque, Dict, Optional

from PyQt6.QtCore import QObject, QProcess, QTimer

import i18n

from .task_contract import TaskInfo, TaskSignals, TaskStatus, TaskType

from .media_task_launcher import start_ffmpeg_for_media_task




# 参数列表: QPRodess, Any(Task config)
# 返回值: bool, str(error_msg)
StartFn = Callable[[QProcess, Any], tuple[bool, str]]

@dataclass(slots=True)
class _TaskRunner:
    task_type: TaskType
    start_fn: StartFn
    process: QProcess
    pending: Deque[str] = field(default_factory=deque)
    running: Optional[str] = None
    done: Deque[str] = field(default_factory=deque)


# 继承 QObject 类
# 可以使用信号槽，处理 qt 事件
class TaskScheduler(QObject):

    # -------------------
    # template
    # -------------------

    _instance: Optional["TaskScheduler"] = None

    @classmethod
    def get_instance(cls) -> "TaskScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def shutdown_instance(cls) -> None:
        if cls._instance is None:
            return
        cls._instance.cleanup()
        cls._instance = None

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._lock = threading.RLock()
        self.signals = TaskSignals()
        self._tasks: Dict[str, TaskInfo] = {}
        self._runners: Dict[TaskType, _TaskRunner] = {}
        # 注册 task runners
        self.register_runner(TaskType.MEDIA, start_ffmpeg_for_media_task)
        print("--" + i18n.t("general.notice_init_complete", name="TaskScheduler"))

    def cleanup(self) -> None:
        """cancel running processes and stop dispatch."""
        for runner in self._runners.values():
            if runner.running:
                task = self._tasks.get(runner.running)
                if task:
                    task.status = TaskStatus.CANCELLED
                    task.error_msg = None
                self._emit_snapshot()
                self._kill_qprocess_tree(runner.process)

   


    # -------------------
    # Registration / Introspection
    # -------------------

    def register_runner(self, task_type: TaskType, start_fn: StartFn) -> None:
        """Register a task type runner.

        Args:
            task_type: The task type to support.
            start_fn: Callable that starts the QProcess for a task.
                Signature: (process, validated_config) -> (ok, error_msg)
        """
        if task_type in self._runners:
            raise ValueError(f"Runner already registered for {task_type}")

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        runner = _TaskRunner(task_type=task_type, start_fn=start_fn, process=process)
        self._runners[task_type] = runner

        # lifecycle
        process.started.connect(lambda: self._on_process_started(task_type))
        process.finished.connect(lambda code, status: self._on_process_finished(task_type, int(code), status))
        process.errorOccurred.connect(lambda err: self._on_process_error(task_type, err))

        # merged output routing
        process.readyReadStandardOutput.connect(lambda: self._on_process_ready_read(task_type))


    def get_process(self, task_type: TaskType) -> Optional[QProcess]:
        runner = self._runners.get(task_type)
        return runner.process if runner else None


    def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        return self._tasks.get(task_id)







    # -------------------
    # Public API
    # -------------------

    @classmethod
    def submit(cls, task_type: TaskType, config: Any, task_name: Optional[str] = None) -> tuple[str, bool]:
        """
        Submit a task.

        Args:
            task_type: The type of task.
            config: The validated config object (Pydantic model).
            task_name: Optional task name for display.

        Returns:
            tuple(task_id, is_task_accepted)
        """
        return cls.get_instance()._submit(task_type, config, task_name)
    

    @classmethod
    def cancel(cls, task_id: str) -> None:
        """Cancel a running/non-running task from registry."""
        cls.get_instance()._cancel_or_remove(task_id)


    def _submit(self, task_type: TaskType, config: Any, task_name: Optional[str] = None) -> tuple[str, bool]:

        runner = self._runners.get(task_type)
        if runner is None:
            return "", False

        # 如果传入的 config 有 task_id 字段，就使用这个 (任务重试)
        # 否则生成一个新的 UUID
        task_id = getattr(config, "task_id", None) or str(uuid.uuid4())

        task = TaskInfo(
            task_id=str(task_id),
            task_type=task_type,
            task_name=(task_name.strip() if isinstance(task_name, str) and task_name.strip() else None),
            accepted_at=datetime.now(),
            status=TaskStatus.PENDING,
            config=config,
        )

        self._tasks[task.task_id] = task
        runner.pending.append(task.task_id)

        self._emit_snapshot()
        self._try_dispatch(task_type)

        return task.task_id, True


    def _cancel_or_remove(self, task_id: str) -> None:

        # 任务不存在
        task = self._tasks.get(task_id)
        if task is None:
            return
        
        # 这类任务的 runner 没注册
        runner = self._runners.get(task.task_type)
        if runner is None:
            self._tasks.pop(task_id, None)
            self._emit_snapshot()
            return

        # RUNNING => cancel (kill process tree)
        if runner.running == task_id:
            task.status = TaskStatus.CANCELLED
            task.error_msg = i18n.t("task_scheduler.notice_user_terminated_task", task_id=task_id)
            self._emit_snapshot()
            self._kill_qprocess_tree(runner.process)
            return

        # PENDING => remove
        if task_id in runner.pending:
            runner.pending = deque(tid for tid in runner.pending if tid != task_id)
            self._tasks.pop(task_id, None)
            self._emit_snapshot()
            return

        # DONE => remove
        if task_id in runner.done:
            runner.done = deque(tid for tid in runner.done if tid != task_id)
            self._tasks.pop(task_id, None)
            self._emit_snapshot()
            return

    


    # -------------------
    # Dispatch
    # -------------------

    def _try_dispatch(self, task_type: TaskType) -> None:
        runner = self._runners.get(task_type)
        if runner is None:
            return

        if runner.running is not None:
            return
        if not runner.pending:
            return

        next_id = runner.pending.popleft()
        if next_id not in self._tasks:
            # removed while queued; try next
            self._try_dispatch(task_type)
            return

        self._start_task(runner, next_id)


    def _start_task(self, runner: _TaskRunner, task_id: str) -> None:
        task = self._tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.error_msg = None

        runner.running = task_id
        self._emit_snapshot()

        ok, msg = runner.start_fn(runner.process, task.config)
        if ok:
            if msg:
                # 延迟 1ms 发送 msg，避免在 started 信号前发送
                QTimer.singleShot(1, lambda: self.signals.task_output.emit(task_id, bytes(msg, 'utf-8')))
            return

        # start failed synchronously
        task.status = TaskStatus.ENDED
        task.error_msg = msg
        runner.done.append(task_id)
        runner.running = None
        self._emit_snapshot()
        self._try_dispatch(runner.task_type)




    # -------------------
    # Process events
    # -------------------

    def _on_process_ready_read(self, task_type: TaskType) -> None:
        runner = self._runners.get(task_type)
        if runner is None or runner.running is None:
            # No running task to attribute output to.
            if runner is not None:
                runner.process.readAllStandardOutput()
            return

        data = runner.process.readAllStandardOutput()
        if not data:
            return

        # QByteArray -> bytes
        payload = bytes(data)
        self.signals.task_output.emit(runner.running, payload)


    def _on_process_started(self, task_type: TaskType) -> None:
        # Snapshot-driven UI; started can be used for immediate refresh.
        self._emit_snapshot()


    def _on_process_error(self, task_type: TaskType, err: QProcess.ProcessError) -> None:
        runner = self._runners.get(task_type)
        if runner is None or runner.running is None:
            self._emit_snapshot()
            return

        task_id = runner.running
        task = self._tasks.get(task_id)

        if task and task.status != TaskStatus.CANCELLED:
            task.status = TaskStatus.ENDED
            task.error_msg = f"process_error={err.name}"

        runner.done.append(task_id)
        runner.running = None
        self._emit_snapshot()
        self._try_dispatch(task_type)


    def _on_process_finished(self, task_type: TaskType, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        runner = self._runners.get(task_type)
        if runner is None or runner.running is None:
            self._emit_snapshot()
            return

        task_id = runner.running
        task = self._tasks.get(task_id)

        if task:
            if task.status != TaskStatus.CANCELLED:

                self.signals.task_output.emit(task_id, bytes(f'[{task_id}] Task finished.\n', 'utf-8'))

                task.status = TaskStatus.ENDED
                if exit_status == QProcess.ExitStatus.CrashExit:
                    task.error_msg = "crashed"
                elif exit_code != 0:
                    task.error_msg = f"exit_code={exit_code}"
                else:
                    task.error_msg = None

        runner.done.append(task_id)
        runner.running = None
        self._emit_snapshot()
        self._try_dispatch(task_type)





    # -------------------
    # Snapshot emission
    # -------------------

    def _emit_snapshot(self) -> None:
        with self._lock:
            snapshot: Dict[str, list[TaskInfo]] = {}
            for task_type, runner in self._runners.items():
                snapshot[task_type.value] = self._build_runner_snapshot(runner)
            self.signals.task_list_changed.emit(snapshot)


    def _build_runner_snapshot(self, runner: _TaskRunner) -> list[TaskInfo]:
        result: list[TaskInfo] = []

        if runner.running and runner.running in self._tasks:
            result.append(self._tasks[runner.running])

        for tid in list(runner.pending):
            task = self._tasks.get(tid)
            if task:
                result.append(task)

        for tid in list(runner.done):
            task = self._tasks.get(tid)
            if task:
                result.append(task)

        return result



    # -------------------
    # Process tree kill
    # -------------------

    def _kill_qprocess_tree(self, process: QProcess) -> None:
        if process.state() == QProcess.ProcessState.NotRunning:
            return

        try:
            pid = int(process.processId())
        except Exception:
            pid = 0

        if pid > 0 and psutil is not None:
            self._kill_process_tree(pid)
            process.waitForFinished(500)
            return

        # Fallback
        process.kill()
        process.waitForFinished(500)


    def _kill_process_tree(self, pid: int) -> None:
        if psutil is None:
            return

        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            for child in children:
                try:
                    child.terminate()
                except Exception:
                    pass

            _, alive = psutil.wait_procs(children, timeout=3)
            for child in alive:
                try:
                    child.kill()
                except Exception:
                    pass

            try:
                parent.terminate()
            except Exception:
                pass

            try:
                parent.wait(timeout=3)
            except Exception:
                try:
                    parent.kill()
                except Exception:
                    pass

        except Exception:
            pass
