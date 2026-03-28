from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Tuple

from PyQt6.QtCore import QProcess

from locales import LocaleManage
from settings import SettingsManage
from tasks.task_configs import MediaAudioTaskConfig, RunFfmpegTaskConfig


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


def _parse_preset(preset: str) -> str:
    # Keep minimal validation; ffmpeg will reject unknown presets.
    return (preset or "medium").strip() or "medium"


def _build_audio_filters(*, volume: int, pad_start_sec: float | None, pad_end_sec: float | None) -> str | None:
    filters: list[str] = []

    # Start padding: adelay in ms. "delays|delays" for stereo.
    if pad_start_sec is not None and pad_start_sec > 0:
        delay_ms = int(round(pad_start_sec * 1000.0))
        filters.append(f"adelay={delay_ms}|{delay_ms}")

    vol = _get_volume_filter(int(volume))
    if vol:
        filters.append(vol)

    # End padding: apad in seconds.
    if pad_end_sec is not None and pad_end_sec > 0:
        filters.append(f"apad=pad_dur={pad_end_sec}")

    if not filters:
        return None
    return ",".join(filters)


def _build_video_filters(
    *,
    width: int | None,
    height: int | None,
    pad_start_sec: float | None,
    pad_end_sec: float | None,
) -> str | None:
    filters: list[str] = []

    if width and height:
        filters.append(f"scale={int(width)}:{int(height)}")

    # tpad supports start_duration/stop_duration.
    if (pad_start_sec is not None and pad_start_sec > 0) or (pad_end_sec is not None and pad_end_sec > 0):
        parts: list[str] = []
        if pad_start_sec is not None and pad_start_sec > 0:
            parts.append(f"start_duration={pad_start_sec}")
        if pad_end_sec is not None and pad_end_sec > 0:
            parts.append(f"stop_duration={pad_end_sec}")
        parts.append("color=black")
        filters.append("tpad=" + ":".join(parts))

    if not filters:
        return None
    return ",".join(filters)


def _get_aac_quality_args(audio_quality: int) -> list[str]:
    # Map tier to bitrate for AAC in video.
    if audio_quality not in (0, 1, 2):
        raise ValueError(LocaleManage.get("core.ffmpeg_launcher.invalid_quality", quality=audio_quality))
    mapping = {0: "128k", 1: "192k", 2: "256k"}
    return ["-b:a", mapping[audio_quality]]


def start_ffmpeg_for_media_task(process: QProcess, config: Any) -> Tuple[bool, str]:
    """Start ffmpeg for a media task using the provided QProcess.

    Scheduler must stay clean and only pass (process, task.config) here.

    Returns:
        (ok, message)
    """
    if isinstance(config, MediaAudioTaskConfig):
        cfg_audio: MediaAudioTaskConfig = config

        ffmpeg_exe, ok, msg = SettingsManage.get_path("ffmpeg_exe")
        if not ok or not ffmpeg_exe:
            return False, LocaleManage.get("core.ffmpeg_launcher.ffmpeg_path_not_available", error=msg)

        input_path = str(Path(cfg_audio.input_path))
        if not cfg_audio.output_path:
            return False, LocaleManage.get("core.ffmpeg_launcher.output_path_missing")
        output_path = str(Path(cfg_audio.output_path))

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
            audio_codec = _get_audio_codec(cfg_audio.format)
            quality_args = _get_audio_quality_args(cfg_audio.format, int(cfg_audio.audio_quality))
            vol_filter = _get_volume_filter(int(cfg_audio.volume))
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
            str(cfg_audio.sample_rate),
            "-ac",
            "2",
        ]

        if vol_filter:
            args.extend(["-af", vol_filter])

        if cfg_audio.clear_metadata:
            args.extend(["-map_metadata", "-1"])

        args.append(output_path)

        process.setProgram(ffmpeg_exe)
        process.setArguments(args)
        process.start()

        return True, LocaleManage.get("core.ffmpeg_launcher.ffmpeg_started")

    if not isinstance(config, RunFfmpegTaskConfig):
        return False, LocaleManage.get("core.ffmpeg_launcher.unsupported_media_task_config")

    cfg: RunFfmpegTaskConfig = config

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
        # Common base args
        args: list[str] = [
            "-y",
            "-hide_banner",
            "-stats",
            "-loglevel",
            "error",
            "-i",
            input_path,
        ]

        # Trim start/end
        if cfg.trim_start_sec is not None:
            args.extend(["-ss", f"{float(cfg.trim_start_sec)}"])

        to_sec = cfg.resolved_trim_end_sec()
        if to_sec is not None:
            args.extend(["-to", f"{float(to_sec)}"])

        if cfg.media_type == "audio":
            audio_codec = _get_audio_codec(cfg.audio_format)
            quality_args = _get_audio_quality_args(cfg.audio_format, int(cfg.audio_quality))

            args.extend(["-c:a", audio_codec, *quality_args])
            args.extend(["-ar", str(cfg.sample_rate)])
            args.extend(["-ac", "2"])  # always force stereo

            af = _build_audio_filters(
                volume=int(cfg.volume),
                pad_start_sec=cfg.pad_start_sec,
                pad_end_sec=cfg.pad_end_sec,
            )
            if af:
                args.extend(["-af", af])

        else:
            # Video / video_muted
            vf = _build_video_filters(
                width=(None if cfg.use_origin_resolution else cfg.width),
                height=(None if cfg.use_origin_resolution else cfg.height),
                pad_start_sec=cfg.pad_start_sec,
                pad_end_sec=cfg.pad_end_sec,
            )
            if vf:
                args.extend(["-vf", vf])

            # Video encoder
            args.extend(["-pix_fmt", "yuv420p"])
            args.extend(["-c:v", "libx264"])
            args.extend(["-preset", _parse_preset(cfg.preset)])
            args.extend(["-crf", str(int(cfg.crf))])

            if not cfg.use_origin_fps and cfg.fps is not None:
                args.extend(["-r", f"{float(cfg.fps)}"])

            if cfg.gop_30:
                args.extend(["-g", "30"])

            if cfg.media_type == "video_muted":
                args.append("-an")
            else:
                # Encode audio to AAC for video
                args.extend(["-c:a", "aac", *(_get_aac_quality_args(int(cfg.audio_quality)))])
                args.extend(["-ar", str(cfg.sample_rate)])
                args.extend(["-ac", "2"])  # always force stereo

                af = _build_audio_filters(
                    volume=int(cfg.volume),
                    pad_start_sec=cfg.pad_start_sec,
                    pad_end_sec=cfg.pad_end_sec,
                )
                # Keep A/V stable on some inputs
                if af:
                    af = af + ",aresample=async=1"
                else:
                    af = "aresample=async=1"
                args.extend(["-af", af])

        if cfg.clear_metadata:
            args.extend(["-map_metadata", "-1"])

        args.append(output_path)

    except Exception as e:
        # Use existing locale key if possible; otherwise return a clear message.
        if cfg.media_type == "audio":
            return False, LocaleManage.get("core.ffmpeg_launcher.invalid_audio_config", error=str(e))
        return False, LocaleManage.get("core.ffmpeg_launcher.invalid_video_config", error=str(e))

    process.setProgram(ffmpeg_exe)
    process.setArguments(args)
    process.start()

    return True, LocaleManage.get("core.ffmpeg_launcher.ffmpeg_started")
