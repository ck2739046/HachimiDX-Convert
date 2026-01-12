from __future__ import annotations

import subprocess
import nanoid
from dataclasses import dataclass
from typing import Any, Optional

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

from src.core.schemas.op_result import OpResult, ok, err


@dataclass(slots=True)
class RunnerEnded:
    runner_id: str
    exit_code: Optional[int] = None
    crashed: bool = False
    cancelled: bool = False
    error_msg: Optional[str] = None
    error_raw: Any = None


class ProcessManagerSignals(QObject):
    runner_output = pyqtSignal(str, object)  # (runner_id, bytes)
    runner_ended = pyqtSignal(str, object)   # (runner_id, RunnerEnded)


class ProcessManager(QObject):
    """Centralized QProcess manager.

    Responsibilities (minimal):
    - Own all QProcess instances.
    - Assign/accept runner_id.
    - Read merged output and forward via a single signal with runner_id.
    - Emit ended signal with runner_id.

    Singleton lifecycle:
    - get_instance(): lazy singleton creation (auto-initializes)
    """

    _instance: Optional["ProcessManager"] = None

    @classmethod
    def get_instance(cls) -> "ProcessManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.signals = ProcessManagerSignals()

        self._flush_interval_ms: int = 200

        self._procs: dict[str, QProcess] = {}
        self._buffers: dict[str, bytearray] = {}
        self._cancel_requested: set[str] = set()
        self._last_error: dict[str, str] = {}

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(self._flush_interval_ms)
        self._flush_timer.timeout.connect(self._flush_all_buffers)
        self._flush_timer.start()



    # -------------------
    # Public operations
    # -------------------

    def start(self, cmd: list[str], *, runner_id: Optional[str] = None) -> OpResult[str]:
        if not isinstance(cmd, list) or not cmd:
            return err("cmd must be a non-empty list[str]")
        if not cmd[0] or not isinstance(cmd[0], str):
            return err("cmd[0] must be program path")

        rid = str(runner_id or "").strip() or self._generate_runner_id()
        if not rid:
            return err("runner_id is empty")
        if rid in self._procs:
            return err(f"runner_id already exists: {rid}")

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        program = cmd[0]
        args = cmd[1:]

        process.setProgram(program)
        process.setArguments(args)

        self._procs[rid] = process
        self._buffers[rid] = bytearray()

        process.readyReadStandardOutput.connect(lambda rid=rid: self._on_ready_read(rid))
        process.finished.connect(lambda code, status, rid=rid: self._on_finished(rid, int(code), status))
        process.errorOccurred.connect(lambda e, rid=rid: self._on_error(rid, e))

        process.start()

        return ok(rid)

    def cancel(self, runner_id: str) -> OpResult[None]:
        rid = str(runner_id).strip()
        if not rid:
            return err("runner_id is empty")

        proc = self._procs.get(rid)
        if proc is None:
            return err(f"runner_id not found: {rid}")

        self._cancel_requested.add(rid)

        try:
            if proc.state() != QProcess.ProcessState.NotRunning:
                proc.terminate()
                QTimer.singleShot(400, lambda rid=rid: self._force_kill_if_running(rid))
        except Exception as e:
            return err("Failed to cancel process", error_raw = e)

        return ok(None)

    # -------------------
    # Internal helpers
    # -------------------  

    def _generate_runner_id(self) -> str:
        return str(nanoid.generate(size=8))

    def _on_ready_read(self, runner_id: str) -> None:
        proc = self._procs.get(runner_id)
        if proc is None:
            return

        data = proc.readAllStandardOutput()
        if not data:
            return

        buf = self._buffers.get(runner_id)
        if buf is None:
            self._buffers[runner_id] = bytearray()
            buf = self._buffers[runner_id]

        buf.extend(bytes(data))

    def _flush_all_buffers(self) -> None:
        # Emit at most once per interval per runner.
        for rid, buf in list(self._buffers.items()):
            if not buf:
                continue
            payload = bytes(buf)
            buf.clear()
            try:
                self.signals.runner_output.emit(rid, payload)
            except Exception:
                # Never let UI signal handlers crash the process manager.
                pass

    def _flush_one_buffer(self, runner_id: str) -> None:
        buf = self._buffers.get(runner_id)
        if not buf:
            return
        payload = bytes(buf)
        buf.clear()
        try:
            self.signals.runner_output.emit(runner_id, payload)
        except Exception:
            pass

    def _on_finished(self, runner_id: str, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if runner_id not in self._procs:
            return

        self._flush_one_buffer(runner_id)

        cancelled = runner_id in self._cancel_requested
        crashed = exit_status == QProcess.ExitStatus.CrashExit
        error_msg = self._last_error.get(runner_id)

        ended = RunnerEnded(
            runner_id=runner_id,
            exit_code=exit_code,
            crashed=bool(crashed),
            cancelled=bool(cancelled),
            error_msg=error_msg,
        )
        self._emit_and_cleanup_ended(runner_id, ended)

    def _on_error(self, runner_id: str, err_type: QProcess.ProcessError) -> None:
        if runner_id not in self._procs:
            return

        # Record error. finished() will emit ended (usually). If the process is already not running,
        # emit ended here to avoid hanging state.
        self._last_error[runner_id] = getattr(err_type, "name", str(err_type))

        proc = self._procs.get(runner_id)
        if proc is None:
            return

        if proc.state() == QProcess.ProcessState.NotRunning:
            self._flush_one_buffer(runner_id)
            ended = RunnerEnded(
                runner_id=runner_id,
                exit_code=None,
                crashed=False,
                cancelled=(runner_id in self._cancel_requested),
                error_msg=self._last_error.get(runner_id),
            )
            self._emit_and_cleanup_ended(runner_id, ended)

    def _force_kill_if_running(self, runner_id: str) -> None:
        proc = self._procs.get(runner_id)
        if proc is None:
            return
        if proc.state() != QProcess.ProcessState.NotRunning:
            pid = int(proc.processId())
            if pid > 0:
                try:
                    # /T: tree, /F: force
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            else:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _emit_and_cleanup_ended(self, runner_id: str, ended: RunnerEnded) -> None:
        try:
            self.signals.runner_ended.emit(runner_id, ended)
        except Exception:
            pass

        proc = self._procs.pop(runner_id, None)
        self._buffers.pop(runner_id, None)
        self._cancel_requested.discard(runner_id)
        self._last_error.pop(runner_id, None)

        if proc is not None:
            try:
                proc.deleteLater()
            except Exception:
                pass
