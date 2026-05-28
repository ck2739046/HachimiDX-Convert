import sys
import time
import subprocess
from typing import Optional

import psutil



def _find_pids_by_process_name(target: str) -> Optional[list[int]]:
    """查根据进程名查找 PID 列表"""

    found_pids = []

    for proc in psutil.process_iter(['pid', 'name']):

        try:
            name = proc.info['name']
            if name and name == target:
                pid = proc.info['pid']
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



def shutdown_majdata() -> None:
    """
    查找所有 MajdataView 和 MajdataEdit 窗口并强制关闭
    """

    # 1) Kill MajdataView first (force)
    _force_kill_process_by_name("MajdataView.exe")

    # 2) Then kill MajdataEdit (force)
    _force_kill_process_by_name("MajdataEdit.exe")









def _parent_alive(pid: int, expected_create_time: float) -> bool:
    """检测父进程是否存活"""
    try:
        proc = psutil.Process(pid)
        return proc.create_time() == expected_create_time
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def main() -> int:
    parent_pid = int(sys.argv[1])

    # 记录父进程创建时间，防止 PID 被回收后又被分配给其他进程
    # 只有创建时间匹配的进程才被认为是原父进程
    try:
        parent_create_time = psutil.Process(parent_pid).create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        print(f"[watchdog] Parent PID {parent_pid} not found at startup, exiting.")
        return 0
    except Exception as e:
        print(f"[watchdog] Error checking parent process at startup: {e}, exiting.")
        return 0

    print(f"[watchdog] Started, watching parent PID {parent_pid}")

    while True:
        if not _parent_alive(parent_pid, parent_create_time):
            print(f"[watchdog] Parent PID {parent_pid} is gone, cleaning up...")
            shutdown_majdata()
            print("[watchdog] Cleanup done, exiting.")
            return 0
        time.sleep(0.1)


if __name__ == "__main__":
    sys.exit(main())
