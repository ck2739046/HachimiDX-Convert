"""Pydantic models for generic FFmpeg run requests.

These models represent validated UI input only.
They do NOT decide how FFmpeg args are built/executed; that is handled later by
media_task_launcher (or other callers).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, FilePath, field_validator, model_validator

from ..task_contract import MediaType


# ===== Common primitives =====

Resolution = Literal[
    "origin",
    "540x540",
    "720x720",
    "1080x1080",
    "1440x1440",
    "2160x2160",
]

Fps = Literal["origin", "30", "60"]


def _ensure_max_3_decimals(value: float, field_name: str) -> float:
    # Accept up to 3 decimal places. We treat typical float noise conservatively.
    scaled = value * 1000
    if abs(scaled - round(scaled)) > 1e-9:
        raise ValueError(f"{field_name} must have at most 3 decimal places")
    return value


def _normalize_crop_str(v: str) -> str:
    raw = (v or "").strip()
    if not raw:
        return ""

    parts = raw.split(":")
    if len(parts) != 4:
        raise ValueError("crop must be in format 'w:h:x:y'")

    try:
        w, h, x, y = (int(p.strip()) for p in parts)
    except Exception:
        raise ValueError("crop must be in format 'w:h:x:y' with integers")

    if w <= 0 or h <= 0 or x < 0 or y < 0:
        raise ValueError("invalid crop values, expect x/y ≥ 0; w/h > 0")

    return f"{w}:{h}:{x}:{y}"





class RunFfmpegBase(BaseModel):
    """Common parameters shared by all run_ffmpeg_* requests."""

    # Required IO
    input_path: FilePath
    output_path: Path

    clear_metadata: bool = Field(default=True)

    # Timing (seconds)
    pad_start_sec: Optional[float] = Field(default=None, gt=0)
    trim_start_sec: Optional[float] = Field(default=None, gt=0)
    trim_end_sec: Optional[float] = Field(default=None)

    # Needed only when trim_end_sec is negative.
    input_duration_sec: Optional[float] = Field(default=None, gt=0)


    def resolved_trim_end_sec(self) -> Optional[float]:
        """Resolve trim_end_sec into an absolute '-to' seconds.

        - Positive values are used as-is.
        - Negative values mean "from end": input_duration_sec + trim_end_sec.
        """
        if self.trim_end_sec is None:
            return None

        end = float(self.trim_end_sec)
        if end >= 0:
            return end

        if self.input_duration_sec is None:
            raise ValueError("input_duration_sec is required when trim_end_sec is negative")

        resolved = float(self.input_duration_sec) + end
        return resolved


    @field_validator("pad_start_sec")
    @classmethod
    def _validate_pad_start_precision(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        return _ensure_max_3_decimals(float(v), "pad_start_sec")


    @field_validator("trim_start_sec")
    @classmethod
    def _validate_trim_start_precision(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        return _ensure_max_3_decimals(float(v), "trim_start_sec")


    @field_validator("trim_end_sec")
    @classmethod
    def _validate_trim_end_precision(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        return _ensure_max_3_decimals(float(v), "trim_end_sec")


    @model_validator(mode="after")
    def _validate_common_constraints(self) -> "RunFfmpegBase":
        # Mutual exclusion: pad_start_sec vs trim_start_sec
        if self.pad_start_sec is not None and self.trim_start_sec is not None:
            raise ValueError("pad_start_sec and trim_start_sec are mutually exclusive")

        # Validate negative trim_end_sec
        if self.trim_end_sec is not None and float(self.trim_end_sec) < 0:
            _ = self.resolved_trim_end_sec()  # may raise

        # If both trim_start and trim_end exist, ensure end > start
        if self.trim_start_sec is not None and self.trim_end_sec is not None:
            end = self.resolved_trim_end_sec()
            if end is not None and end <= float(self.trim_start_sec):
                raise ValueError("trim_end_sec must be greater than trim_start_sec")

        return self






# ===== Audio =====

AudioFormat = Literal["ogg", "mp3"]

OggVbr = Literal["vbr 8 (256k)", "vbr 7 (224k)", "vbr 6 (191k)"]
Mp3Vbr = Literal["vbr 0 (245k)", "vbr 1 (225k)", "vbr 2 (190k)"]

SampleRate = Literal[44100, 48000]


class RunFfmpegAudio(RunFfmpegBase):
    """Run FFmpeg: audio output."""

    media_type: MediaType = Field(default=MediaType.AUDIO)

    format: AudioFormat = Field(default="ogg")
    sample_rate: SampleRate = Field(default=44100)

    # If omitted, default is the middle option for the chosen format.
    bitrate: Optional[str] = Field(default=None)

    volume: int = Field(default=100, ge=0, le=200, description="0-200 means 0%-200%")


    @model_validator(mode="after")
    def _validate_audio_bitrate(self) -> "RunFfmpegAudio":
        if self.bitrate is None:
            self.bitrate = "vbr 7 (224k)" if self.format == "ogg" else "vbr 1 (225k)"
            return self

        if self.format == "ogg":
            allowed: tuple[str, ...] = ("vbr 8 (256k)", "vbr 7 (224k)", "vbr 6 (191k)")
        else:
            allowed = ("vbr 0 (245k)", "vbr 1 (225k)", "vbr 2 (190k)")

        if self.bitrate not in allowed:
            raise ValueError(f"Invalid bitrate for format={self.format}: {self.bitrate}")

        return self






# ===== Video without audio =====

class RunFfmpegVideoWithoutAudio(RunFfmpegBase):
    """Run FFmpeg: video output without audio."""

    media_type: MediaType = Field(default=MediaType.VIDEO_WITHOUT_AUDIO)

    crf: int = Field(default=23, ge=20, le=28)
    resolution: Resolution = Field(default="origin")
    fps: Fps = Field(default="origin")
    gop_optimize: bool = Field(default=False)

    # Optional crop rectangle: "w:h:x:y"
    crop: Optional[str] = Field(default=None)


    @field_validator("crop")
    @classmethod
    def _validate_crop(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = _normalize_crop_str(v)
        return normalized or None






# ===== Video with audio =====

aac_bitrate = Literal["cbr 224k", "cbr 192k", "cbr 160k"]


class RunFfmpegVideoWithAudio(RunFfmpegBase):
    """Run FFmpeg: video output with audio (AAC)."""

    media_type: MediaType = Field(default=MediaType.VIDEO_WITH_AUDIO)

    # audio
    audio_format: Literal["aac"] = Field(default="aac")
    audio_sample_rate: SampleRate = Field(default=44100)
    audio_bitrate: Optional[aac_bitrate] = Field(default=None)
    volume: int = Field(default=100, ge=0, le=200, description="0-200 means 0%-200%")

    # video
    crf: int = Field(default=23, ge=20, le=28)
    resolution: Resolution = Field(default="origin")
    fps: Fps = Field(default="origin")
    gop_optimize: bool = Field(default=False)

    # Optional crop rectangle: "w:h:x:y"
    crop: Optional[str] = Field(default=None)

    mute: bool = Field(default=False)


    @field_validator("crop")
    @classmethod
    def _validate_crop(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = _normalize_crop_str(v)
        return normalized or None


    @model_validator(mode="after")
    def _validate_aac_defaults(self) -> "RunFfmpegVideoWithAudio":
        if self.audio_bitrate is None:
            self.audio_bitrate = "cbr 192k"
        return self
