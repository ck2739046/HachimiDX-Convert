from dataclasses import dataclass
from enum import Enum
from typing import Literal


class MediaType(str, Enum):
    AUDIO = "audio"
    VIDEO_WITH_AUDIO = "video_with_audio"
    VIDEO_WITHOUT_AUDIO = "video_without_audio"
    UNKNOWN = "unknown"



@dataclass(slots=True)
class MediaConfig_Definition:
    """
    Definition for MediaConfig

    Attributes:
        key: str
        type: Literal["int", "float", "path", "str", "bool", "enum(MediaType)"]
        group: Literal["audio", "video", "common"]
        default: any
        optional: bool
        constraints: dict | None

    Constraints:
        For int/float:
            - "ge": int, minimum value (inclusive)
            - "gt": int, minimum value (exclusive)
            - "le": int, maximum value (inclusive)
            - "lt": int, maximum value (exclusive)
            - "options": list of allowed values
        For str:
            - "options": list of allowed strings
        For path:
            - "must_exist": bool
        For bool:
            - N/A
    """

    key: str
    type: Literal["int", "float", "path", "str", "bool", "enum"]
    group: Literal["audio", "video", "common"]
    default: any = None
    optional: bool = True
    constraints: dict | None = None
    


@dataclass(slots=True)
class MediaConfig_Definitions:

    # common

    media_type = MediaConfig_Definition(
        key="media_type",
        type="enum",
        group="common",
        optional=False, # 必选没有默认值
    )

    input_path = MediaConfig_Definition(
        key="input_path",
        type="path",
        group="common",
        optional=False, # 必选没有默认值
        constraints={
            "must_exist": True
        }
    )

    output_path = MediaConfig_Definition(
        key="output_path",
        type="path",
        group="common",
        optional=False, # 必选没有默认值
        constraints={
            "must_exist": False
        }
    )

    clear_metadata = MediaConfig_Definition(
        key="clear_metadata",
        type="bool",
        group="common",
        default=False
    )

    duration = MediaConfig_Definition(
        key="duration",
        type="float",
        group="common",
        default=None,
        constraints={
            "ge": 0.0
        }
    )

    pad_start = MediaConfig_Definition(
        key="pad_start",
        type="float",
        group="common",
        default=None,
        constraints={
            "ge": 0.0
        }
    )

    start = MediaConfig_Definition(
        key="start",
        type="float",
        group="common",
        default=None,
        constraints={
            "ge": 0.0
        }
    )

    end = MediaConfig_Definition(
        key="end",
        type="float",
        group="common",
        default=None,
    )





    # audio

    # see get_audio_format_by_media_type()
    audio_format = MediaConfig_Definition(
        key="audio_format",
        type="str",
        group="audio",
        default=None, # auto
    )

    @staticmethod
    def get_audio_format_by_media_type(media_type: MediaType) -> tuple[str, list[str]]:
        """return (default, options)"""
        if media_type == MediaType.AUDIO:
            return "ogg", ["mp3", "aac", "ogg"]
        elif media_type == MediaType.VIDEO_WITH_AUDIO or \
            media_type == MediaType.VIDEO_WITHOUT_AUDIO:
            return "aac", ["aac"]
        else:
            return "", [""]

    # see get_audio_bitrate_by_audio_format()
    audio_bitrate = MediaConfig_Definition(
        key="audio_bitrate",
        type="str",
        group="audio",
        default=None, # auto
    )

    @staticmethod
    def get_audio_bitrate_by_audio_format(audio_format: str) -> tuple[str, list[str]]:
        """return (default, options)"""
        if audio_format == "mp3":
            return "vbr_1", ["vbr_0", "vbr_1", "vbr_2"]
        elif audio_format == "aac":
            return "cbr_192k", ["cbr_160k", "cbr_192k", "cbr_224k"]
        elif audio_format == "ogg":
            return "vbr_7", ["vbr_6", "vbr_7", "vbr_8"]
        else:
            return "", [""]

    audio_sample_rate = MediaConfig_Definition(
        key="audio_sample_rate",
        type="int",
        group="audio",
        default=44100,
        constraints={
            "options": [44100, 48000]
        }
    )

    audio_volume = MediaConfig_Definition(
        key="audio_volume",
        type="int",
        group="audio",
        default=100,
        constraints={
            "ge": 0,
            "le": 200
        }
    )










    # video

    video_crf = MediaConfig_Definition(
        key="video_crf",
        type="int",
        group="video",
        default=23,
        constraints={
            "ge": 20,
            "le": 28
        }
    )

    video_side_resolution = MediaConfig_Definition(
        key="video_side_resolution",
        type="int",
        group="video",
        default=0, # original
        constraints={
            "options": [0, 480, 720, 1080, 1440, 2160]
        }
    )

    video_fps = MediaConfig_Definition(
        key="video_fps",
        type="int",
        group="video",
        default=0, # original
        constraints={
            "options": [0, 30, 60]
        }
    )

    video_gop_optimize = MediaConfig_Definition(
        key="video_gop_optimize",
        type="bool",
        group="video",
        default=False
    )

    video_mute = MediaConfig_Definition(
        key="video_mute",
        type="bool",
        group="video",
        default=False
    )

    video_crop_x = MediaConfig_Definition(
        key="video_crop_x",
        type="int",
        group="video",
        default=None,
        constraints={
            "ge": 0
        }
    )

    video_crop_y = MediaConfig_Definition(
        key="video_crop_y",
        type="int",
        group="video",
        default=None,
        constraints={
            "ge": 0
        }
    )

    video_crop_w = MediaConfig_Definition(
        key="video_crop_w",
        type="int",
        group="video",
        default=None,
        constraints={
            "gt": 0
        }
    )

    video_crop_h = MediaConfig_Definition(
        key="video_crop_h",
        type="int",
        group="video",
        default=None,
        constraints={
            "gt": 0
        }
    )
