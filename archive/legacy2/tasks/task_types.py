"""Task contracts: types and task metadata.

Keep this module dependency-light:
- No scheduler implementation
- No subprocess/ffmpeg logic
- No UI widgets

It defines the shared vocabulary used by UI, scheduler, and workers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class TaskType(str, Enum):
    AUTO_CONVERT = "auto_convert"
    MEDIA = "media"
    QUICK_ACTION = "quick_action"


class TaskStatus(str, Enum):
    PENDING = "pending"      # accepted, waiting in queue
    RUNNING = "running"      # currently executing
    ENDED = "ended"          # process ended (success/failure not distinguished)
    CANCELLED = "cancelled"  # cancelled by user


@dataclass(slots=True)
class TaskInfo:
    """A minimal task record for UI display and scheduling.

    Notes:
    - `config` is a *validated* config object (typically a Pydantic model).
    - `accepted_at` should be set when scheduler accepts the task.
    """

    task_id: str
    task_type: TaskType

    task_name: Optional[str] = None
    accepted_at: Optional[datetime] = None

    status: TaskStatus = TaskStatus.PENDING

    # Validated config object (Pydantic model). Kept as Any to avoid hard coupling.
    config: Any = None

    # Optional error message for UI timeline / diagnostics.
    # Normal successful runs should keep this empty.
    error_msg: Optional[str] = None
