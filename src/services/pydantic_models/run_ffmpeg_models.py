"""Pydantic models for generic FFmpeg run requests.

These models represent validated UI input only.
They do NOT decide how FFmpeg args are built/executed; that is handled later by
media_task_launcher (or other callers).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, get_args

from pydantic import BaseModel, Field, FilePath, field_validator, model_validator

from ..path_manage import PathManage

from ..task_contract import MediaType

import i18n




# common
Clear_Metadata = "bool"
Clear_Metadata_Default = True


# video
Video_Resolution_Options = Literal["origin", "540×540",
                                   "720×720", "1080×1080",
                                   "1440×1440", "2160×2160"]
Video_Resolution_Default = "origin"

Video_FPS_Options = Literal["origin", "30", "60"]
Video_FPS_Default = "origin"

Video_CRF_Range = (20, 28)
Video_CRF_Default = 23

Video_GOP_Optimize = "bool"
Video_GOP_Optimize_Default = False

Video_Mute = "bool"
Video_Mute_Default = False


# audio
Audio_SampleRate_Options = Literal[44100, 48000]
Audio_SampleRate_Default = 44100

Audio_Volume_Range = (0, 200)
Audio_Volume_Default = 100

Audio_Format_Options_Audio = Literal["ogg", "mp3"]
Audio_Format_Default_Audio = "ogg"
Audio_Bitrate_Options_ogg = Literal["vbr 8 (256k)", "vbr 7 (224k)", "vbr 6 (191k)"]
Audio_Bitrate_Default_ogg = "vbr 7 (224k)"
Audio_Bitrate_Options_mp3 = Literal["vbr 0 (245k)", "vbr 1 (225k)", "vbr 2 (190k)"]
Audio_Bitrate_Default_mp3 = "vbr 1 (225k)"

Audio_Format_Options_Video = Literal["aac"]
Audio_Format_Default_Video = "aac"
Audio_Bitrate_Options_aac = Literal["cbr 224k", "cbr 192k", "cbr 160k"]
Audio_Bitrate_Default_aac = "cbr 192k"






def _ensure_max_3_decimals(value: float, field_name: str) -> float:
    # Accept up to 3 decimal places
    scaled = value * 1000
    if abs(scaled - round(scaled)) > 1e-9:
        raise ValueError(f"{field_name} must have at most 3 decimal places")
    return value



class RunFFmpegBase(BaseModel):
    """
    Common parameters shared by all run_ffmpeg_* requests.

    必需:
        input_path     已存在的文件路径
        output_path    输出文件路径，父目录必须存在
        clear_metadata 是否清除元数据，bool，默认True

    可选:
        media_type          MediaType Enum，后续子类会覆此字段
        input_duration_sec  输入文件时长(秒)，最多三位小数float，≥0
        pad_start_sec       开头填充时长(秒)，最多三位小数float，≥0
        start_sec           起始时间(秒)，最多三位小数float，≥0
                            该时间点之前的内容将被丢弃
        end_sec             结束时间(秒)，最多三位小数float，可为负数
                            该时间点之后的内容将被丢弃

    说明:
        - pad_start_sec 与 start_sec 互斥，不能同时设置
        - 如果设置了 start_sec 或 end_sec，则必须提供 input_duration_sec
        - end_sec 为负数时，表示从文件结尾向前计算 -> input_duration_sec + end_sec
        - pad_start_sec/start_sec/end_sec/input_duration_sec = 0 视为未设置 (None)
    """

    # Required
    input_path: FilePath # must exist
    output_path: Path    # only parent dir must exist
    clear_metadata: bool = Field(default = Clear_Metadata_Default)

    # Optional
    input_duration_sec: Optional[float] = Field(default=None, gt=0)
    pad_start_sec: Optional[float] = Field(default=None, gt=0)
    start_sec: Optional[float] = Field(default=None, gt=0)
    end_sec: Optional[float] = Field(default=None)

    # 基础校验，三位小数
    @field_validator("pad_start_sec")
    @classmethod
    def _validate_pad_start_precision(cls, v: Optional[float]) -> Optional[float]:
        if v is None or v == 0:
            return None
        return _ensure_max_3_decimals(float(v), "pad_start_sec")

    # 基础校验，三位小数
    @field_validator("start_sec")
    @classmethod
    def _validate_start_precision(cls, v: Optional[float]) -> Optional[float]:
        if v is None or v == 0:
            return None
        return _ensure_max_3_decimals(float(v), "start_sec")

    # 基础校验，三位小数
    @field_validator("end_sec")
    @classmethod
    def _validate_end_precision(cls, v: Optional[float]) -> Optional[float]:
        if v is None or v == 0:
            return None
        return _ensure_max_3_decimals(float(v), "end_sec")

    # 后校验，互斥，检查取值范围，end_sec变正数
    @model_validator(mode="after")
    def _validate_times_constraints(self) -> "RunFFmpegBase":

        def resolved_end_sec(self) -> Optional[float]:
            """
            Positive: use as-is.
            Negative: input_duration_sec + end_sec.
            """
            # 检查 input_duration_sec 存在
            if self.input_duration_sec is None or self.input_duration_sec == 0:
                raise ValueError("input_duration_sec is required when end_sec is set")
            # resolve negative
            end_f = float(self.end_sec)
            duration_f = float(self.input_duration_sec)
            end_resolved = duration_f + end_f if end_f < 0 else end_f
            # 检查 end > duration
            if end_resolved > duration_f:
                raise ValueError("Must not end_sec > input_duration_sec")
            return end_resolved

        set_start = self.start_sec is not None and self.start_sec != 0
        set_end = self.end_sec is not None and self.end_sec != 0
        set_pad = self.pad_start_sec is not None and self.pad_start_sec != 0
        set_duration = self.input_duration_sec is not None and self.input_duration_sec != 0

        # Mutual exclusion: pad_start_sec vs start_sec
        if set_pad and set_start:
            raise ValueError("pad_start_sec and start_sec cannot be both set")
        
        # Validata start_sec < input_duration_sec
        if set_start:
            if not set_duration:
                raise ValueError("input_duration_sec is required when start_sec is set")
            if float(self.start_sec) >= float(self.input_duration_sec):
                raise ValueError("Must not start_sec ≥ input_duration_sec")     
        # Validate trim_end_sec < input_duration_sec
        if set_end:
            _ = resolved_end_sec(self) # check included, may raise

        # Ensure start_sec < end_sec if both are set
        if set_start and set_end:
            if float(self.start_sec) >= resolved_end_sec(self):
                raise ValueError("Must not start_sec ≥ end_sec")

        return self
    
    # 后校验，确保 output_path 不存在
    @model_validator(mode="after")
    def _validate_output_path_not_exists(self) -> "RunFFmpegBase":
        if not self.output_path.exists:
            return self
        # 已存在，询问用户是否删除
        from src.core.tools import show_confirm_dialog # 避免循环依赖
        user_confirmed = show_confirm_dialog(
            title = "",
            prompt_text = i18n.t("pydantic_models.run_ffmpeg.ui_prompt_delete_existing_output_file", file_path=str(self.output_path))
        )
        if user_confirmed:
            # 用户同意删除文件
            try:
                self.output_path.unlink()
            except Exception as e:
                raise ValueError(f"Failed to delete existing output file: {e}")
        else:
            # 用户不同意，抛出错误
            raise ValueError("Output file already exists and user declined to delete it.")





# ===== Audio =====

class RunFFmpegAudio(RunFFmpegBase):
    """
    Run FFmpeg: audio output.

    包含所有 Base 字段，另加:
    
    必需:
        media_type        MediaType.AUDIO
        audio_format      音频格式，str(ogg/mp3), 默认 ogg
        audio_sample_rate 音频采样率，int(44100/48000)，默认 44100
        audio_volume      音频音量，int(0-200)，默认 100
    
    可选:
        audio_bitrate     音频码率，str，未设置时根据 format 自动选择默认值
    """

    media_type: MediaType = Field(default = MediaType.AUDIO)

    audio_format: Audio_Format_Options_Audio = Field(default = Audio_Format_Default_Audio)
    audio_bitrate: Optional[str] = Field(default=None) # 可选，如果 None，根据 format 自动选择默认

    audio_sample_rate: Audio_SampleRate_Options = Field(default = Audio_SampleRate_Default)
    audio_volume: int = Field(default = Audio_Volume_Default,
                              ge = Audio_Volume_Range[0],
                              le = Audio_Volume_Range[1],
                              description=f"{Audio_Volume_Range[0]}-{Audio_Volume_Range[1]} means {Audio_Volume_Range[0]}%-{Audio_Volume_Range[1]}%")

    @model_validator(mode="after")
    def _validate_audio_bitrate(self) -> "RunFFmpegAudio":
        # 如果 bitrate 未设置，使用默认值
        if self.audio_bitrate is None:
            if self.audio_format == "ogg":
                self.audio_bitrate = Audio_Bitrate_Default_ogg
            elif self.audio_format == "mp3":
                self.audio_bitrate = Audio_Bitrate_Default_mp3
            return self
        
        # 如果 bitrate 已设置，检查合法性
        if self.audio_format == "ogg":
            allowed: tuple[str, ...] = get_args(Audio_Bitrate_Options_ogg)
        elif self.audio_format == "mp3":
            allowed: tuple[str, ...] = get_args(Audio_Bitrate_Options_mp3)

        if self.audio_bitrate not in allowed:
            raise ValueError(f"Invalid bitrate for format={self.audio_format}: {self.audio_bitrate}")

        return self






# ===== Video without audio =====

class RunFFmpegVideoWithoutAudio(RunFFmpegBase):
    """
    Run FFmpeg: video output without audio.
    
    包含所有 Base 字段，另加:

    必需:
        media_type          MediaType.VIDEO_WITHOUT_AUDIO
        video_crf           视频CRF，int(20-28)，默认23
        video_resolution    视频分辨率，str(xxx)，默认origin
        video_fps           视频帧率，str(origin/30/60)，默认origin
        video_gop_optimize  是否启用GOP优化，bool，默认False

    可选:
        video_crop          视频裁剪，int tuple(w, h, x, y)

    说明:
        - video_crop 中的 w,h > 0，x,y ≥ 0
    """

    media_type: MediaType = Field(default=MediaType.VIDEO_WITHOUT_AUDIO)

    video_crf: int = Field(default = Video_CRF_Default,
                           ge = Video_CRF_Range[0],
                           le = Video_CRF_Range[1])
    video_resolution: Video_Resolution_Options = Field(default = Video_Resolution_Default)
    video_fps: Video_FPS_Options = Field(default = Video_FPS_Default)
    video_gop_optimize: bool = Field(default = Video_GOP_Optimize_Default)

    # Optional video_crop param: int tuple(w, h, x, y)
    video_crop: Optional[tuple[int, int, int, int]] = Field(default=None)


    @field_validator("video_crop")
    @classmethod
    def _validate_video_crop(cls, v: Optional[tuple[int, int, int, int]]) -> Optional[tuple[int, int, int, int]]:
        if v is None:
            return None
        w, h, x, y = v
        if w <= 0 or h <= 0:
            raise ValueError("video_crop width and height must be positive integers")
        if x < 0 or y < 0:
            raise ValueError("video_crop x_offset and y_offset must be non-negative integers")
        return v






# ===== Video with audio =====

class RunFFmpegVideoWithAudio(RunFFmpegVideoWithoutAudio):
    """
    Run FFmpeg: video output with audio.

    包含所有 Base + RunFFmpegVideoWithoutAudio 字段，另加:

    必需:
        media_type        MediaType.VIDEO_WITH_AUDIO
        video_mute        是否静音，bool，默认False

    可选 (仅 video_mute=False 才需要):
        audio_format      音频格式，str(aac)，默认 aac
        audio_sample_rate 音频采样率，int(44100/48000)，默认 44100
        audio_volume      音频音量，int(0-200)，默认 100
        audio_bitrate     音频码率，str，未设置时根据 format 自动选择默认值

    说明:
        - 如果 video_mute=True，音频相关的参数将被后端忽略。
    """

    media_type: MediaType = Field(default=MediaType.VIDEO_WITH_AUDIO)

    # 必需字段
    video_mute: bool

    # 音频参数可选，保留默认值
    audio_format: Optional[Audio_Format_Options_Video] = Field(default = Audio_Format_Default_Video)
    audio_bitrate: Optional[str] = Field(default=None) # 如果 None，根据 format 自动选择默认
    audio_sample_rate: Optional[Audio_SampleRate_Options] = Field(default = Audio_SampleRate_Default)
    audio_volume: Optional[int] = Field(default = Audio_Volume_Default,
                                        ge = Audio_Volume_Range[0],
                                        le = Audio_Volume_Range[1],
                                        description=f"{Audio_Volume_Range[0]}-{Audio_Volume_Range[1]} means {Audio_Volume_Range[0]}%-{Audio_Volume_Range[1]}%")

    @model_validator(mode="after")
    def _validate_audio_bitrate(self) -> "RunFFmpegVideoWithAudio":
        # 如果 bitrate 未设置，使用默认值
        if self.audio_bitrate is None:
            self.audio_bitrate = Audio_Bitrate_Default_aac
            return self
        # 如果 bitrate 已设置，检查合法性
        allowed: tuple[str, ...] = get_args(Audio_Bitrate_Options_aac)
        if self.audio_bitrate not in allowed:
            raise ValueError(f"Invalid bitrate for format={self.audio_format}: {self.audio_bitrate}")
        return self
  








def get_ffmpeg_options() -> tuple[dict, dict, dict]:
    """
    返回三个字典: tuple(common_opts, video_opts, audio_opts)
    
    combobox: dict{opts: list, default: value}
    checkbox: bool_default_value
    lineEdit: min_int, max_int, default_int

    common:
        clear_metadata: bool_default_value

    video:
        video_crf: dict(str_list, default_int)
        video_resolution: dict(str_list, default_str)
        video_fps: dict(str_list, default_str)
        video_gop_optimize: bool_default_value
        video_mute: bool_default_value

    audio:
        audio_format_audio: dict(str_list, default_str)
        audio_format_video: dict(str_list, default_str) 
        audio_bitrate_ogg: dict(str_list, default_str)
        audio_bitrate_mp3: dict(str_list, default_str)
        audio_bitrate_aac: dict(str_list, default_str)
        audio_sample_rate: dict(int_list, default_int)
        volume: tuple(min_int, max_int, default_int)
    """

    common_opts = {
        "clear_metadata": Clear_Metadata_Default,
    }
    
    video_opts = {
        "video_crf": {"opts": list(range(Video_CRF_Range[0], Video_CRF_Range[1]+1)),
                      "default": Video_CRF_Default},
        "video_resolution": {"opts": list(get_args(Video_Resolution_Options)),
                             "default": Video_Resolution_Default},
        "video_fps": {"opts": list(get_args(Video_FPS_Options)),
                      "default": Video_FPS_Default},
        "video_gop_optimize": Video_GOP_Optimize_Default,
        "video_mute": Video_Mute_Default,
    }

    audio_opts = {
        "audio_format_video": {"opts": list(get_args(Audio_Format_Options_Video)),
                               "default": Audio_Format_Default_Video},
        "audio_format_audio": {"opts": list(get_args(Audio_Format_Options_Audio)),
                               "default": Audio_Format_Default_Audio},
        # bitrate 命名格式: audio_bitrate_{format}
        "audio_bitrate_ogg":  {"opts": list(get_args(Audio_Bitrate_Options_ogg)),
                               "default": Audio_Bitrate_Default_ogg},
        "audio_bitrate_mp3":  {"opts": list(get_args(Audio_Bitrate_Options_mp3)),
                               "default": Audio_Bitrate_Default_mp3},
        "audio_bitrate_aac":  {"opts": list(get_args(Audio_Bitrate_Options_aac)),
                               "default": Audio_Bitrate_Default_aac},
        "audio_sample_rate":  {"opts": list(get_args(Audio_SampleRate_Options)),
                               "default": Audio_SampleRate_Default},
        "audio_volume": (Audio_Volume_Range[0],
                         Audio_Volume_Range[1],
                         Audio_Volume_Default)
    }

    return common_opts, video_opts, audio_opts



def build_full_output_path(input_path: str, output_filename: str, output_extension: str) -> tuple[bool, Optional[Path], Optional[str]]:

    """
    构建完整的输出文件路径

    Args:
        input_path: Path，输入文件路径
        output_filename: str，输出文件名，仅文件名，不包含路径和扩展名
        output_extension: str，输出文件扩展名，包含点号，例如 ".mp4"

    Returns:
        ok: bool
        output_path: Optional[Path]
        error_msg: Optional[str])

    说明:
        - 首先检查 output_filename 是否符合 windows 标准
        - 如果 output_filename 为空，默认使用 input_filename_modified
        - 输出文件与输入文件在同一目录下
    """

    # 校验输出文件名 (如果有提供)
    if output_filename:
        is_valid = PathManage.validate_windows_filename(output_filename)
        if not is_valid:
            error_msg = i18n.t("pydantic_models.run_ffmpeg.error_invalid_output_filename")
            return False, None, error_msg
        
    # 校验输出拓展名
    if not output_extension:
        error_msg = i18n.t("pydantic_models.run_ffmpeg.error_empty_output_extension")
        return False, None, error_msg
    if not output_extension.startswith("."):
        error_msg = i18n.t("pydantic_models.run_ffmpeg.error_invalid_output_extension")
        return False, None, error_msg
        
    # 构建最终输出文件路径
    input_dir = Path(input_path).parent

    if not output_filename:
        input_stem = Path(input_path).stem # 如果空文件名，使用默认文件名
        final_output_path = input_dir / f"{input_stem}_modified{output_extension}"
    else:
        final_output_path = input_dir / f"{output_filename}{output_extension}"

    return True, final_output_path, None
