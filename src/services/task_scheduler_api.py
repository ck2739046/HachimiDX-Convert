from __future__ import annotations

from typing import Any, Callable, Optional

from src.core.schemas.op_result import OpResult, err
from .task_scheduler import BuildCmdFn, TaskScheduler, TaskType


def get_signals():
    """Get TaskScheduler signals for UI/subscribers."""
    return TaskScheduler.get_instance().signals


def register(task_type: TaskType,
             build_cmd_fn: BuildCmdFn,
             concurrency: int = 1) -> None:
    """Register a task type with its build_cmd function and concurrency limit."""

    if not isinstance(concurrency, int) or concurrency < 1:
        concurrency = 1

    TaskScheduler.get_instance().register(task_type, build_cmd_fn, concurrency=concurrency)


def submit(task_type: TaskType,
           config: Any,
           task_name: Optional[str] = "") -> OpResult[str]:
    """
    Submit a new task to the scheduler.

    Args:
        task_type: TaskType
        config: pydantic model
        task_name: optional task name
    """
    return TaskScheduler.get_instance().submit(task_type, config=config, task_name=task_name)


def cancel(runner_id: str) -> OpResult[None]:
    """Cancel a running task by runner_id."""

    rid = str(runner_id or "").strip()
    if not rid:
        return err("Invalid runner_id")

    return TaskScheduler.get_instance().cancel(rid)
