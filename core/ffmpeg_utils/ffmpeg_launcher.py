from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Tuple

from PyQt6.QtCore import QProcess

from locales import LocaleManage
from settings import SettingsManage
from tasks.task_configs import MediaAudioTaskConfig


def _get_audio_codec(format_str: str) -> str:
    if format_str == "mp3":
        return "libmp3lame"
    if format_str == "ogg":
        return "libvorbis"
    raise ValueError(LocaleManage.get("core.ffmpeg_launcher.unsupported_audio_format", format=format_str))


def _get_audio_quality_args(format_str: str, audio_quality: int) -> list[str]:
    if audio_quality not in (0, 1, 2):
        raise ValueError(LocaleManage.get("core.ffmpeg_launcher.invalid_quality", quality=audio_quality))

    if format_str == "mp3":
        # vbr -q:a 0/1/2
        return ["-q:a", str(audio_quality)]

    if format_str == "ogg":
        # tier 0/1/2 -> q 8/7/6
        mapping = {0: "8", 1: "7", 2: "6"}
        return ["-q:a", mapping[audio_quality]]

    raise ValueError(LocaleManage.get("core.ffmpeg_launcher.unsupported_format_for_quality", format=format_str))


def _get_volume_filter(volume_percent: int) -> str | None:
    # volume=100 means no filter.
    if volume_percent == 100:
        return None
    return f"volume={volume_percent / 100.0:.2f}"


def start_ffmpeg_for_media_task(process: QProcess, config: Any) -> Tuple[bool, str]:
    """Start ffmpeg for a media task using the provided QProcess.

    Scheduler must stay clean and only pass (process, task.config) here.

    Returns:
        (ok, message)
    """
    if not isinstance(config, MediaAudioTaskConfig):
        return False, LocaleManage.get("core.ffmpeg_launcher.unsupported_media_task_config")

    cfg: MediaAudioTaskConfig = config

    ffmpeg_exe, ok, msg = SettingsManage.get_path("ffmpeg_exe")
    if not ok or not ffmpeg_exe:
        return False, LocaleManage.get("core.ffmpeg_launcher.ffmpeg_path_not_available", error=msg)

    input_path = str(Path(cfg.input_path))
    if not cfg.output_path:
        return False, LocaleManage.get("core.ffmpeg_launcher.output_path_missing")
    output_path = str(Path(cfg.output_path))

    # Ensure output dir exists
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, LocaleManage.get("core.ffmpeg_launcher.failed_create_output_dir", error=str(e))

    # Delete existing output file if present
    try:
        if os.path.exists(output_path):
            os.remove(output_path)
    except Exception as e:
        return False, LocaleManage.get("core.ffmpeg_launcher.failed_remove_existing_output", error=str(e))

    try:
        audio_codec = _get_audio_codec(cfg.format)
        quality_args = _get_audio_quality_args(cfg.format, int(cfg.audio_quality))
        vol_filter = _get_volume_filter(int(cfg.volume))
    except Exception as e:
        return False, LocaleManage.get("core.ffmpeg_launcher.invalid_audio_config", error=str(e))

    args: list[str] = [
        "-y",
        "-hide_banner",
        "-stats",
        "-loglevel",
        "error",
        "-i",
        input_path,
        "-c:a",
        audio_codec,
        *quality_args,
        "-ar",
        str(cfg.sample_rate),
        "-ac",
        "2",
    ]

    if vol_filter:
        args.extend(["-af", vol_filter])

    if cfg.clear_metadata:
        args.extend(["-map_metadata", "-1"])

    args.append(output_path)

    process.setProgram(ffmpeg_exe)
    process.setArguments(args)
    process.start()

    return True, LocaleManage.get("core.ffmpeg_launcher.ffmpeg_started")
