"""Media task config: Run FFmpeg (audio/video/video_muted).

This config is created from the Run FFmpeg UI form.
All fields are validated by Pydantic so the backend ffmpeg launcher can stay lean.

Output path rule:
- Output file is in the same directory as input.
- Output filename is input stem + _yy-mm-dd_hh-mm-ss + .{ext}
- For video/video_muted, ext is always mp4.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, FilePath, model_validator

from .base_task_config import BaseTaskConfig


MediaType = Literal["audio", "video", "video_muted"]
AudioFormat = Literal["mp3", "ogg"]
AudioQualityTier = Literal[0, 1, 2]
SampleRate = Literal[44100, 48000]


class RunFfmpegTaskConfig(BaseTaskConfig):
    """Validated config for running a general ffmpeg job."""

    # Required input
    input_path: FilePath

    # Determined by detect, user can override
    media_type: MediaType = Field(default="audio")

    # Derived output path (kept as a field so UI can display/log it).
    output_path: Path | None = Field(default=None)

    # Common options
    clear_metadata: bool = Field(default=True)

    # Timing (seconds)
    trim_start_sec: float | None = Field(default=None, ge=0)
    trim_end_sec: float | None = Field(default=None)
    pad_start_sec: float | None = Field(default=None, ge=0)
    pad_end_sec: float | None = Field(default=None, ge=0)

    # Needed only when trim_end_sec is negative
    input_duration_sec: float | None = Field(default=None, gt=0)

    # Audio options (audio-only; also reused for video-with-audio)
    audio_format: AudioFormat = Field(default="ogg")
    audio_quality: AudioQualityTier = Field(default=1)
    sample_rate: SampleRate = Field(default=44100)
    volume: int = Field(default=100, ge=0, le=200)

    # Video options
    use_origin_resolution: bool = Field(default=True)
    width: int | None = Field(default=None, ge=16, le=7680)
    height: int | None = Field(default=None, ge=16, le=4320)

    use_origin_fps: bool = Field(default=True)
    fps: float | None = Field(default=None, gt=0, le=240)

    crf: int = Field(default=23, ge=0, le=51)
    preset: str = Field(default="medium")
    gop_30: bool = Field(default=False)

    @staticmethod
    def _timestamp_suffix(now: datetime | None = None) -> str:
        dt = now or datetime.now()
        return dt.strftime("%y-%m-%d_%H-%M-%S")

    def resolved_trim_end_sec(self) -> float | None:
        """Resolve trim_end_sec into an absolute '-to' time in seconds.

        - Positive values are used as-is.
        - Negative values mean "from end": duration + trim_end_sec.
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

    @model_validator(mode="after")
    def _validate_and_derive(self) -> "RunFfmpegTaskConfig":
        # Mutual exclusion: pad_start vs trim_start
        if self.pad_start_sec is not None and self.trim_start_sec is not None:
            raise ValueError("pad_start_sec and trim_start_sec cannot both be set")

        # Mutual exclusion: pad_end vs trim_end
        if self.pad_end_sec is not None and self.trim_end_sec is not None:
            raise ValueError("pad_end_sec and trim_end_sec cannot both be set")

        # Validate negative trim_end
        if self.trim_end_sec is not None and float(self.trim_end_sec) < 0:
            _ = self.resolved_trim_end_sec()  # may raise

        # If both trim_start and trim_end exist, ensure end > start
        if self.trim_start_sec is not None and self.trim_end_sec is not None:
            end = self.resolved_trim_end_sec()
            if end is not None and end <= float(self.trim_start_sec):
                raise ValueError("trim_end_sec must be greater than trim_start_sec")

        # Derive output path
        in_path = Path(self.input_path)
        suffix = self._timestamp_suffix(datetime.now())

        if self.media_type in ("video", "video_muted"):
            ext = "mp4"
        else:
            ext = self.audio_format

        out_name = f"{in_path.stem}_{suffix}.{ext}"
        self.output_path = in_path.parent / out_name

        return self
