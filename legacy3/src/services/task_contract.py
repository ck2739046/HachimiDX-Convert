from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal


class TaskType(str, Enum):
    AUTO_CONVERT = "auto_convert"
    MEDIA = "media"


class MediaType(str, Enum):
    AUDIO = "audio"
    VIDEO_WITH_AUDIO = "video_with_audio"
    VIDEO_WITHOUT_AUDIO = "video_without_audio"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    PENDING = "pending"      # accepted, waiting in queue
    RUNNING = "running"      # currently executing
    ENDED = "ended"          # process ended (success/failure not distinguished)
    CANCELLED = "cancelled"  # cancelled by user


@dataclass(slots=True)
class TaskInfo:

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


class TaskSignals(QObject):

    # Fired whenever any task list changes. Payload is a FULL snapshot for UI rendering.
    # Payload shape (dict): { "media": [TaskInfo, ...], "auto_convert": [TaskInfo, ...], ... }
    task_list_changed = pyqtSignal(object)

    # Fired when the currently RUNNING task produces output.
    # Output is merged (stdout/stderr), as raw bytes.
    task_output = pyqtSignal(str, object)
