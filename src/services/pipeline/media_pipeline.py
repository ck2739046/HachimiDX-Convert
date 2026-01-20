from __future__ import annotations

from typing import Any, Optional

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
        """Register MEDIA task type to scheduler (concurrency only)."""
        try:
            task_scheduler_api.register(
                TaskType.MEDIA,
                concurrency = 1,
            )
            cls._is_registered = True
            return ok()
        
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
    def submit_task(cls, raw_data: dict[str, Any], task_name: str = "") -> OpResult[tuple[str, list[str]]]:
        """
        API (scheduler-run): validate -> build cmd -> submit_task to TaskScheduler.

        Returns:
            OpResult[]: tuple(runner_id, command list)
        """

        if not cls._is_registered:
            return err("MediaPipeline is not initialized (not registered)")

        v_res = cls.validate(raw_data)
        if not v_res.is_ok:
            return err("Failed to validate media task input", inner=v_res)

        cmd_res = cls.build_cmd(v_res.value)
        if not cmd_res.is_ok:
            return err("Failed to build ffmpeg command", inner=cmd_res)

        rid_res = task_scheduler_api.submit_task(
            TaskType.MEDIA,
            cmd_res.value,
            task_name=task_name,
        )
        if not rid_res.is_ok:
            return err("Failed to submit task to scheduler", inner=rid_res)

        return ok((rid_res.value, cmd_res.value))


    @classmethod
    def run_now(cls, raw_data: dict[str, Any], runner_id: Optional[str]) -> OpResult[tuple[str, list[str]]]:
        """
        API (direct-run): validate -> build cmd -> ProcessManager.start.

        Returns:
            OpResult[]: tuple(runner_id, command list)
        """

        v_res = cls.validate(raw_data)
        if not v_res.is_ok:
            return err("Failed to validate media input", inner=v_res)

        cmd_res = cls.build_cmd(v_res.value)
        if not cmd_res.is_ok:
            return err("Failed to build ffmpeg command", inner=cmd_res)

        rid_res = process_manager_api.start(cmd_res.value, runner_id)
        if not rid_res.is_ok:
            return err("Failed to start process", inner=rid_res)
        
        return ok((rid_res.value, cmd_res.value))
