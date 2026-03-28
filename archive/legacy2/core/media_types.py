from enum import Enum

class MediaType(str, Enum):
    UNKNOWN = "unknown"
    VIDEO_WITH_AUDIO = "video_with_audio"
    VIDEO_WITHOUT_AUDIO = "video_without_audio"
    AUDIO = "audio"
