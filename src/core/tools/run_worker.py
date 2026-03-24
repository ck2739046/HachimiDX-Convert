import subprocess
import sys

from src.services.path_manage import PathManage




def build_cmd_head_module(module_path) -> list[str]:
    return [sys.executable, "-u", "-m", str(module_path).strip()]


def build_cmd_head_python_exe(worker_path) -> list[str]:
    # 需要传入 root_dir, 解决 worker 的间接导入问题
    return [sys.executable, "-u", str(worker_path).strip(), str(PathManage.ROOT_DIR)]


def run_worker_by_module(module_path, args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    
    cmd = build_cmd_head_module(module_path)
    worker_args = [str(item) for item in (args or [])]
    cmd.extend(worker_args)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_worker_by_python_exe(worker_path, args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    
    cmd = build_cmd_head_python_exe(worker_path)
    worker_args = [str(item) for item in (args or [])]
    cmd.extend(worker_args)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
