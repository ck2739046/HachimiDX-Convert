"""Media task config: Audio transcode.

This config is intended to be created from UI form values.
All fields are validated by Pydantic, so backend ffmpeg utilities can stay lean.

Output path rule (per requirements):
- Output file is in the same directory as input.
- Output filename is input stem + _yy-mm-dd_hh-mm-ss + .{format}
- If output file already exists, it should be deleted *before* running ffmpeg (handled by backend).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, FilePath, model_validator

from .base_task_config import BaseTaskConfig


AudioFormat = Literal["mp3", "ogg"]
AudioQualityTier = Literal[0, 1, 2]
SampleRate = Literal[44100, 48000]


class MediaAudioTaskConfig(BaseTaskConfig):
    """Validated config for running an audio ffmpeg job."""

    # Input file must exist.
    input_path: FilePath

    # Output is always derived from input_path + timestamp + format.
    # We still keep it as a field so it can be displayed and logged.
    output_path: Path | None = Field(default=None)

    # Audio options
    format: AudioFormat = Field(default="ogg")
    audio_quality: AudioQualityTier = Field(default=1)
    sample_rate: SampleRate = Field(default=44100)
    volume: int = Field(default=100, ge=0, le=200, description="0-200, representing 0%-200%")
    clear_metadata: bool = Field(default=True)

    @staticmethod
    def _timestamp_suffix(now: datetime | None = None) -> str:
        dt = now or datetime.now()
        return dt.strftime("%y-%m-%d_%H-%M-%S")

    @model_validator(mode="after")
    def _derive_output_path(self) -> "MediaAudioTaskConfig":
        # Always derive output path from input path + format.
        in_path = Path(self.input_path)
        # BaseTaskConfig intentionally does not carry created_at.
        # Use "now" at validation time as the timestamp source.
        suffix = self._timestamp_suffix(datetime.now())
        out_name = f"{in_path.stem}_{suffix}.{self.format}"
        self.output_path = in_path.parent / out_name
        return self
