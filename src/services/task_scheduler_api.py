from __future__ import annotations

from typing import Any, Callable, Optional

from src.core.schemas.op_result import OpResult
from src.services.task_scheduler import BuildCmdFn, TaskScheduler, TaskType


def get_signals():
    return TaskScheduler.get_instance().signals


def register(task_type: TaskType, build_cmd_fn: BuildCmdFn, *, concurrency: int = 1) -> None:
    TaskScheduler.get_instance().register(task_type, build_cmd_fn, concurrency=concurrency)


def submit(task_type: TaskType, *, runner_id: str, config: Any, task_name: str = "") -> OpResult[str]:
    return TaskScheduler.get_instance().submit(task_type, runner_id=runner_id, config=config, task_name=task_name)


def cancel(runner_id: str) -> None:
    TaskScheduler.get_instance().cancel(runner_id)
