"""Qt signals contract for task events.

This defines the signals that UI can listen to.
Scheduler/workers will emit these signals.

- UI only needs to know when a task is accepted (for submit button feedback).
- UI rebuilds Tasks page from a single queue snapshot signal.

All other internal runner events (started/finished/updated) are intentionally
not exposed here.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from .task_types import TaskInfo


class TaskSignals(QObject):
    """Signals emitted by scheduler/workers.

    UI usage examples:
    - submit button listens to `task_accepted`
    - tasks page listens to `task_list_changed` and redraws from snapshot
    """

    # Fired when a task is accepted into queue (PENDING).
    task_accepted = pyqtSignal(TaskInfo)

    # Fired on ANY task change. Payload is a snapshot of all tasks for UI rendering.
    # Payload shape (dict):
    #   {
    #     "auto_convert": [TaskInfo, ...],
    #     "media": [TaskInfo, ...],
    #   }
    task_list_changed = pyqtSignal(object)
