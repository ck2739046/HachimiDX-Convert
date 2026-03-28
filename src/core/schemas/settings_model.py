import os
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .settings_config import SettingsConfig_Definitions as S_Defs


class SettingsModel(BaseModel):

    model_config = ConfigDict(extra="allow")

    # 模型推理相关
    model_backend: str = Field(default=S_Defs.model_backend.default)
    inference_device: str = Field(default=S_Defs.inference_device.default)
    predict_batch_size_detect_obb: Annotated[int, Field(gt=S_Defs.predict_batch_size_detect_obb.constraints["gt"])] = S_Defs.predict_batch_size_detect_obb.default
    predict_batch_size_classify: Annotated[int, Field(gt=S_Defs.predict_batch_size_classify.constraints["gt"])] = S_Defs.predict_batch_size_classify.default
    # FFmpeg 硬件加速相关
    # ffmpeg_hw_accel_vp9: str = Field(default=S_Defs.ffmpeg_hw_accel_vp9.default)
    # ffmpeg_hw_accel_h264: str = Field(default=S_Defs.ffmpeg_hw_accel_h264.default)
    # 应用通用设置
    language: str = Field(default=S_Defs.language.default)
    main_output_dir: str = Field(default=S_Defs.main_output_dir.default)
    # 窗口大小
    main_app_init_size: tuple[
        Annotated[int, Field(ge=S_Defs.main_app_init_size.constraints["item_ge"], le=S_Defs.main_app_init_size.constraints["item_le"])],
        Annotated[int, Field(ge=S_Defs.main_app_init_size.constraints["item_ge"], le=S_Defs.main_app_init_size.constraints["item_le"])],
    ] = S_Defs.main_app_init_size.default
    main_app_min_size: tuple[
        Annotated[int, Field(ge=S_Defs.main_app_min_size.constraints["item_ge"], le=S_Defs.main_app_min_size.constraints["item_le"])],
        Annotated[int, Field(ge=S_Defs.main_app_min_size.constraints["item_ge"], le=S_Defs.main_app_min_size.constraints["item_le"])],
    ] = S_Defs.main_app_min_size.default



    @field_validator("model_backend")
    @classmethod
    def validate_model_backend_options(cls, v: str) -> str:
        allowed = S_Defs.model_backend.constraints["options"]
        if v not in allowed:
            raise ValueError(f"model_backend must be one of {allowed}")
        return v



    @field_validator("inference_device")
    @classmethod
    def validate_inference_device_options(cls, v: str) -> str:
        allowed = S_Defs.inference_device.constraints["options"]
        if v not in allowed:
            raise ValueError(f"inference_device must be one of {allowed}")
        return v



    # @field_validator("ffmpeg_hw_accel_vp9")
    # @classmethod
    # def validate_ffmpeg_hw_accel_vp9_options(cls, v: str) -> str:
    #     allowed = S_Defs.ffmpeg_hw_accel_vp9.constraints["options"]
    #     if v not in allowed:
    #         raise ValueError(f"ffmpeg_hw_accel_vp9 must be one of {allowed}")
    #     return v



    # @field_validator("ffmpeg_hw_accel_h264")
    # @classmethod
    # def validate_ffmpeg_hw_accel_h264_options(cls, v: str) -> str:
    #     allowed = S_Defs.ffmpeg_hw_accel_h264.constraints["options"]
    #     if v not in allowed:
    #         raise ValueError(f"ffmpeg_hw_accel_h264 must be one of {allowed}")
    #     return v



    @field_validator("language")
    @classmethod
    def validate_language_options(cls, v: str) -> str:
        allowed = S_Defs.language.constraints["options"]
        if v not in allowed:
            raise ValueError(f"language must be one of {allowed}")
        return v



    @model_validator(mode="after")
    def sync_inference_device_with_backend(self):
        self.inference_device = S_Defs.get_inference_device_by_backend(self.model_backend)
        return self



    # 自定义校验逻辑
    @field_validator('main_output_dir')
    @classmethod
    def check_main_output_dir(cls, v):
        text = str(v).strip()
        if not text:
            raise ValueError("main_output_dir cannot be empty")

        try:
            normalized = Path(text).expanduser().resolve(strict=False)
        except Exception as e:
            raise ValueError(f"main_output_dir is invalid path: {e}") from e

        if not normalized.is_absolute():
            raise ValueError("main_output_dir must be an absolute path")
        # 允许目录不存在，由运行时自动创建
        # 如果目录已存在，则检查是否为目录且可读写
        if normalized.exists():
            if not normalized.is_dir():
                raise ValueError("main_output_dir must be a directory")
            if not os.access(normalized, os.R_OK | os.W_OK):
                raise ValueError("main_output_dir is not readable/writable")

        return str(normalized)
