from typing import Optional, Literal, Any
from pathlib import Path
from pydantic import BaseModel, Field, FilePath, field_validator, model_validator
from .media_config import MediaType
from .media_config import MediaConfig_Definitions as M_Defs

class MediaModel(BaseModel):
    """
    Media configuration model for validation and processing.
    All fields have defaults as defined in media_config.py.
    """
    
    # Common fields

    media_type: MediaType # 必需参数 没有默认值
    
    input_path: FilePath  # 必需参数 没有默认值
    
    output_path: Path     # 必需参数 没有默认值
    
    clear_metadata: Optional[bool] = Field(default=M_Defs.clear_metadata.default)
    
    duration: Optional[float] = Field(default=M_Defs.duration.default, ge=M_Defs.duration.constraints["ge"])
    
    pad_start: Optional[float] = Field(default=M_Defs.pad_start.default, ge=M_Defs.pad_start.constraints["ge"])
    
    start: Optional[float] = Field(default=M_Defs.start.default, ge=M_Defs.start.constraints["ge"])
    
    end: Optional[float] = Field(default=M_Defs.end.default) # 可以是负数
    




    # Audio fields

    audio_format: Optional[str] = Field(default=M_Defs.audio_format.default)   # default 动态变化，此处默认 None
    
    audio_bitrate: Optional[str] = Field(default=M_Defs.audio_bitrate.default) # default 动态变化，此处默认 None
    
    audio_sample_rate: Optional[int] = Field(default=M_Defs.audio_sample_rate.default)
    
    audio_volume: Optional[int] = Field(
        default=M_Defs.audio_volume.default,
        ge=M_Defs.audio_volume.constraints["ge"],
        le=M_Defs.audio_volume.constraints["le"],
    )
    




    # Video fields

    video_crf: Optional[int] = Field(
        default=M_Defs.video_crf.default,
        ge=M_Defs.video_crf.constraints["ge"],
        le=M_Defs.video_crf.constraints["le"]
    )
    
    video_side_resolution: Optional[int] = Field(default=M_Defs.video_side_resolution.default)
    
    video_fps: Optional[int] = Field(default=M_Defs.video_fps.default)
    
    video_gop_optimize: Optional[bool] = Field(default=M_Defs.video_gop_optimize.default)

    video_mute: Optional[bool] = Field(default=M_Defs.video_mute.default)
    
    video_crop_x: Optional[int] = Field(default=M_Defs.video_crop_x.default, ge=M_Defs.video_crop_x.constraints["ge"])
    video_crop_y: Optional[int] = Field(default=M_Defs.video_crop_y.default, ge=M_Defs.video_crop_y.constraints["ge"])
    video_crop_w: Optional[int] = Field(default=M_Defs.video_crop_w.default, gt=M_Defs.video_crop_w.constraints["gt"])
    video_crop_h: Optional[int] = Field(default=M_Defs.video_crop_h.default, gt=M_Defs.video_crop_h.constraints["gt"])
    
    
    




    # Validators

    # 检查 options 约束
    @field_validator('audio_sample_rate')
    @classmethod
    def validate_audio_sample_rate_options(cls, v):
        if v is None:
            return v
        allowed = M_Defs.audio_sample_rate.constraints["options"]
        if v not in allowed:
            raise ValueError(f"audio_sample_rate must be one of {allowed}, got {v}")
        return v

    @field_validator('video_side_resolution')
    @classmethod
    def validate_video_side_resolution_options(cls, v):
        if v is None:
            return v
        allowed = M_Defs.video_side_resolution.constraints["options"]
        if v not in allowed:
            raise ValueError(f"video_side_resolution must be one of {allowed}, got {v}")
        return v

    @field_validator('video_fps')
    @classmethod
    def validate_video_fps_options(cls, v):
        if v is None:
            return v
        allowed = M_Defs.video_fps.constraints["options"]
        if v not in allowed:
            raise ValueError(f"video_fps must be one of {allowed}, got {v}")
        return v
    
    # 检查 media_type 不是 unknown
    @field_validator('media_type')
    @classmethod
    def validate_media_type_not_unknown(cls, v: MediaType):
        if v == MediaType.UNKNOWN:
            raise ValueError("media_type cannot be UNKNOWN.")
        return v









    # 后校验

    @model_validator(mode='after')
    def validate_common_times(self):
        """校验 start/end/pad_start/duration 之间的关系"""

        def resolve_end(self):
            return self.duration + self.end if self.end < 0 else self.end

        set_start = self.start is not None and self.start != 0
        set_end = self.end is not None and self.end != 0
        set_pad = self.pad_start is not None and self.pad_start != 0
        set_duration = self.duration is not None and self.duration != 0

        # 1. 如果 set_start / set_end，需要确保 set_duration
        if set_start and not set_duration:
            raise ValueError("If 'start' is set, 'duration' must also be set.")
        if set_end and not set_duration:
            raise ValueError("If 'end' is set, 'duration' must also be set.")

        # 2. set_start 和 set_pad 不能同时存在
        if set_start and set_pad:
            raise ValueError("'start' and 'pad_start' cannot both be set.")
        
        # 3. 确保 start < end < duration
        if set_start and self.start >= self.duration:
            raise ValueError("'start' must be less than 'duration'.")
        if set_end and resolve_end(self) >= self.duration:
            raise ValueError("'end' must be less than 'duration'.")
        if set_start and set_end and self.start >= resolve_end(self):
            raise ValueError("'start' must be less than 'end'.")

        # 最后更新 end 值 (如果设置了)
        if set_end:
            self.end = resolve_end(self)
        # 统一设置为三位小数/None
        self.start     = round(self.start, 3)     if set_start else None
        self.end       = round(self.end, 3)       if set_end else None
        self.pad_start = round(self.pad_start, 3) if set_pad else None
        self.duration  = round(self.duration, 3)  if set_duration else None

        return self



    @model_validator(mode='after')
    def validate_audio_format_bitrate(self):
        """根据 media_type 检验 audio_format 和 audio_bitrate"""

        # 获取 audio_format 的默认值和可选项
        result = M_Defs.get_audio_format_by_media_type(self.media_type)
        if not result.is_ok:
            raise ValueError(result.error_msg)
        audio_format_default, audio_format_options = result.value
        # 校验 audio_format
        if not self.audio_format:
            self.audio_format = audio_format_default
        if self.audio_format not in audio_format_options:
            raise ValueError(f"audio_format must be one of {audio_format_options}, got {self.audio_format}")

        # 获取 audio_bitrate 的默认值和可选项
        result = M_Defs.get_audio_bitrate_by_audio_format(self.audio_format)
        if not result.is_ok:
            raise ValueError(result.error_msg)
        audio_bitrate_default, audio_bitrate_options = result.value
        # 校验 audio_bitrate
        if not self.audio_bitrate:
            self.audio_bitrate = audio_bitrate_default
        if self.audio_bitrate not in audio_bitrate_options:
            raise ValueError(f"audio_bitrate must be one of {audio_bitrate_options}, got {self.audio_bitrate}")

        return self



    @model_validator(mode='after')
    def validate_video_crop_params(self):
        """校验 video_crop_w/h/x/y 的关系"""
        set_w = self.video_crop_w is not None
        set_h = self.video_crop_h is not None
        set_x = self.video_crop_x is not None
        set_y = self.video_crop_y is not None

        all_set = set_w and set_h and set_x and set_y
        all_unset = not set_w and not set_h and not set_x and not set_y

        # w/h/x/y 必须同时设置或同时不设置
        if not (all_set or all_unset):
            raise ValueError("video_crop w/h/x/y must be all set or all unset.")

        # 此处不做进一步的检查，交给 ffmpeg 自行处理
        return self



    @model_validator(mode='after')
    def validate_output_path(self):

        input_resolved = self.input_path.resolve()
        output_resolved = self.output_path.resolve()

        # 输出不能和输入相同
        if input_resolved == output_resolved:
            raise ValueError("output_path cannot be the same as input_path.")

        # 输出不能已存在
        if self.output_path.exists():
            raise ValueError(f"Output path already exists. Please delete it first:\n{output_resolved}")
        
        return self
