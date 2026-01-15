from __future__ import annotations

import win32gui
import subprocess
import psutil
import time
from typing import Optional

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

from src.core.schemas.op_result import OpResult, ok, err
from .path_manage import PathManage


class MajdataSession(QObject):
    """
    Launche/End MajdataView/MajdataEdit and provides their window handles for embedding.

    Notes:
    1. 先启动 majdataview 再启动 majdataedit
    2. 先强杀 majdataview 再通过 control file 请求 majdataedit 退出，最后超时强杀 majdataedit
    3. 通过轮询方式获取两个程序的窗口句柄（hwnd），通过信号通知调用方
    """

    # signals
    # ready -> 启动时成功找到两个窗口句柄
    # error -> 启动超时，未找到窗口句柄
    # shutdown_finished -> 通知程序退出完成
    ready = pyqtSignal(int, int)  # (majdataview_hwnd, majdataedit_hwnd)
    error = pyqtSignal(str)
    shutdown_finished = pyqtSignal()


    @property
    def majdataview_hwnd(self) -> Optional[int]:
        return self._majdataview_hwnd

    @property
    def majdataedit_hwnd(self) -> Optional[int]:
        return self._majdataedit_hwnd



    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        self._majdataview_proc: Optional[QProcess] = None
        self._majdataedit_proc: Optional[QProcess] = None
        self._majdataview_hwnd: Optional[int] = None
        self._majdataedit_hwnd: Optional[int] = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll_hwnds)
        self._poll_started_at: Optional[float] = None
        self._poll_timeout_s: float = 10.0

        self._shutdown_in_progress: bool = False
        
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(100)
        self._shutdown_timer.timeout.connect(self._poll_majdataedit_exit)
        self._shutdown_started_at: Optional[float] = None
        self._shutdown_timeout_s: float = 10.0


    

    def start(self) -> OpResult[None]:

        static_shutdown_majdata()

        majdataview_exe = PathManage.MajdataView_EXE_PATH
        majdataedit_exe = PathManage.MajdataEdit_EXE_PATH
        control_txt = PathManage.MajdataEdit_CONTROL_TXT_PATH

        # Ensure control file is clean before starting.
        try:
            if control_txt.exists():
                control_txt.unlink()
        except Exception:
            pass

        working_dir = str(majdataedit_exe.parent)

        self._majdataview_proc = QProcess(self)
        self._majdataview_proc.setWorkingDirectory(working_dir)
        self._majdataview_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._majdataview_proc.setProgram(str(majdataview_exe))

        self._majdataedit_proc = QProcess(self)
        self._majdataedit_proc.setWorkingDirectory(working_dir)
        self._majdataedit_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._majdataedit_proc.setProgram(str(majdataedit_exe))

        self._majdataedit_proc.setArguments(["--embed_mode", str(control_txt)])

        self._majdataview_proc.readyReadStandardOutput.connect(self._on_majdataview_stdout_ready)
        self._majdataedit_proc.readyReadStandardOutput.connect(self._on_majdataedit_stdout_ready)

        # majdataedit 在启动时会尝试启动 majdataview
        # 为了避免启动 2 个 majdataview
        # 先启动 majdataview，再延迟 1s 启动 majdataedit
        self._majdataview_proc.start()
        QTimer.singleShot(1000, self._majdataedit_proc.start)

        self._majdataview_hwnd = None
        self._majdataedit_hwnd = None

        # 开始轮询窗口句柄
        self._poll_started_at = time.time()
        self._poll_timer.start()

        return ok(None)






    def _on_majdataview_stdout_ready(self) -> None:

        # 过滤输出
        filters = (
            # 启动的 unity memory config 日志
            '[unitymemory] configuration parameters',
            '"memorysetup-'
        )

        if self._majdataview_proc:
            data = self._majdataview_proc.readAllStandardOutput().data().decode('utf-8', errors='replace')
            if not data: return
            new_lines = []
            for line in data.splitlines():
                if line.lower().strip().startswith(filters):
                    continue
                # 每一行都加上前缀
                new_lines.append("[MajdataView STDOUT] " + line.rstrip())
            if new_lines:
                print("\n".join(new_lines))


    def _on_majdataedit_stdout_ready(self) -> None:

        # 过滤输出
        filters = (
            # iniwave 打印
            'initwave'
        )
        
        if self._majdataedit_proc:
            data = self._majdataedit_proc.readAllStandardOutput().data().decode('utf-8', errors='replace')
            if not data: return
            new_lines = []
            for line in data.splitlines():
                if line.lower().strip().startswith(filters):
                    continue
                # 每一行都加上前缀
                new_lines.append("[MajdataEdit STDOUT] " + line.rstrip())
            if new_lines:
                print("\n".join(new_lines))






    def _poll_hwnds(self) -> None:

        if self._poll_started_at is None:
            return

        elapsed = time.time() - self._poll_started_at
        if elapsed > self._poll_timeout_s:
            self._poll_timer.stop()
            self.error.emit("MajdataSession: timed out waiting for MajdataView/MajdataEdit windows.")
            return

        if self._majdataview_hwnd is None:
            self._majdataview_hwnd = self._find_hwnd("MajdataView")
        if self._majdataedit_hwnd is None:
            self._majdataedit_hwnd = self._find_hwnd("MajdataEdit")

        if self._majdataview_hwnd is not None and self._majdataedit_hwnd is not None:
            self._poll_timer.stop()
            self.ready.emit(int(self._majdataview_hwnd), int(self._majdataedit_hwnd))


    @staticmethod
    def _find_hwnd(title_prefix: str) -> Optional[int]:

        def callback(hwnd: int, extra: list[int]) -> bool:
            name = win32gui.GetWindowText(hwnd)
            # 通过排除 '-' 来避免找到 Explorer.exe 窗口
            if name.startswith(title_prefix) and "-" not in name:
                extra.append(hwnd)
            return True

        found = []
        win32gui.EnumWindows(callback, found)
        return found[0] if found else None






    def shutdown(self) -> None:

        if self._shutdown_in_progress:
            return

        self._shutdown_in_progress = True

        # Stop polling to avoid late emits during teardown.
        self._poll_timer.stop()

        # majdataedit 退出时会弹窗提示是否要关闭 majdataview
        # 为了避免弹窗，先退出 majdataview 再退出 majdataedit

        # 1) Kill MajdataView first (force).
        proc = self._majdataview_proc
        if proc:
            proc.kill()
            proc.waitForFinished(500)

        # 2) Request MajdataEdit exit via control file.
        try:
            if self._majdataedit_proc:
                control_txt = PathManage.MajdataEdit_CONTROL_TXT_PATH
                control_txt.write_text("exit", encoding="utf-8")
        except Exception:
            pass

        # 3) 启动非阻塞轮询 MajdataEdit 退出，如果超时会强制退出
        self._shutdown_started_at = time.time()
        self._shutdown_timer.start()







    def _poll_majdataedit_exit(self) -> None:

        proc = self._majdataedit_proc

        if proc and proc.state() != QProcess.ProcessState.NotRunning:
            # 如果 majdataedit 还在运行，检查是否超时
            elapsed = time.time() - self._shutdown_started_at
            if elapsed < self._shutdown_timeout_s:
                return
            
            # 超时，强制杀掉
            proc.kill()
            proc.waitForFinished(500)


        # cleanup
        self._shutdown_timer.stop()
        self._poll_timer.stop()

        self._shutdown_timer = None
        self._poll_timer = None

        self._majdataview_proc = None
        self._majdataedit_proc = None
        self._majdataview_hwnd = None
        self._majdataedit_hwnd = None

        self._shutdown_in_progress = False

        # 发送信号，通知关闭完成
        try:
            self.shutdown_finished.emit()
        except Exception:
            pass






def _find_pids_by_process_name(target: str) -> Optional[list[int]]:
    """查根据进程名查找 PID 列表"""

    found_pids = []

    for proc in psutil.process_iter(['pid', 'name']):

        try:
            name = proc.info['name'].lower()
            pid = proc.info['pid']
            if name.startswith(target.lower()) and "-" not in name:
                found_pids.append(pid)

        except Exception:
            pass

    return found_pids if found_pids else None



def _force_kill_process_by_name(target: str) -> None:
    
    result = _find_pids_by_process_name(target)
    if result:
        print(f"Found {len(result)} '{target}' process(es): {result}, will force kill...")
        for pid in result:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], 
                                timeout=5, capture_output=True)
            except Exception:
                pass
        time.sleep(0.5)  # wait a moment



# static method
def static_shutdown_majdata() -> None:
    """
    查找所有 MajdataView 和 MajdataEdit 窗口并强制关闭
    """

    # 1) Kill MajdataView first (force)
    _force_kill_process_by_name("MajdataView")

    # 2) Then kill MajdataEdit (force)
    _force_kill_process_by_name("MajdataEdit")
