import psutil
from PyQt6.QtCore import QProcess


def kill_qprocess_tree(process: QProcess) -> None:
    """Kill a QProcess and its entire process tree (children)."""
    if process.state() == QProcess.ProcessState.NotRunning:
        return

    try:
        pid = process.processId()
        if pid and pid > 0:
            kill_process_tree(int(pid))
        process.waitForFinished(500)
    except Exception:
        process.kill()
        process.waitForFinished(500)


def kill_process_tree(pid: int) -> None:
    """Kill a process and its children using psutil."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)

        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        _, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass

        parent.terminate()
        try:
            parent.wait(timeout=3)
        except psutil.TimeoutExpired:
            parent.kill()

    except psutil.NoSuchProcess:
        pass
    except Exception:
        pass
