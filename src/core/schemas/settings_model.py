from typing import Literal, Annotated
from pydantic import BaseModel, Field, field_validator

from ..tools import validate_windows_filename


class SettingsModel(BaseModel):

    # 模型推理相关
    model_backend: Literal["tensorrt", "directml"] = Field(default="tensorrt")
    tensorrt_batch_size: Annotated[int, Field(ge=1, le=8)] = 2
    # FFmpeg 硬件加速相关
    ffmpeg_hw_accel_vp9: Literal["cpu", "nvidia"] = Field(default="cpu")
    ffmpeg_hw_accel_h264: Literal["cpu", "nvidia"] = Field(default="cpu")
    # 应用通用设置
    language: Literal["zh_CN", "en_US"] = Field(default="zh_CN")
    main_output_dir_name: str = Field(default="1-output")
    # 窗口大小
    main_app_init_size: tuple[Annotated[int, Field(ge=500, le=5000)], Annotated[int, Field(ge=500, le=5000)]] = (1300, 900)
    main_app_min_size: tuple[Annotated[int, Field(ge=500, le=5000)], Annotated[int, Field(ge=500, le=5000)]] = (800, 600)

    # 自定义校验逻辑
    @field_validator('main_output_dir_name')
    @classmethod
    def check_filename(cls, v):
        result = validate_windows_filename(v)
        if not result.is_ok:
            raise ValueError(result.error_msg)
        return v
