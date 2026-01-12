from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import nanoid

from src.core.schemas.op_result import OpResult, ok, err
from src.core.tools import validate_pydantic
from src.core.schemas.media_model import MediaModel
from src.core.build_ffmpeg_cmd import build_ffmpeg_cmd

from ..task_scheduler import TaskType
from .. import task_scheduler_api, process_manager_api


class MediaPipeline:
    """
    Media pipeline
    """

    _is_registered: bool = False

    # -------------------
    # Initialization / registration
    # -------------------

    @classmethod
    def init(cls) -> OpResult[None]:
        """Register MEDIA task type to scheduler."""
        try:
            # Register build_cmd for scheduler dispatch.
            task_scheduler_api.register(
                TaskType.MEDIA,
                cls.build_cmd,
                concurrency = 1,
            )
            cls._is_registered = True
            return ok(None)
        
        except Exception as e:
            return err("Failed to initialize MediaPipeline", error_raw = e)


    # -------------------
    # Core building blocks
    # -------------------

    @staticmethod
    def validate(raw_data: dict[str, Any]) -> OpResult[MediaModel]:
        res = validate_pydantic(MediaModel, raw_data)
        if not res.is_ok:
            return err("MediaModel validation failed", inner=res)
        model = res.value
        if not isinstance(model, MediaModel):
            return err("Validated model has unexpected type", error_raw=type(model))
        return ok(model)


    @staticmethod
    def build_cmd(config: Any) -> OpResult[list[str]]:
        """TaskScheduler build_cmd_fn"""
        if not isinstance(config, MediaModel):
            return err("MEDIA task config must be MediaModel", error_raw=type(config))
        return build_ffmpeg_cmd(config)


    # -------------------
    # Public APIs
    # -------------------

    @classmethod
    def submit_task(cls, raw_data: dict[str, Any], task_name: str = "") -> OpResult[str]:
        """
        API (scheduler-run): validate -> submit to TaskScheduler.

        Returns:
            OpResult[str]: runner_id
        """

        if not cls._is_registered:
            return err("MediaPipeline is not initialized (not registered)")

        v = cls.validate(raw_data)
        if not v.is_ok:
            return err("Failed to validate media task input", inner=v)

        return task_scheduler_api.submit(
            TaskType.MEDIA,
            config=v.value,
            task_name=task_name,
        )


    @classmethod
    def run_now(cls, raw_data: dict[str, Any]) -> OpResult[str]:
        """
        API (direct-run): validate -> build cmd -> ProcessManager.start.

        Returns:
            OpResult[str]: runner_id
        """

        v = cls.validate(raw_data)
        if not v.is_ok:
            return err("Failed to validate media input", inner=v)

        cmd_res = cls.build_cmd(v.value)
        if not cmd_res.is_ok:
            return err("Failed to build ffmpeg command", inner=cmd_res)

        return process_manager_api.start(cmd_res.value)


    @staticmethod
    def cancel_run(runner_id: str) -> OpResult[None]:
        """Cancel a running process (direct-run) by runner_id."""
        return process_manager_api.cancel(runner_id)
